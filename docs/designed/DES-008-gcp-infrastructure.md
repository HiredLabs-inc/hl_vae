# DES-008: GCP infrastructure (stage on Cloud Run)

- **Status:** Designed
- **Area:** Infrastructure
- **Created:** 2026-11-08
- **Updated:** 2026-11-08
- **Related:** supersedes DES-004 and DES-007. Follow-ups: DES-002, DES-003, DES-005, DES-006, DES-009. Modeled on `hl_main/infra/` (`TARGET_DESIGN.md`, `README.md`).

## Summary

VAE gets one hosted environment, **stage**, on Google Cloud. It uses the same
pattern as hl_main: Cloud Run, Cloud SQL Postgres on private IP over the
Shared VPC, Secret Manager, keyless service accounts, Cloud Build deploys, and
everything provisioned by Terraform in `infra/`. The target cost is
**$2–5/month**.

## Motivation / Problem

VAE is a bare Django app. It uses SQLite, a hardcoded `SECRET_KEY`,
`DEBUG = True` and `ALLOWED_HOSTS = ["*"]`, and it can't be deployed yet. It
needs somewhere hosted to demo and test. The same team runs hl_main, so VAE
should look like hl_main: the same naming, the same runbook shape, and the same
deploy flow. Then nothing about it has to be learned twice.

VAE may never go to production, so this design covers **stage only** and is
tuned for cost. Prod is a later decision. The Terraform module is parameterised
by environment, so adding prod later means adding `envs/prod` rather than
redesigning anything.

## Goals and Non-goals

**Goals**

- A reproducible stage environment, defined in Terraform and reviewed in git.
- A push to `staging` builds, migrates and deploys. `develop` is promoted with
  `git push origin develop:staging`.
- No service account keys anywhere, and no secrets or passwords in Terraform state.
- Scale to zero. The database is stopped when nobody is testing.
- Decide DES-004 (database) and DES-007 (deploy target), and define the
  contract that DES-002, -003, -005 and -006 implement.

**Non-goals**

- A prod environment, load balancer, Cloud CDN or Certificate Manager.
- A custom domain (DES-009).
- Background workers, Cloud Tasks, or scheduled jobs beyond the SQL stop.
- A media bucket. Add one when a feature needs user uploads.
- Multi-region or disaster recovery. Stage data is disposable.
- A cloud dev environment. Dev stays local.

## Proposed Design

### Naming and placement

Resources are named `vae-<env>-<thing>`, so on stage that's `vae-stage-*`. This
mirrors hl_main's `hl-<env>-*`.

```
Org hiredlabs.org
├── Common/      vpc-host-staging-yk380-hm150 (vpc-staging-shared, subnet-staging-1 us-west1)
└── Staging/     hl-main-stage   (hl_main, unchanged)
                 hl-vae-stage    ← new: all VAE stage workloads, service project of vpc-host-staging
```

Region: **us-west1**, the same as hl_main.

### Resources

| Piece | VAE stage | hl_main reference |
|---|---|---|
| Project | `hl-vae-stage`, a service project of the staging Shared VPC | `shared/main.tf` `local.hosts` |
| Network | Cloud Run Direct VPC egress (`PRIVATE_RANGES_ONLY`) on `subnet-staging-1`. Cloud SQL reuses the existing `sql-dev` private-services range on `vpc-staging-shared`. No VPC connector | `hl-env` web `vpc_access` |
| Cloud Run web | `vae-stage-web`: `INGRESS_TRAFFIC_ALL`, `invoker_iam_disabled = true` (public without an `allUsers` binding), min 0 / max 3, 1 CPU, 512Mi, `cpu_idle`, startup CPU boost. Placeholder image until the first build. `ignore_changes` on image | `google_cloud_run_v2_service.web` |
| Cloud Run jobs | `vae-stage-migrate` runs `migrate` on every deploy. `vae-stage-manage` runs any management command, with args given at execution | `google_cloud_run_v2_job.jobs` |
| Cloud SQL | `vae-stage-sql`: Postgres 15, Enterprise, db-f1-micro, 10 GB **HDD** with auto-resize, zonal, no public IP, 1 retained backup, no PITR, no deletion protection. Database `vae`. **Created running**, then stopped nightly by Cloud Scheduler and started by deploys. `ignore_changes` on `activation_policy` | `google_sql_database_instance.db`, `sql_nightly_stop` |
| Secret | `vae-stage-app-env`: an `.env`-format blob. Terraform creates only the container; versions are added with `gcloud` | `google_secret_manager_secret.app_env` |
| Service accounts | `vae-stage-app` is the runtime for web and jobs: Cloud SQL client, secret accessor, log writer. `vae-stage-deploy` is the Cloud Build deployer: run developer, AR writer, act-as app, Cloud SQL editor so it can start the instance. `vae-stage-sql-scheduler` handles the nightly stop. **No keys**, and the default compute SA isn't used | `hl-env` SA and IAM blocks |
| Images | Artifact Registry repo `vae-images` in `hl-vae-stage`, image `vae`. Tags `:<short-sha>` and `:stage`. Cleanup keeps the 10 most recent plus `stage`-tagged images and deletes the rest after 30 days | `shared/main.tf` `images` |
| CI/CD | Cloud Build trigger `vae-stage-deploy` on `HiredLabs-inc/hl_vae`, branch `^staging$`, file `infra/cloudbuild/deploy.yaml`, `ignored_files` = `infra/terraform/**` and `**/*.md`. Substitution `_START_SQL=true` | `google_cloudbuild_trigger.deploy` |
| Terraform state | The existing bucket `gs://hiredlabs-tf-state` (versioned), with prefixes `vae/shared` and `vae/stage` | backend blocks |

