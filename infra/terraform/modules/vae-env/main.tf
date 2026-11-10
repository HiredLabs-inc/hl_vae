# One VAE environment (DES-008) in its own project, attached to a Shared VPC.
# Forked from hl_main's modules/hl-env and trimmed: no worker service, Cloud
# Tasks, media bucket, reminder job or Vertex AI. Cloud Build owns the
# container image; Terraform owns everything else.

locals {
  name = "vae-${var.env}"
  apis = [
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
  ]
  # Deployed until the first Cloud Build run replaces it.
  placeholder_image = "us-docker.pkg.dev/cloudrun/container/hello"

  network_id   = "projects/${var.host_project_id}/global/networks/${var.network}"
  subnet_id    = "projects/${var.host_project_id}/regions/${var.region}/subnetworks/${var.subnet}"
  run_agent    = "service-${data.google_project.this.number}@serverless-robot-prod.iam.gserviceaccount.com"
  secret_name  = "${local.name}-app-env"
  sql_instance = "${local.name}-sql"

  # The only plain env vars. Everything else comes from the secret (DES-003).
  container_env = {
    DJANGO_SETTINGS_MODULE = "hl_vae.settings.${var.env}"
    GCP_PROJECT_ID         = var.project_id
    GCP_SECRETS_NAME       = local.secret_name
  }
}

data "google_project" "this" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# --- Service accounts (no keys) ---------------------------------------------

resource "google_service_account" "app" {
  project      = var.project_id
  account_id   = "${local.name}-app"
  display_name = "VAE ${var.env} runtime (web and jobs)"
}

resource "google_service_account" "deploy" {
  project      = var.project_id
  account_id   = "${local.name}-deploy"
  display_name = "VAE ${var.env} Cloud Build deployer"
}

resource "google_project_iam_member" "app" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/logging.logWriter",
  ])
  project = var.project_id
  role    = each.value
  member  = google_service_account.app.member
}

resource "google_project_iam_member" "deploy" {
  for_each = toset(concat(
    ["roles/run.developer", "roles/logging.logWriter"],
    # Deploys start the stopped-by-default database before migrating.
    var.sql_always_on ? [] : ["roles/cloudsql.editor"],
  ))
  project = var.project_id
  role    = each.value
  member  = google_service_account.deploy.member
}

resource "google_service_account_iam_member" "deploy_acts_as_app" {
  service_account_id = google_service_account.app.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.deploy.member
}

resource "google_artifact_registry_repository_iam_member" "deploy_writer" {
  project    = var.artifact_repo.project
  location   = var.artifact_repo.location
  repository = var.artifact_repo.name
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.deploy.member
}

resource "google_artifact_registry_repository_iam_member" "run_agent_reader" {
  project    = var.artifact_repo.project
  location   = var.artifact_repo.location
  repository = var.artifact_repo.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${local.run_agent}"
  depends_on = [google_project_service.apis]
}

# Direct VPC egress into the Shared VPC subnet.
resource "google_compute_subnetwork_iam_member" "network_user" {
  for_each = {
    run_agent = "serviceAccount:${local.run_agent}"
    deploy    = google_service_account.deploy.member
  }
  project    = var.host_project_id
  region     = var.region
  subnetwork = var.subnet
  role       = "roles/compute.networkUser"
  member     = each.value
  depends_on = [google_project_service.apis]
}

# --- Secret -----------------------------------------------------------------

# Container only. The value is the .env blob read by hl_vae/settings/cloud.py,
# added out-of-band so no secret ends up in Terraform state (infra/README.md):
#   gcloud secrets versions add vae-<env>-app-env --data-file=... --project=<project>
resource "google_secret_manager_secret" "app_env" {
  project   = var.project_id
  secret_id = local.secret_name
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

# Only the runtime reads it. The deployer and Cloud Build don't.
resource "google_secret_manager_secret_iam_member" "app_env" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.app_env.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.app.member
}

resource "google_secret_manager_secret_iam_member" "app_env_managers" {
  for_each = {
    for pair in setproduct(var.secret_managers, [
      "roles/secretmanager.secretAccessor",
      "roles/secretmanager.secretVersionManager",
    ]) : "${pair[0]} ${pair[1]}" => { member = pair[0], role = pair[1] }
  }
  project   = var.project_id
  secret_id = google_secret_manager_secret.app_env.secret_id
  role      = each.value.role
  member    = each.value.member
}

# --- Cloud SQL --------------------------------------------------------------

