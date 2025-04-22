# GCP Cloud Run Performance and Cost Benchmarking Framework

## Overview

This project provides an automated framework for deploying, benchmarking, and estimating the cost of a sample web application running on Google Cloud Run behind a Global HTTP(S) Load Balancer. It leverages Terraform for infrastructure provisioning, PerfKitBenchmarker (PKB) with a custom `wrk` benchmark for performance testing, and Infracost for cost estimation. The entire process is orchestrated using a GitHub Actions workflow, allowing for easy comparison of different Cloud Run configurations.

## Features

*   **Automated Infrastructure:** Uses Terraform (`infra/`) to define and deploy GCP resources (Cloud Run, Load Balancer, etc.).
*   **Performance Benchmarking:** Employs PerfKitBenchmarker (`pkb/`, `pkb_extensions/`) with a custom `wrk` benchmark (`scripts/upload_script.lua`) to measure application performance (e.g., requests per second, latency) under load.
*   **Cost Estimation:** Integrates Infracost to provide:
    *   Initial cost estimates based on Terraform configuration.
    *   Usage-based cost estimates derived from PKB benchmark results (`scripts/generate_infracost_usage.py`).
*   **Configurable Benchmarks:** Allows easy testing of different Cloud Run parameters (Memory, CPU, Concurrency, Min/Max Instances) via GitHub Actions inputs.
*   **CI/CD Integration:** Uses a GitHub Actions workflow (`.github/workflows/`) to automate the entire deploy-benchmark-destroy lifecycle.
*   **Reporting:** Generates a summary JSON report (`scripts/generate_summary_report.py`) combining key performance metrics and cost estimates.
*   **Sample Application:** Includes a basic Python Flask application (`app/`) for demonstration purposes.

## Architecture

1.  **GitHub Actions Workflow:** Triggered manually with specified Cloud Run parameters.
2.  **Terraform Apply:** Deploys the Cloud Run service, Load Balancer, and supporting infrastructure based on files in `infra/` and workflow inputs.
3.  **Infracost (Initial):** Estimates costs based on the deployed infrastructure configuration.
4.  **PerfKitBenchmarker:**
    *   Clones PKB.
    *   Installs a custom `wrk` benchmark module from `pkb_extensions/`.
    *   Uses a configuration template (`pkb/configs/`) populated with the Load Balancer IP.
    *   Runs `wrk` (using `scripts/upload_script.lua`) against the application endpoint.
5.  **Infracost (Usage-based):**
    *   A script (`scripts/generate_infracost_usage.py`) processes PKB results to create an Infracost usage file (`infracost_usage.yml`).
    *   Infracost re-runs using the usage file to provide a more accurate cost estimate based on observed traffic.
6.  **Summary Report:** A script (`scripts/generate_summary_report.py`) combines PKB metrics and the final Infracost data into `summary_report.json`.
7.  **Artifact Upload:** Uploads PKB results, Infracost estimates, and the summary report as workflow artifacts.
8.  **Terraform Destroy:** Cleans up all deployed GCP resources.

## Prerequisites

*   **Google Cloud Project:** A GCP project with billing enabled.
*   **APIs Enabled:** Ensure the following APIs are enabled in your GCP project:
    *   Cloud Run API
    *   Compute Engine API
    *   Artifact Registry API
    *   Cloud Resource Manager API
    *   IAM API
    *   Cloud Billing API (for cost estimation features)
*   **Docker Image:** A container image for the application pushed to Artifact Registry (or another accessible registry). The default workflow assumes `us-central1-docker.pkg.dev/${GCP_PROJECT_ID}/demo-repo/demo-api`. You might need to build and push the image from the `app/` directory first.
*   **GitHub Secrets:** Configure the following secrets in your GitHub repository settings:
    *   `GCP_PROJECT_ID`: Your Google Cloud Project ID.
    *   `GCP_SA_KEY`: A JSON service account key with necessary permissions (e.g., Cloud Run Admin, Compute Admin, Storage Admin, Service Account User, Artifact Registry Writer). *Note: Using Workload Identity Federation is recommended over service account keys.*
    *   `INFRACOST_API_KEY`: Your Infracost API key (obtainable from [Infracost Cloud](https://www.infracost.io/docs/cloud_beta/)).

## Usage

1.  **Navigate** to the "Actions" tab of your GitHub repository.
2.  **Select** the "GCP Cloud Run Demo Benchmark" workflow.
3.  **Click** "Run workflow".
4.  **Fill in** the desired parameters for the benchmark run:
    *   Cloud Run Memory (MB)
    *   Cloud Run Concurrency Limit
    *   Cloud Run CPU Cores
    *   Cloud Run Min Instances (0 for cold start tests)
    *   Cloud Run Max Instances
    *   Docker Image Tag (e.g., `latest` or a specific Git SHA)
5.  **Click** "Run workflow".

The workflow will execute the steps outlined in the Architecture section.

## Outputs

Upon completion, the workflow provides the following artifacts for download:

*   `infracost-estimate-[run_id].zip`: Contains `infracost_estimate.json` (initial cost estimate).
*   `pkb-results-[run_id].zip`: Contains `pkb_results.json` (raw results from PerfKitBenchmarker).
*   `infracost-estimate-with-usage-[run_id].zip`: Contains `infracost_estimate_with_usage.json` (cost estimate including usage data).
*   `summary-report-json-[run_id].zip`: Contains `summary_report.json` (a consolidated view of key performance metrics and final costs).

## Customization

*   **Application:** Modify the code in the `app/` directory and rebuild/push the Docker image.
*   **Infrastructure:** Adjust the Terraform configuration in `infra/`. Remember to update relevant variables and potentially the Infracost usage generation script if resources change significantly.
*   **Benchmark:**
    *   Modify the `wrk` Lua script (`scripts/upload_script.lua`).
    *   Adjust the PKB configuration template (`pkb/configs/`).
    *   Enhance or change the custom PKB benchmark module (`pkb_extensions/`).
*   **Workflow:** Edit `.github/workflows/gcp-serverless-demo-benchmark.yml` to change steps, tools, or logic.