### Deploy pipeline (`infra/cloudbuild/deploy.yaml`)

This is hl_main's pipeline without the worker and reminder steps:

1. **pull-cache:** `docker pull $_IMAGE:stage || true`.
2. **build:** tag `:$SHORT_SHA` and `:stage`, using `--cache-from :stage`.
3. **push:** `--all-tags`.
4. **start-sql:** when `_START_SQL=true`, run `patch --activation-policy=ALWAYS --async`,
   then poll for up to 30 minutes until the instance is `RUNNABLE` *and* no
   operations are pending.
5. **migrate:** point `vae-stage-migrate` and `vae-stage-manage` at the new
   image, then execute the migrate job with `--wait`.
6. **deploy-web:** `gcloud run deploy vae-stage-web --image=$_IMAGE:$SHORT_SHA`.

Cloud Build owns the image. Terraform owns everything else.

### Repo layout

```
infra/
├── README.md            # what lives where, conventions, day-2 runbook
├── BOOTSTRAP.md         # one-time setup, done by hand (see Implementation Plan)
├── cloudbuild/
│   └── deploy.yaml
└── terraform/
    ├── .gitignore       # .terraform/, *.tfstate*, *.tfplan
    ├── shared/          # Shared VPC attachment, org-policy override, AR repo
    ├── modules/
    │   └── vae-env/     # one environment (main.tf, variables.tf, outputs.tf, versions.tf)
    └── envs/
        └── stage/       # module call with stage values
```

`modules/vae-env` is **forked from hl_main's `hl-env` and trimmed**. It drops
the worker service, Cloud Tasks, the signup-reminders job and scheduler, the
media bucket and `aiplatform`. A module shared between the two repos is out of
scope, because the apps will drift and coupling their Terraform would slow both
down.

Provider: `hashicorp/google ~> 6.20`, Terraform `>= 1.5`. Use the same pins as hl_main.

### App contract

This is what the code has to provide for the infrastructure to work. The
details are built in the follow-up items.

- **Settings module `hl_vae.settings.cloud`**, shared by every Cloud Run environment.
  `hl_vae.settings.stage` imports it (DES-002 sets up the package; DES-003 covers the rest).
  It follows `hl_main/settings/cloud.py`:
  - The Cloud Run env sets `DJANGO_SETTINGS_MODULE=hl_vae.settings.stage`, `GCP_PROJECT_ID` and `GCP_SECRETS_NAME`.
  - At import, it reads `projects/$GCP_PROJECT_ID/secrets/$GCP_SECRETS_NAME/versions/latest`
    and loads it with `django-environ`. Values already in the environment win.
  - It sets `DEBUG = False`. `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` come from
    `ALLOWED_HOSTS` plus the host of `CLOUDRUN_SERVICE_URL`, plus the
    deterministic `*-<project number>.us-west1.run.app` host.
  - Postgres connects on private IP with `CONN_MAX_AGE = 60` and
    `CONN_HEALTH_CHECKS = True`. db-f1-micro allows about 25 connections, and
    one instance with 8 threads uses at most 8.
