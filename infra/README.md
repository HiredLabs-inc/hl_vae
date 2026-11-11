# infra/

VAE's one hosted environment, **stage**, on Google Cloud (DES-008 in the
[backlog](../docs/backlog.md)). It follows hl_main's layout and conventions.

| Path | What |
|---|---|
| `BOOTSTRAP.md` | One-time setup, done by hand before the first apply |
| `terraform/shared` | Shared VPC attachment of `hl-vae-stage`, the org-policy override for public Cloud Run, the `vae-images` Artifact Registry repo |
| `terraform/modules/vae-env` | One environment: APIs, service accounts, Cloud SQL, the secret container, Cloud Run web and jobs, nightly SQL stop, deploy trigger. Forked from hl_main's `hl-env` and trimmed |
| `terraform/envs/stage` | The stage root (`hl-vae-stage`) |
| `cloudbuild/deploy.yaml` | Build → push → start SQL → migrate → deploy. A push to `staging` runs it |

**Conventions**

- Resources are named `vae-<env>-<thing>`, e.g. `vae-stage-web`.
- No service account keys anywhere. Cloud Run and Cloud Build use their
  service accounts through the metadata server.
- Cloud Build owns container images. Terraform owns everything else.
- Secrets and the DB password never go through Terraform, so they stay out of
  state. Terraform creates only the secret's container.
- State lives in `gs://hiredlabs-tf-state` under `vae/shared` and `vae/stage`.
- Region `us-west1`. Provider `hashicorp/google ~> 6.20`, Terraform `>= 1.5`.
  `.terraform.lock.hcl` is committed for linux_amd64, darwin_arm64 and
  darwin_amd64; after changing providers, re-run
  `terraform providers lock -platform=linux_amd64 -platform=darwin_arm64 -platform=darwin_amd64`.
- CI runs `terraform fmt -check` and `validate` on every root (no backend, no
  credentials). `plan` and `apply` are run by hand.
- `terraform init` creates `.terraform/` in each root. It's ignored by
  `infra/terraform/.gitignore`, so on a branch from before that file existed,
  git lists it as untracked. That's harmless: don't stash or commit it; it's
  ignored again once you're back on a current branch.

## What's in stage

| Piece | Name | Notes |
|---|---|---|
| Project | `hl-vae-stage` | Service project of the staging Shared VPC (`vpc-host-staging-yk380-hm150`) |
| Web | `vae-stage-web` | Public on its `run.app` URLs (`invoker_iam_disabled`), 0–3 instances, 1 CPU, 512Mi, Direct VPC egress on `subnet-staging-1` |
| Jobs | `vae-stage-migrate`, `vae-stage-manage` | `migrate` runs on every deploy; `manage` runs any management command |
| Database | `vae-stage-sql`, database `vae`, user `vae` | Postgres 15, db-f1-micro, 10 GB HDD, private IP only. Stopped nightly at 02:00 PT, started by deploys |
| Secret | `vae-stage-app-env` | `.env`-format blob read by `hl_vae/settings/cloud.py` |
| Service accounts | `vae-stage-app`, `vae-stage-deploy`, `vae-stage-sql-scheduler` | Runtime, Cloud Build deployer, nightly stop |
| Images | `us-west1-docker.pkg.dev/hl-vae-stage/vae-images/vae` | Tags `:<short sha>` and `:stage` |
| Deploy trigger | `vae-stage-deploy` | Push to `staging`; ignores `infra/terraform/**` and `**/*.md` |

## Stand up stage

First do everything in [`BOOTSTRAP.md`](BOOTSTRAP.md). Then:

```bash
cd infra/terraform/shared && terraform init && terraform apply
cd ../envs/stage          && terraform init && terraform apply
```

The shared root's Org Policy resource bills quota to `hl-vae-stage` (provider
alias `google.quota`), because user ADC has no quota project.

At the first stage apply, check that `vae-stage-sql` got an address in the
staging VPC's existing `sql-dev` range (10.0.32.0/24):
`terraform output -json env | jq -r .sql_private_ip`. If the range can't take
it, allocate a second range on `vpc-staging-shared` in `shared/`.

Then, using the values from `terraform output env`:

1. **DB user.** The instance is created running. The password stays out of state:

   ```bash
   gcloud sql users create vae --instance=vae-stage-sql --password='<generated>' --project=hl-vae-stage
   ```

