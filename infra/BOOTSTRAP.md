# Bootstrap (one time, by hand)

Done once, before the first `terraform apply` (DES-008 step 3). Everything
after this is in Terraform or in the [README](README.md).

## Who can do it

The person running the bootstrap and the first applies needs:

- **Owner** on `hl-vae-stage`.
- **Billing Account User** on the HiredLabs billing account, to link it.
- **Shared VPC Admin** (`roles/compute.xpnAdmin`) on the org or the Common
  folder, so `shared/` can attach `hl-vae-stage` to `vpc-host-staging-yk380-hm150`.
- **Compute Network Admin** on `vpc-host-staging-yk380-hm150`, so
  `envs/stage` can grant `compute.networkUser` on `subnet-staging-1`.
- **Organization Policy Administrator** on the org, so `shared/` can relax
  `run.managed.requireInvokerIam` on the project.
- **Storage Object Admin** on `gs://hiredlabs-tf-state`.

## Steps

1. **Project.** Create `hl-vae-stage` in the Staging folder and link the
   billing account:

   ```bash
   gcloud projects create hl-vae-stage --folder=<Staging folder id>
   gcloud billing projects link hl-vae-stage --billing-account=<billing account id>
   ```

2. **Cloud Build GitHub App.** In `hl-vae-stage`: Console → Cloud Build →
   Triggers → **Connect repository** → GitHub (Cloud Build GitHub App,
   **1st gen**) → `HiredLabs-inc/hl_vae`. Don't create a trigger there;
   Terraform creates `vae-stage-deploy`. This must be done before applying
   `envs/stage`, or creating the trigger fails.

3. **`staging` branch.** Create it on `origin` from `develop`:

   ```bash
   git push origin origin/develop:refs/heads/staging
   ```

   Then protect it with a **separate** ruleset targeting `staging` (DES-005):
   require the status check `checks` (GitHub Actions), block deletion and
   force-pushes, and **don't** require a pull request. Don't add `staging` to
   the "Protect develop and main" ruleset: its pull-request rule would reject
   the promotion push. With this rule, `git push origin develop:staging`
   is accepted only when the commit has already passed `CI / checks` on
   `develop`.

4. **State bucket.** `gs://hiredlabs-tf-state` already exists (hl_main uses
   it, versioned). Check you can read and write it; VAE only adds the
   `vae/shared` and `vae/stage` prefixes:

   ```bash
   gcloud storage ls gs://hiredlabs-tf-state/
   ```

5. **Application Default Credentials** for Terraform:

   ```bash
   gcloud auth application-default login
   ```

Then continue with *Stand up stage* in the [README](README.md).
