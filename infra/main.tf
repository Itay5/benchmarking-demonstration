terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.27" # Use a recent 6.x version
    }
  }
  // required_version = ">= 1.7.0" # Provider 6.x needs >= 1.5.0, handled implicitly
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "project" {} # Get project details like number

# --- Service Account & IAM ---
resource "google_service_account" "run_sa" {
  # Use a predictable name if not passing email via variable
  account_id   = "cloudrun-sa-${substr(replace(var.run_id, "-", ""), 0, 10)}" # Keep it short
  display_name = "Cloud Run SA for Benchmark ${var.run_id}"
  project      = var.project_id
}

# Grants the Cloud Run SA permission only on the specific bucket
resource "google_storage_bucket_iam_member" "run_sa_bucket_access" {
  bucket = google_storage_bucket.images_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.run_sa.email}"
}

# Enable necessary APIs if not already enabled
resource "google_project_service" "apis" {
  project = var.project_id
  for_each = toset([
    "run.googleapis.com",
    "compute.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com", # Needed if using Cloud Build
    "logging.googleapis.com",
    "monitoring.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false # Keep APIs enabled after destroy
}

# --- GCS Bucket ---
resource "google_storage_bucket" "images_bucket" {
  project                     = var.project_id
  # Use a unique name based on run_id for isolation during tests
  name                        = "${var.project_id}-images-bucket-${substr(replace(var.run_id, "-", ""), 0, 10)}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true # Useful for cleanup during testing
  labels = {
    run_id = var.run_id
    benchmark = "image-saver"
  }
}

# --- Cloud Run Service ---
resource "google_cloud_run_v2_service" "image_saver_service" {
  project  = var.project_id
  name     = "image-saver-${substr(replace(var.run_id, "-", ""), 0, 10)}"
  location = var.region
  labels = {
    run_id    = var.run_id
    benchmark = "image-saver"
  }

  deletion_protection = false

  template {
    service_account = google_service_account.run_sa.email
    containers {
      image = var.image_uri
      ports { container_port = 8080 }
      env {
        name  = "BUCKET_NAME"
        value = google_storage_bucket.images_bucket.name
      }
      resources {
        limits = {
          "memory" = "${var.memory_mb}Mi"
          "cpu"    = var.cpu_cores
        }
        # Keep CPU allocated for the entire instance lifetime, not just during requests.
        # This changes the billing model for the instance's uptime.
        cpu_idle = true 
      }
    }
    scaling {
      # Keep at least 1 instance running 24/7
      min_instance_count = 1 # Or set higher based on var.min_instances if you want > 0 always
      max_instance_count = var.max_instances
    }
    max_instance_request_concurrency = var.concurrency_limit
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis,
    google_storage_bucket_iam_member.run_sa_bucket_access
  ]
}

# Allow unauthenticated access to the Cloud Run service *if* not using IAP/LB Auth
# Or allow access only from the Load Balancer's health check ranges and external IP sources.
# For simplicity in demo, allow allUsers - **NOT recommended for production**
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  project  = google_cloud_run_v2_service.image_saver_service.project
  location = google_cloud_run_v2_service.image_saver_service.location
  name     = google_cloud_run_v2_service.image_saver_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}


# --- Load Balancer (Serverless NEG) ---
resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  project               = var.project_id
  name                  = "neg-${substr(replace(var.run_id, "-", ""), 0, 10)}"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = google_cloud_run_v2_service.image_saver_service.name
    # Optional: Specify tag for specific revision, default is latest stable
  }
}

resource "google_compute_backend_service" "backend" {
  project               = var.project_id
  name                  = "backend-${substr(replace(var.run_id, "-", ""), 0, 10)}"
  protocol              = "HTTP" # Change to HTTPS if using HTTPS proxy
  port_name             = "http" # Default, ensure matches Cloud Run port if specified
  load_balancing_scheme = "EXTERNAL_MANAGED"
  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg.id
  }
  # Add health check if needed, though often omitted for Serverless NEG
  # enable_cdn = false # Set true if using Cloud CDN
}

resource "google_compute_url_map" "urlmap" {
  project         = var.project_id
  name            = "urlmap-${substr(replace(var.run_id, "-", ""), 0, 10)}"
  default_service = google_compute_backend_service.backend.id
}

# --- HTTP Proxy and Forwarding Rule (Change to HTTPS for production) ---
resource "google_compute_target_http_proxy" "http_proxy" {
  project = var.project_id
  name    = "http-proxy-${substr(replace(var.run_id, "-", ""), 0, 10)}"
  url_map = google_compute_url_map.urlmap.id
}

resource "google_compute_global_forwarding_rule" "fw_rule" {
  project               = var.project_id
  name                  = "fw-rule-${substr(replace(var.run_id, "-", ""), 0, 10)}"
  target                = google_compute_target_http_proxy.http_proxy.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
} 