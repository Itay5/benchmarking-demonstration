#!/usr/bin/env python3
# scripts/generate_infracost_usage.py
# Reads PKB results and generates an Infracost usage YAML file.

import json
import os
import yaml # Requires PyYAML
import sys
import math

# --- Configuration & Inputs ---
pkb_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), 'pkb_results.json')
usage_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.getcwd(), 'infracost_usage.yml')
sample_jpg_size_bytes = int(sys.argv[3]) if len(sys.argv) > 3 else 0

# Get config needed for calculation (provide defaults)
cpu_cores = float(os.getenv('TF_VAR_cpu_cores', '1.0'))
memory_mb = float(os.getenv('TF_VAR_memory_mb', '512.0'))
memory_gib = memory_mb / 1024.0

# --- Helper to extract PKB metric ---
def get_pkb_metric(samples, metric_name, default=0.0):
    for sample in samples:
        if sample.get('metric') == metric_name:
            val = sample.get('value')
            # Return default if value is None or not a number or NaN/Inf
            return val if isinstance(val, (int, float)) and not math.isnan(val) and not math.isinf(val) else default
    return default

# --- Load PKB Data ---
pkb_samples = []
try:
    with open(pkb_file, 'r') as f:
        for line in f:
            try:
                pkb_samples.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Warning: Skipping invalid JSON line in {pkb_file}: {line.strip()}")
except FileNotFoundError:
    print(f"Error: PKB file {pkb_file} not found. Cannot generate usage.")
    sys.exit(1) # Exit if PKB data is missing

if not pkb_samples:
    print(f"Error: No valid samples found in {pkb_file}. Cannot generate usage.")
    sys.exit(1)

# --- Extract Key Metrics from PKB ---
# Use Completed Requests as it represents successful operations
completed_requests = get_pkb_metric(pkb_samples, 'Completed Requests', default=0)
# Use p50 latency as a proxy for average request duration (in ms) - ACKNOWLEDGE LIMITATION
p50_latency_ms = get_pkb_metric(pkb_samples, 'Latency p50', default=0.0)
p50_latency_sec = p50_latency_ms / 1000.0 if p50_latency_ms > 0 else 0.0 # Avoid negative

# --- Estimate Usage Based on Test Run ---
# WARNING: Using p50 latency is a *very rough* proxy for server-side compute time.
# WARNING: Extrapolating short test to monthly usage is inaccurate for totals.
# We provide metrics Infracost *might* use based on common schemas.
# Check Infracost GCP provider docs for exact keys if this fails.

estimated_total_request_processing_seconds = completed_requests * p50_latency_sec
estimated_total_vcpu_seconds = estimated_total_request_processing_seconds * cpu_cores
estimated_total_gib_seconds = estimated_total_request_processing_seconds * memory_gib
total_data_processed_gb = (completed_requests * sample_jpg_size_bytes) / (1024**3) if sample_jpg_size_bytes > 0 else 0

# --- Define Usage Data ---
# Check Infracost docs for the definitive keys for your version!
# Resource names MUST match your Terraform resource addresses
# Adjust 'google_cloud_run_v2_service.image_saver_service', 
# 'google_storage_bucket.images_bucket', 'google_compute_global_forwarding_rule.fw_rule', 
# 'google_compute_target_http_proxy.http_proxy' if different in your infra/main.tf
usage_data = {
    "version": "0.1",
    "resource_usage": {
        "google_cloud_run_v2_service.image_saver_service": {
             # Provide *total* estimated compute seconds during the test period
             # Infracost might use these directly OR via requests/duration_ms
             "requests": completed_requests,
             "request_duration_ms": p50_latency_ms,
             # Also provide estimated totals if the schema prefers it
             # These keys might vary based on Infracost version/GCP provider specifics
             "vcpu_seconds": estimated_total_vcpu_seconds,
             "memory_gib_seconds": estimated_total_gib_seconds,
        },
        "google_storage_bucket.images_bucket": {
            "storage_gb": 0.1,
            "monthly_class_a_operations": completed_requests,
            "monthly_class_b_operations": 0,
        },
        "google_compute_global_forwarding_rule.fw_rule": {
             "ingress_data_gb": total_data_processed_gb
        },
        # ADDED usage key for proxy - check schema, 'data_processed_gb' is common
         "google_compute_target_http_proxy.http_proxy": {
             "data_processed_gb": total_data_processed_gb
         }
    }
}

# --- Write YAML Usage File ---
try:
    with open(usage_file, 'w') as f:
        yaml.dump(usage_data, f, sort_keys=False, default_flow_style=False)
    print(f"Successfully generated Infracost usage file: {usage_file}")
except Exception as e:
    print(f"Error writing usage file {usage_file}: {e}")
    sys.exit(1) 