- **Secret keys** (in `vae-stage-app-env`):

  ```
  DJANGO_SECRET_KEY=           # new random value
  GCP_REGION=us-west1
  GCP_CLOUDSQL_DB_NAME=vae
  GCP_CLOUDSQL_USER=vae
  GCP_CLOUDSQL_PASSWORD=       # from the gcloud sql users create step
  GCP_CLOUDSQL_PRIVATE_IP=     # terraform output sql_private_ip
  CLOUDRUN_SERVICE_URL=        # terraform output web_url
  ALLOWED_HOSTS=               # empty on stage
  ```
- **Build-only settings module `hl_vae.settings.build`**, with no secrets and no
  database, so `collectstatic` can run during `docker build`.
- **Dockerfile:** `python:3.12-slim` with uv (`uv sync --frozen --no-dev`).
  It runs `collectstatic` at build time and starts with
  `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 hl_vae.wsgi:application`.
  There are no credentials in the image; Cloud Run uses the metadata server.
- **Static files:** **WhiteNoise** serves them from the image
  (`CompressedManifestStaticFilesStorage`). That's enough without a load
  balancer or CDN, and it's the decision for DES-006.
- **New runtime dependencies:** `gunicorn`, `psycopg[binary]`, `django-environ`,
  `google-cloud-secret-manager`, `whitenoise`.
- **Local dev** stays on SQLite through the dev settings. Local Postgres is
  optional. There is no cloud dev environment.

### Lessons carried over from hl_main

These are from hl_main's implementation notes (2026-10-14/15), and they're
built in here from the start:

- **Org policy:** `invoker_iam_disabled` needs `run.managed.requireInvokerIam`
  set to *not enforced* on the project. Put that in `shared/` from day one,
  through a `google.quota` provider alias with `billing_project` set, because
  the Org Policy API needs a quota project when run with user ADC.
- **SQL is created running.** You can't create a database or user on a
  stopped instance. The nightly scheduler stops it afterwards, and
  `ignore_changes` keeps Terraform from fighting the start/stop.
- **The trigger reads `deploy.yaml` from GitHub**, so the file has to be on
  `origin/staging` before the first manual `gcloud builds triggers run`.
  Otherwise the run fails with `NOT_FOUND: File infra/cloudbuild/deploy.yaml`.
- **Starting the database is slow.** It can take about 15 minutes and can
  report `RUNNABLE` before it's done, so the start step also waits for pending
  operations.

### Network capacity check (2026-11-08)

The values below were checked with `gcloud` against `vpc-host-staging-yk380-hm150`.

