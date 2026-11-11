# Resources outside the environment module (DES-008): the Shared VPC
# attachment, the org-policy override that allows a public Cloud Run service
# without an allUsers binding, and the vae-images Artifact Registry repo.
# Apply this before envs/stage.

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
    prefix = "vae/shared"
  }
}

locals {
  region  = "us-west1"
  project = "hl-vae-stage"

  # The staging Shared VPC (hl_main stage is attached to it too).
  host_project = "vpc-host-staging-yk380-hm150"
}

provider "google" {
  region = local.region
}

# The Org Policy API needs an explicit quota project when Terraform runs with
# user Application Default Credentials.
provider "google" {
  alias                 = "quota"
  region                = local.region
  billing_project       = local.project
  user_project_override = true
}

# compute: needed before the project can be attached to the Shared VPC.
resource "google_project_service" "apis" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "orgpolicy.googleapis.com",
  ])
  project            = local.project
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_shared_vpc_service_project" "stage" {
  host_project    = local.host_project
  service_project = local.project
  depends_on      = [google_project_service.apis]
}

# vae-stage-web uses invoker_iam_disabled (public without an allUsers binding,
# so domain-restricted sharing stays on). That needs this managed constraint
# relaxed on the project.
resource "google_org_policy_policy" "allow_invoker_iam_disabled" {
  provider = google.quota
  name     = "projects/${local.project}/policies/run.managed.requireInvokerIam"
  parent   = "projects/${local.project}"
  spec {
    rules {
      enforce = "FALSE"
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_artifact_registry_repository" "images" {
  project       = local.project
  location      = local.region
  repository_id = "vae-images"
  format        = "DOCKER"
  description   = "VAE images, built by Cloud Build"

  # Keep the 10 newest and anything tagged stage; delete the rest after 30 days.
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }
  cleanup_policies {
    id     = "keep-env-tags"
    action = "KEEP"
    condition {
      tag_state    = "TAGGED"
      tag_prefixes = ["stage"]
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [google_project_service.apis]
}

output "image_repo" {
  value = "${local.region}-docker.pkg.dev/${local.project}/${google_artifact_registry_repository.images.repository_id}/vae"
}

output "artifact_repo" {
  value = {
    project  = local.project
    location = local.region
    name     = google_artifact_registry_repository.images.repository_id
  }
}
