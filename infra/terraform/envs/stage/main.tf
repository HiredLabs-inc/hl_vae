# VAE stage (DES-008): hl-vae-stage, on the staging Shared VPC.
# Apply infra/terraform/shared first.

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.20"
    }
  }
  backend "gcs" {
    bucket = "hiredlabs-tf-state"
    prefix = "vae/stage"
  }
}

provider "google" {
  region = "us-west1"
}

module "env" {
  source = "../../modules/vae-env"

  env        = "stage"
  project_id = "hl-vae-stage"

  host_project_id = "vpc-host-staging-yk380-hm150"
  network         = "vpc-staging-shared"
  subnet          = "subnet-staging-1"

  # From shared/ (outputs image_repo and artifact_repo).
  image_repo    = "us-west1-docker.pkg.dev/hl-vae-stage/vae-images/vae"
  artifact_repo = { project = "hl-vae-stage", location = "us-west1", name = "vae-images" }

  web_min_instances = 0
  web_max_instances = 3
  web_memory        = "512Mi"

  # Stopped unless someone is testing: about $1/mo stopped.
  sql_disk_type              = "PD_HDD"
  sql_always_on              = false
  sql_nightly_stop           = true
  sql_retained_backups       = 1
  sql_point_in_time_recovery = false
  deletion_protection        = false

  # Who may read the secret and add or disable versions (DES-003). Not decided
  # yet; until then, project owners do it through their owner role.
  secret_managers = []

  deploy_branch = "staging"
}

output "env" {
  value = module.env
}
