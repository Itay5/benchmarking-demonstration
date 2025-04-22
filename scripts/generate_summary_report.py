#!/usr/bin/env python3
# scripts/generate_summary_report.py
# Generates a structured JSON summary report from PKB benchmark results and Infracost estimates

import json
import os
import math
import sys

# --- Configuration ---
# Use command-line args or default paths
pkb_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), 'pkb_results.json')
# *** Read from the new Infracost file (passed as 2nd arg) ***
infracost_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.getcwd(), 'infracost_estimate_with_usage.json')
output_file = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.getcwd(), 'summary_report.json')

# --- Helper Functions ---
def get_pkb_metric(samples, metric_name, default=None):
    """Finds the first sample matching the metric name and returns its value."""
    for sample in samples:
        if sample.get('metric') == metric_name:
            # Ensure value is serializable (primarily converting float('inf') if it occurs)
            val = sample.get('value', default)
            if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                 return None # Represent infinity/NaN as null in JSON
            return val
    return default

def get_pkb_label(samples, label_key, default=None):
    """Extracts a label value from the first sample that has labels."""
    for sample in samples:
         if 'labels' in sample and isinstance(sample['labels'], str):
             parts = sample['labels'].split('|')
             for part in parts:
                 if ':' in part:
                     try:
                         k, v = part.split(':', 1)
                         if k == label_key:
                             if v.startswith("['") and v.endswith("']"):
                                 v = v[2:-2]
                             return v
                     except ValueError:
                         continue
    return default

# --- Initialize Data Holders ---
pkb_samples = []
infracost_data = None
summary_data = {
    "run_id": os.getenv('RUN_ID', None),
    "architecture_configuration": {
        "cloud_run_memory_mb": os.getenv('TF_VAR_memory_mb', None),
        "cloud_run_cpu_cores": os.getenv('TF_VAR_cpu_cores', None),
        "cloud_run_concurrency_limit": os.getenv('TF_VAR_concurrency_limit', None),
        "cloud_run_min_instances": os.getenv('TF_VAR_min_instances', None),
        "cloud_run_max_instances": os.getenv('TF_VAR_max_instances', None),
        "cloud_run_image_tag": os.getenv('IMAGE_URI', 'N/A').split(':')[-1] if os.getenv('IMAGE_URI') else None, # Extract tag
        "pkb_client_vm_type": None # Will be extracted from PKB labels
    },
    "performance": {
        "latency_p50_ms": None,
        "latency_p95_ms": None,
        "latency_p99_ms": None,
        "throughput_rps": None,
        "cold_start_latency": None # Not measured by this setup
    },
    "scalability_elasticity": {
        "scale_out_time_sec": None, # Not measured by this setup
        "resource_utilization": None # Not measured by this setup
    },
    "reliability": {
        "error_rate_percent": None
    },
    "cost": {
        "total_estimated_monthly_usd": None,
        "total_estimated_hourly_usd": None,
        "estimated_cost_per_unit": None, # Still null, calculation complex
        "resource_cost_breakdown_monthly": None
    }
}

# --- Process PKB Results ---
try:
    with open(pkb_file, 'r') as f:
        for line in f:
            try:
                pkb_samples.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Warning: Skipping invalid JSON line in {pkb_file}: {line.strip()}")

    if pkb_samples:
        # Extract performance metrics
        summary_data["performance"]["latency_p50_ms"] = get_pkb_metric(pkb_samples, 'Latency p50')
        summary_data["performance"]["latency_p95_ms"] = get_pkb_metric(pkb_samples, 'Latency p95')
        summary_data["performance"]["latency_p99_ms"] = get_pkb_metric(pkb_samples, 'Latency p99')
        summary_data["performance"]["throughput_rps"] = get_pkb_metric(pkb_samples, 'Requests Per Second')

        # Extract client VM type
        summary_data["architecture_configuration"]["pkb_client_vm_type"] = get_pkb_label(pkb_samples, 'machine_type')

        # Calculate error rate
        errors = get_pkb_metric(pkb_samples, 'Total Errors', default=0.0)
        completed = get_pkb_metric(pkb_samples, 'Completed Requests', default=0.0)
        if isinstance(errors, (int, float)) and isinstance(completed, (int, float)):
            denominator = completed + errors
            if denominator > 0:
                error_rate_val = (errors / denominator) * 100
                summary_data["reliability"]["error_rate_percent"] = round(error_rate_val, 2)
            elif errors > 0:
                 summary_data["reliability"]["error_rate_percent"] = 100.00
            else:
                 summary_data["reliability"]["error_rate_percent"] = 0.00
    else:
        print(f"Warning: No valid PKB samples found in {pkb_file}. Performance data will be null.")