2. **App secret.** Write the blob in memory (see *Edit the secret* below for
   the pattern) with the keys from the catalogue, then add it as the first version:

   ```
   DJANGO_SECRET_KEY=            # new random value (see Rotate DJANGO_SECRET_KEY)
   GCP_REGION=us-west1
   GCP_CLOUDSQL_DB_NAME=vae
   GCP_CLOUDSQL_USER=vae
   GCP_CLOUDSQL_PASSWORD=        # from step 1
   GCP_CLOUDSQL_PRIVATE_IP=      # output sql_private_ip
   CLOUDRUN_SERVICE_URL=         # output web_url
   ALLOWED_HOSTS=                # empty on stage
   ```

   ```bash
   f=$(mktemp -p /dev/shm vae-env.XXXXXX)
   $EDITOR "$f"
   gcloud secrets versions add vae-stage-app-env --data-file="$f" --project=hl-vae-stage
   rm -f "$f"
   ```

3. **First deploy.** The trigger reads `infra/cloudbuild/deploy.yaml` from
   GitHub, so it has to be on `staging` first. Promote `develop` from
   GitHub (see *Promote to stage*):

   ```bash
   git fetch origin && git push origin origin/develop:staging
   ```

   After that, a deploy can be re-run by hand:
   `gcloud builds triggers run vae-stage-deploy --branch=staging --project=hl-vae-stage`.

4. **Smoke test.** Open the `web_url`: the index renders, `/admin/` loads
   styled, and admin login has no `DisallowedHost` or CSRF error. Then:

   ```bash
   gcloud run jobs execute vae-stage-manage --region=us-west1 --project=hl-vae-stage \
     --args=manage.py,check,--deploy,--fail-level,WARNING --wait
   ```

## Day 2

**Promote to stage.** Pushes to `develop` don't deploy. To deploy what's on
`develop`, fast-forward `staging` to GitHub's `develop`:

```bash
git fetch origin && git push origin origin/develop:staging
```

