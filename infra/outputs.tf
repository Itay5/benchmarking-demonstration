output "load_balancer_ip" {
  description = "Public IP address of the HTTP Load Balancer"
  value       = google_compute_global_forwarding_rule.fw_rule.ip_address
}

output "cloud_run_service_url" {
  description = "Direct URL of the Cloud Run service revision"
  value       = google_cloud_run_v2_service.image_saver_service.uri
}

output "cloud_run_service_name" {
  description = "Name of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.image_saver_service.name
}

output "bucket_name" {
  description = "Name of the GCS bucket created for images"
  value       = google_storage_bucket.images_bucket.name
}

output "service_account_email" {
  description = "Email of the service account used by Cloud Run"
  value       = google_service_account.run_sa.email
} 