resource "google_sql_database_instance" "db" {
  project             = var.project_id
  name                = local.sql_instance
  region              = var.region
  database_version    = "POSTGRES_15"
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.sql_tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_type         = var.sql_disk_type
    disk_size         = 10
    disk_autoresize   = true
    # Always created running (the database and user can't be created on a
    # stopped instance). With sql_always_on = false it's then stopped by the
    # nightly scheduler job and started by deploys.
    activation_policy           = "ALWAYS"
    deletion_protection_enabled = var.deletion_protection

    # Private IP only, from the network's existing private services access
    # range (sql-dev, 10.0.32.0/24, on the staging VPC).
    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = local.network_id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "08:00"
      point_in_time_recovery_enabled = var.sql_point_in_time_recovery
      transaction_log_retention_days = var.sql_point_in_time_recovery ? 7 : 1
      backup_retention_settings {
        retained_backups = var.sql_retained_backups
      }
    }

    # Sunday 03:00 Pacific
    maintenance_window {
      day  = 7
      hour = 10
    }
  }

  lifecycle {
    # Started and stopped outside Terraform (deploys, scheduler, by hand).
    ignore_changes = [settings[0].activation_policy]
  }

  depends_on = [google_project_service.apis]
}

# The DB user is created out-of-band so its password stays out of state:
#   gcloud sql users create vae --instance=vae-<env>-sql --password=... --project=<project>
resource "google_sql_database" "app" {
  project  = var.project_id
  instance = google_sql_database_instance.db.name
  name     = "vae"
}

# Nightly stop, so the database only runs while someone is testing.
resource "google_service_account" "sql_scheduler" {
  count        = var.sql_nightly_stop ? 1 : 0
  project      = var.project_id
  account_id   = "${local.name}-sql-scheduler"
  display_name = "Stops ${local.sql_instance} nightly"
}

resource "google_project_iam_member" "sql_scheduler" {
  count   = var.sql_nightly_stop ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.editor"
  member  = google_service_account.sql_scheduler[0].member
}

resource "google_cloud_scheduler_job" "sql_nightly_stop" {
  count     = var.sql_nightly_stop ? 1 : 0
  project   = var.project_id
  region    = var.region
  name      = "${local.sql_instance}-nightly-stop"
  schedule  = "0 2 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    http_method = "PATCH"
    uri         = "https://sqladmin.googleapis.com/v1/projects/${var.project_id}/instances/${local.sql_instance}"
    body        = base64encode(jsonencode({ settings = { activationPolicy = "NEVER" } }))
    headers     = { "Content-Type" = "application/json" }
    oauth_token {
      service_account_email = google_service_account.sql_scheduler[0].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_project_service.apis]
}

# --- Cloud Run --------------------------------------------------------------

resource "google_cloud_run_v2_service" "web" {
  project              = var.project_id
  name                 = "${local.name}-web"
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL" # served on its run.app URL
  invoker_iam_disabled = true                  # public without an allUsers binding (keeps domain-restricted sharing on)
  deletion_protection  = var.deletion_protection

  template {
    service_account                  = google_service_account.app.email
    timeout                          = "300s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = var.web_min_instances
      max_instance_count = var.web_max_instances
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = local.network_id
        subnetwork = local.subnet_id
      }
    }

    containers {
      image = local.placeholder_image
      resources {
        limits            = { cpu = "1", memory = var.web_memory }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      dynamic "env" {
        for_each = local.container_env
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  lifecycle {
    # scaling: service-level block the API echoes back empty (scaling lives in template).
    ignore_changes = [template[0].containers[0].image, client, client_version, scaling]
  }

  depends_on = [google_project_service.apis, google_compute_subnetwork_iam_member.network_user]
}

# vae-<env>-migrate runs on every deploy. vae-<env>-manage runs any management
# command on demand, with args given at execution, e.g.:
#   gcloud run jobs execute vae-stage-manage --region=us-west1 --args=manage.py,check,--deploy
resource "google_cloud_run_v2_job" "jobs" {
  for_each = {
    migrate = ["python", "manage.py", "migrate", "--no-input"]
    manage  = ["python", "manage.py", "showmigrations"]
  }
  project             = var.project_id
  name                = "${local.name}-${each.key}"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.app.email
      max_retries     = 0
      timeout         = "1200s"

      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = local.network_id
          subnetwork = local.subnet_id
        }
      }

      containers {
        image   = local.placeholder_image
        command = [each.value[0]]
        args    = slice(each.value, 1, length(each.value))
        resources {
          limits = { cpu = "1", memory = "512Mi" }
        }
        dynamic "env" {
          for_each = local.container_env
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_project_service.apis, google_compute_subnetwork_iam_member.network_user]
}

# --- CI/CD ------------------------------------------------------------------

# Needs the Cloud Build GitHub App installed on the repo and the repo connected
# to this project (one-time, by hand; infra/BOOTSTRAP.md).
resource "google_cloudbuild_trigger" "deploy" {
  project         = var.project_id
  location        = "global"
  name            = "${local.name}-deploy"
  description     = "Push to ${var.deploy_branch}: build, migrate and deploy ${var.env}"
  filename        = "infra/cloudbuild/deploy.yaml"
  service_account = google_service_account.deploy.id
  ignored_files   = ["infra/terraform/**", "**/*.md"]

  github {
    owner = var.github_owner
    name  = var.github_repo
    push {
      branch = "^${var.deploy_branch}$"
    }
  }

  substitutions = {
    _ENV       = var.env
    _REGION    = var.region
    _IMAGE     = var.image_repo
    _START_SQL = var.sql_always_on ? "false" : "true"
  }

  depends_on = [google_project_service.apis]
}
