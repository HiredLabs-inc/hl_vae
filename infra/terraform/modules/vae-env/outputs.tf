output "app_service_account" {
  value = google_service_account.app.email
}

output "deploy_service_account" {
  value = google_service_account.deploy.email
}

output "web_service_name" {
  value = google_cloud_run_v2_service.web.name
}

# CLOUDRUN_SERVICE_URL in the app secret.
output "web_url" {
  value = google_cloud_run_v2_service.web.uri
}

output "sql_instance" {
  value = google_sql_database_instance.db.name
}

# GCP_CLOUDSQL_PRIVATE_IP in the app secret.
output "sql_private_ip" {
  value = google_sql_database_instance.db.private_ip_address
}

output "secret_name" {
  value = google_secret_manager_secret.app_env.secret_id
}

output "deploy_trigger" {
  value = google_cloudbuild_trigger.deploy.name
}
