variable "env" {
  description = "Environment name, e.g. stage. Used as the vae-<env>-* resource prefix."
  type        = string
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-west1"
}

# --- Shared VPC -------------------------------------------------------------

variable "host_project_id" {
  description = "Shared VPC host project."
  type        = string
}

variable "network" {
  description = "Shared VPC network name in the host project. Cloud SQL uses its existing private services access range."
  type        = string
}

variable "subnet" {
  description = "Subnet (in var.region) used for Cloud Run Direct VPC egress."
  type        = string
}

# --- Cloud Run --------------------------------------------------------------

variable "image_repo" {
  description = "Artifact Registry image path without a tag, e.g. us-west1-docker.pkg.dev/hl-vae-stage/vae-images/vae."
  type        = string
}

variable "artifact_repo" {
  description = "Artifact Registry repository the image lives in (output artifact_repo of shared/)."
  type = object({
    project  = string
    location = string
    name     = string
  })
}

variable "web_min_instances" {
  type    = number
  default = 0
}

variable "web_max_instances" {
  type    = number
  default = 3
}

variable "web_memory" {
  type    = string
  default = "512Mi"
}

# --- Cloud SQL --------------------------------------------------------------

variable "sql_tier" {
  type    = string
  default = "db-f1-micro"
}

variable "sql_disk_type" {
  description = "PD_SSD or PD_HDD. Can't be changed after creation."
  type        = string
}

variable "sql_always_on" {
  description = "false: deploys start the instance (so the deploy SA may); combine with sql_nightly_stop to keep it off when idle."
  type        = bool
}

variable "sql_nightly_stop" {
  description = "Cloud Scheduler job that stops the instance every night."
  type        = bool
  default     = false
}

variable "sql_retained_backups" {
  type = number
}

variable "sql_point_in_time_recovery" {
  type = bool
}

variable "deletion_protection" {
  type = bool
}

# --- Secrets ----------------------------------------------------------------

variable "secret_managers" {
  description = "Members (e.g. user:a@hiredlabs.org) who may read the app secret and add or disable its versions (DES-003). Project owners can do this anyway."
  type        = list(string)
  default     = []
}

# --- CI/CD ------------------------------------------------------------------

variable "github_owner" {
  type    = string
  default = "HiredLabs-inc"
}

variable "github_repo" {
  type    = string
  default = "hl_vae"
}

variable "deploy_branch" {
  description = "Pushes to this branch build and deploy this environment."
  type        = string
}