except FileNotFoundError:
    print(f"Error: PKB results file not found at {pkb_file}. Performance data will be null.")
except Exception as e:
    print(f"Error processing PKB results: {e}")


# --- Process Infracost Results (Reading the file with usage applied) ---
try:
    # Attempt to read the *new* infracost file passed as arg 2
    with open(infracost_file, 'r') as f:
        infracost_data = json.load(f)

    if infracost_data:
        # Extract TOTAL costs (these should now reflect usage)
        total_monthly = infracost_data.get('totalMonthlyCost')
        total_hourly = infracost_data.get('totalHourlyCost')
        try:
            summary_data["cost"]["total_estimated_monthly_usd"] = float(total_monthly) if total_monthly is not None else None
        except (ValueError, TypeError):
            print(f"Warning: Could not convert totalMonthlyCost '{total_monthly}' to float.")
            summary_data["cost"]["total_estimated_monthly_usd"] = None
        try:
            summary_data["cost"]["total_estimated_hourly_usd"] = float(total_hourly) if total_hourly is not None else None
        except (ValueError, TypeError):
            print(f"Warning: Could not convert totalHourlyCost '{total_hourly}' to float.")
            summary_data["cost"]["total_estimated_hourly_usd"] = None

        # Extract the breakdown (costs here should also reflect usage)
        cost_breakdown = []
        try:
            resources = infracost_data.get('projects', [{}])[0].get('breakdown', {}).get('resources', [])
            for res in resources:
                 monthly_cost_val = None
                 raw_monthly_cost = res.get('monthlyCost')
                 if raw_monthly_cost is not None:
                     try:
                         monthly_cost_val = float(raw_monthly_cost)
                     except (ValueError, TypeError):
                          print(f"Warning: Could not convert monthly cost '{raw_monthly_cost}' for resource '{res.get('name')}' to float.")

                 cost_breakdown.append({
                    "resource_name": res.get('name'),
                    "resource_type": res.get('resourceType'),
                    # Use "monthly_cost_usd" consistently
                    "monthly_cost_usd": monthly_cost_val
                })
            summary_data["cost"]["resource_cost_breakdown_monthly"] = cost_breakdown
        except (IndexError, AttributeError, TypeError, KeyError) as e:
            print(f"Warning: Could not parse Infracost resource breakdown: {e}")
            summary_data["cost"]["resource_cost_breakdown_monthly"] = None # Keep breakdown null if parsing fails
    else:
         print(f"Warning: Infracost data (with usage) is empty. Cost data will be null.")
         # Ensure total costs are also null if infracost_data is None/empty
         summary_data["cost"]["total_estimated_monthly_usd"] = None
         summary_data["cost"]["total_estimated_hourly_usd"] = None
         summary_data["cost"]["resource_cost_breakdown_monthly"] = None

except FileNotFoundError:
     # Handle case where the *second* infracost run might have failed
     print(f"Error: Infracost estimate file with usage not found at {infracost_file}. Cost data will use base estimate or be null.")
     # Optionally, you could fallback to reading the original infracost_estimate.json here
     # For simplicity, we'll just leave cost data as null if the usage-applied file isn't found.
     summary_data["cost"]["total_estimated_monthly_usd"] = None
     summary_data["cost"]["total_estimated_hourly_usd"] = None
     summary_data["cost"]["resource_cost_breakdown_monthly"] = None
except json.JSONDecodeError as e:
     print(f"Error: Could not parse Infracost JSON file with usage at {infracost_file}: {e}. Cost data will be null.")
     summary_data["cost"]["total_estimated_monthly_usd"] = None
     summary_data["cost"]["total_estimated_hourly_usd"] = None
     summary_data["cost"]["resource_cost_breakdown_monthly"] = None
except Exception as e:
     print(f"Error processing Infracost results with usage: {e}")
     summary_data["cost"]["total_estimated_monthly_usd"] = None
     summary_data["cost"]["total_estimated_hourly_usd"] = None
     summary_data["cost"]["resource_cost_breakdown_monthly"] = None

# --- Write JSON Report ---
try:
    with open(output_file, 'w') as f:
        json.dump(summary_data, f, indent=2) # Use indent for readability
    print(f"Successfully generated JSON summary report: {output_file}")
except IOError as e:
     print(f"Error writing JSON report file {output_file}: {e}")
except TypeError as e:
     print(f"Error serializing data to JSON: {e}. Data was: {summary_data}") 