| Range | CIDR | Used by | Headroom |
|---|---|---|---|
| `subnet-staging-1` (us-west1) | 10.0.16.0/24, 252 usable | Direct VPC egress for hl_main stage: web max 10, worker max 5, jobs | Plenty. Direct VPC egress reserves about 2 IPs per instance during revision rollover. hl_main stage peaks at about 40, and VAE adds about 10 (web max 3 plus jobs). Google's documented minimum subnet is /26, and this is a /24 |
| `sql-dev` (private services access) | 10.0.32.0/**24** | `hl-stage-sql` at 10.0.32.22 | Enough for a second us-west1 instance. Cloud SQL places instances from the same network and region in the existing producer subnet. Confirm at the first apply (see Open Questions) |

Note: hl_main's `shared/main.tf` comment says this range is `/20`. It's
actually a `/24`. That's harmless, but the comment should be corrected in
hl_main.

### Cost (list-price estimate)

| Item | Est. monthly cost |
|---|---|
| Cloud SQL f1-micro, 10 GB HDD | about $1 stopped, $2–3 at typical use, about $8.60 if left on |
| Cloud Run (scale to zero, low traffic) | about $0 (free tier) |
| Artifact Registry, Secret Manager, Scheduler, state | cents |
| Cloud Build | about $0 (within the free build minutes) |
| **Total** | **about $2–5** |

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| App Engine, GKE Autopilot or a VM | Familiar or flexible | More ops work, or deprecated in favour of Cloud Run | Cloud Run was chosen, and it matches hl_main |
| gcloud scripts or console setup | Faster first day | Drifts, and hard to tear down or reproduce | Terraform was chosen, and it matches hl_main |
| Deploy into `hl-main-stage` | No new project | Shared IAM, quotas and billing with hl_main | A separate project is a clean boundary |
| A database on `hl-stage-sql` | About $0 extra | Tied to hl_main's start/stop schedule and maintenance, and crosses projects | Isolation is worth $1–3/mo |
| Images in hl_main's `hl-images` repo | One registry | Shared cleanup policy and IAM, and the repo lives in hl-main-prod | Keep VAE self-contained |
| Load balancer with a custom domain | Branded URL, CDN | About $18/mo | Not needed for stage. Deferred to DES-009 |
| One Terraform module shared with hl_main | No duplication | Changes to one app ripple into the other | Premature coupling |
| Serverless VPC Access connector | Works | About $10–15/mo in always-on VMs | Direct VPC egress is free |

## Implementation Plan

Work happens on a branch off `develop` and reaches stage through `develop` → `staging`.

1. **App contract** (implements parts of DES-002, -003 and -006):
   - [ ] Add the dependencies, `hl_vae/settings/cloud.py`, `hl_vae/settings/build.py`
     and WhiteNoise, and switch `stage.py` to `from .cloud import *` (layout from DES-002). Move the hardcoded `SECRET_KEY` out of the committed settings.
   - [ ] Add a `Dockerfile` and `.dockerignore`. Check that `docker build` works
     and that the container serves locally against Postgres.
2. **Terraform skeleton:**
   - [ ] Add `infra/terraform/{shared,modules/vae-env,envs/stage}` and
     `infra/cloudbuild/deploy.yaml`.
   - [ ] Add `infra/README.md` (layout, conventions, day-2 runbook) and
     `infra/BOOTSTRAP.md` (below).
   - [ ] Confirm `terraform fmt -check` and `terraform validate` pass for every root.
3. **Bootstrap**, done by the user by hand following `infra/BOOTSTRAP.md`:
   - [ ] Create project `hl-vae-stage` in the Staging folder and link the billing account.
   - [ ] Connect the Cloud Build GitHub App to `HiredLabs-inc/hl_vae` in `hl-vae-stage`
     (Console → Cloud Build → Triggers → Connect repository, 1st gen).
   - [ ] Create the `staging` branch on `origin` from `develop`.
   - [ ] Confirm `gs://hiredlabs-tf-state` access. The bucket already exists; only the `vae/*` prefixes are new.
4. **Apply:**
   - [ ] `terraform apply` in `infra/terraform/shared`, then in `envs/stage`.
5. **Out-of-band secrets:**
   - [ ] `gcloud sql users create vae --instance=vae-stage-sql --password=... --project=hl-vae-stage`.
   - [ ] Write the `.env`, run `gcloud secrets versions add vae-stage-app-env --data-file=.env`,
     and delete the local file.
6. **First deploy:**
   - [ ] Promote `develop` to `staging` (`git push origin develop:staging`), with
     `infra/cloudbuild/deploy.yaml` already on `develop`.
   - [ ] Smoke-test the `run.app` URL.
7. **Lifecycle check:**
   - [ ] The next morning, confirm `vae-stage-sql` was stopped by the scheduler.
   - [ ] Confirm the next deploy starts it again.

## Testing / Verification

- `terraform fmt -check`, `terraform validate` and `terraform plan` run clean in
  every root, and `plan` shows no changes after the apply.
- `docker build .` succeeds, and the container serves `/` and `/admin/` with
  static files when run locally against Postgres.
- The first `vae-stage-deploy` Cloud Build run is green through every step.
- On the `run.app` URL, the index renders, `/admin/` loads styled, and there's
  no `DisallowedHost` or CSRF error on admin login.
- `gcloud run jobs execute vae-stage-manage --args=manage.py,check,--deploy`
  passes with no security warnings.
- Nobody can read the secret except `vae-stage-app`, and
  `gcloud iam service-accounts keys list` shows no user-managed keys.

## Open Questions

- ~~Who creates `hl-vae-stage` and links billing?~~ **Answered:** the user does
  it by hand. The steps go in `infra/BOOTSTRAP.md` as part of implementation.
- ~~Is `subnet-staging-1` big enough to share with hl_main?~~ **Answered:** yes.
  See *Network capacity check*.
- ~~Does `staging` need creating on `origin`?~~ **Answered:** yes. The user
  creates it, and it's a step in `infra/BOOTSTRAP.md`.
- ~~Custom domain later?~~ **Answered:** yes, the intent is
  `veteranacademicexchange.org`, but it depends on real-world factors.
  Tracked as **DES-009** (Idea).
- At the first `envs/stage` apply, confirm `vae-stage-sql` gets an address in
  `sql-dev` (10.0.32.0/24). If the producer subnet can't take it, allocate a
  second range on `vpc-staging-shared` in `shared/`.

## Changelog

- 2026-11-08 — Created. Open questions answered by the user, and the subnet capacity was checked.
- 2026-11-08 — Cloud Run now uses `hl_vae.settings.stage` (which imports `cloud`), following the DES-002 layout.
