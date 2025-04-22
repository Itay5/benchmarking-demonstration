variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for deployment"
  type        = string
  default     = "us-central1"
}

variable "image_uri" {
  description = "Full URI of the container image in Artifact Registry"
  type        = string
}

variable "run_id" {
  description = "Unique ID for this benchmark run, used for naming and tagging"
  type        = string
  default     = "default-benchmark-run"
}

# --- Cloud Run Configuration Variables ---

variable "memory_mb" {
  description = "Memory allocated to Cloud Run instance (MiB)"
  type        = number
  default     = 512
}

variable "cpu_cores" {
  description = "CPU cores allocated (1, 2, 4, etc.)"
  type        = number
  default     = 1
}

variable "concurrency_limit" {
  description = "Max concurrent requests per Cloud Run instance"
  type        = number
  default     = 80
}

variable "min_instances" {
  description = "Minimum number of Cloud Run instances to keep warm"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances for autoscaling"
  type        = number
  default     = 10
}

variable "service_account_email" {
  description = "Email of the service account for Cloud Run"
  type        = string
  default     = "" # Optional: derive or create dynamically if preferred
} 