Push `origin/develop`, not your local `develop`. That promotes exactly the
commit that was merged and checked by CI, however stale your local branch is.
(The first deploy failed with `File infra/cloudbuild/deploy.yaml not found`
because a local `develop` from before PR #10 was pushed.) The `staging`
ruleset rejects the push unless `CI / checks` passed on that commit.

**Run a management command.** `vae-stage-manage` takes the command as args:

```bash
gcloud run jobs execute vae-stage-manage --region=us-west1 --project=hl-vae-stage \
  --args=manage.py,createsuperuser,--no-input --wait
```

(`createsuperuser --no-input` reads `DJANGO_SUPERUSER_USERNAME`, `_EMAIL` and
`_PASSWORD`; pass them with `--update-env-vars` on the execution, never in the
secret.) The database must be running (see below).

**Stage database on demand.** It's created running and stopped every night at
02:00 PT. Deploys start it automatically. To start or stop it by hand:

```bash
gcloud sql instances patch vae-stage-sql --activation-policy=ALWAYS --project=hl-vae-stage   # NEVER to stop
```

Starting can take about 15 minutes.

## Secrets

Settings come from three places on Cloud Run (DES-003): plain env vars set by
Terraform, the `vae-stage-app-env` blob, and defaults in `cloud.py`
(non-secret only). Values already in the environment win over the blob.
Security switches (`DEBUG`, secure cookies, HSTS, SSL redirect) are code in
`cloud.py`, so the secret can't turn them off. A missing required value fails
the revision at startup with `Set the NAME environment variable`.

### Variable catalogue

A new variable is added here (and to `.env.example` if it's used locally) in
the same change that starts reading it.

| Variable | Read by | Local dev | Stage: set in | Secret | Required on stage |
|---|---|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Django | `manage.py` default `hl_vae.settings.dev` | Cloud Run env: `hl_vae.settings.stage` | no | yes (`wsgi.py` has no default) |
| `GCP_PROJECT_ID` | `cloud.py` | — | Cloud Run env: `hl-vae-stage` | no | yes |
| `GCP_SECRETS_NAME` | `cloud.py` | — | Cloud Run env: `vae-stage-app-env` | no | yes |
| `DJANGO_SECRET_KEY` | `dev.py`, `cloud.py` | optional; `dev.py` has a dev-only default | blob | **yes** | yes |
| `DJANGO_SECRET_KEY_FALLBACKS` | `cloud.py` | — | blob, normally empty | **yes** | no (default `[]`) |
| `GCP_REGION` | `cloud.py` | — | blob: `us-west1` | no | yes |
| `GCP_CLOUDSQL_DB_NAME` | `cloud.py` | — | blob: `vae` | no | yes |
| `GCP_CLOUDSQL_USER` | `cloud.py` | — | blob: `vae` | no | yes |
| `GCP_CLOUDSQL_PASSWORD` | `cloud.py` | — | blob | **yes** | yes |
| `GCP_CLOUDSQL_PRIVATE_IP` | `cloud.py` | — | blob (output `sql_private_ip`) | no | yes |
| `CLOUDRUN_SERVICE_URL` | `cloud.py` | — | blob (output `web_url`) | no | no (the deterministic host is still added) |
| `ALLOWED_HOSTS` | `dev.py`, `cloud.py` | optional; default `localhost,127.0.0.1,[::1]` | blob, empty on stage | no | no |
| `DJANGO_DEBUG` | `dev.py` only | optional; default `true` | **never read** | no | — |
| `DATABASE_URL` | `dev.py` only | optional; default SQLite at `db.sqlite3` | **never read** | maybe (local only) | — |
| `K_SERVICE` | `hl_vae/cloudrun.py` | — | set by Cloud Run | no | — |

### Who can read it

Only `vae-stage-app` has `secretAccessor` on the secret; the deployer and
Cloud Build don't, and no step in `deploy.yaml` reads it. People listed in
`secret_managers` (in `envs/stage/main.tf`) get `secretAccessor` and
`secretVersionManager` on this one secret. That list is empty until it's
decided; until then, project owners manage the secret through their owner role.

### Edit the secret

Work in memory, never in the repo, and delete the copy afterwards:

```bash
f=$(mktemp -p /dev/shm vae-env.XXXXXX)      # 0600, RAM-backed
gcloud secrets versions access latest --secret=vae-stage-app-env --project=hl-vae-stage > "$f"
$EDITOR "$f"
gcloud secrets versions add vae-stage-app-env --data-file="$f" --project=hl-vae-stage
rm -f "$f"
```

The blob is `KEY=value` per line, `#` comments, no `export`, no shell
expansion. Quote values that contain `#` or spaces.

### Apply a changed secret

The secret is read once, at startup, from `versions/latest`. Re-run the deploy
to pick up a new version:

```bash
gcloud builds triggers run vae-stage-deploy --branch=staging --project=hl-vae-stage
```

That creates a new web revision and repoints the jobs, and nothing drifts from
Terraform. Jobs pick up the new version on their next execution anyway.

### Add a variable

1. Read it in a settings module with `env(...)`. Use no default if stage needs it.
2. Add it to the catalogue above, and to `.env.example` if it's used locally.
3. Add a secret version that includes it **before** promoting the code to
   `staging`. Otherwise the new revision fails at startup and the old one keeps
   serving.

### Rotate `DJANGO_SECRET_KEY`

1. Generate a key:
   `uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`.
2. In a new version, set `DJANGO_SECRET_KEY` to the new key and
   `DJANGO_SECRET_KEY_FALLBACKS` to the old one. Apply.
3. After two weeks (Django's default session length), add a version with an
   empty `DJANGO_SECRET_KEY_FALLBACKS`. Apply.

On stage it's fine to skip the fallback and set only the new key. Everyone is
just logged out.

### Rotate the database password

1. `gcloud sql users set-password vae --instance=vae-stage-sql --prompt-for-password --project=hl-vae-stage`.
   The instance must be running.
2. Add a version with the new `GCP_CLOUDSQL_PASSWORD`. Apply.

Requests fail between steps 1 and 2. That's acceptable on stage.

### Retire old versions

After a change is verified, disable the previous version
(`gcloud secrets versions disable <n> --secret=vae-stage-app-env --project=hl-vae-stage`).
Leave it disabled, not destroyed, for 30 days so it can be re-enabled to roll
back, then destroy it.

### If a secret leaks

Rotate that value now using the steps above, disable every version that
contained it, and check who had access with
`gcloud secrets get-iam-policy vae-stage-app-env --project=hl-vae-stage`. If it
leaked into git, rotating it is the fix. Rewriting history isn't required.
