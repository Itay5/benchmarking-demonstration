# Copyright 2025 PerfKitBenchmarker Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Basic benchmark to run wrk against a target URL."""

import logging
import re
from absl import flags
from perfkitbenchmarker import benchmark_spec as bm_spec
from perfkitbenchmarker import configs
from perfkitbenchmarker import sample
from perfkitbenchmarker.linux_packages import wrk


# Define flags specific to this custom benchmark using PKB's flag system
# These names match the keys expected under the 'wrk:' section in the YAML
flags.DEFINE_string('wrk_target_url', None, 'URL to benchmark.')
flags.DEFINE_integer('wrk_num_threads', 1, 'Number of wrk threads.')
flags.DEFINE_integer('wrk_num_conns', 1, 'Number of wrk connections.')
flags.DEFINE_integer('wrk_duration', 60, 'Duration of wrk test in seconds.')
flags.DEFINE_string('wrk_script_local_path', None,
                    'Path to the Lua script on the controller.')
flags.DEFINE_string('wrk_script_remote_path', 'request.lua',
                    'Path for the Lua script on the client VM.')
flags.DEFINE_list('wrk_script_data_files', [],
                  'Data files needed by the Lua script, relative to PKB root.')
flags.DEFINE_string('wrk_flags', '', 'Additional flags for wrk.')


FLAGS = flags.FLAGS

BENCHMARK_NAME = 'wrk' # This is how PKB identifies our benchmark
BENCHMARK_CONFIG = """
wrk:
  description: Runs wrk against a specified URL.
  vm_groups:
    default:
      os_type: ubuntu2004 # Or your preferred client OS
      vm_spec:
        GCP:
          machine_type: e2-standard-2
"""

def GetConfig(user_config):
  return configs.LoadConfig(BENCHMARK_CONFIG, user_config, BENCHMARK_NAME)

def Prepare(benchmark_spec: bm_spec.BenchmarkSpec):
  """Install wrk tool on the client VM."""
  vm = benchmark_spec.vm_groups['default'][0]
  vm.Install('wrk') # Uses the wrk package definition in PKB

  # Copy the Lua script and any data files if specified in config/flags
  if FLAGS.wrk_script_local_path:
    script_local_path = FLAGS.wrk_script_local_path
    script_remote_path = FLAGS.wrk_script_remote_path
    vm.PushFile(script_local_path, script_remote_path)
    logging.info('Copied wrk Lua script %s to %s on VM',
                 script_local_path, script_remote_path)

  if FLAGS.wrk_script_data_files:
    for data_file in FLAGS.wrk_script_data_files:
      # Assuming data files are relative to PKB root or a known path
      # PKB usually handles data file copying via vm.InstallData()
      # or direct PushFile if path is known. Let's assume PushFile for simplicity.
      # Note: This might need adjustment based on where data files reside.
      try:
          vm.PushFile(data_file, data_file) # Copy to same relative path on VM
          logging.info('Copied wrk data file %s to VM', data_file)
      except Exception as e:
          logging.error('Failed to copy data file %s: %s', data_file, e, exc_info=True)
          # Decide if this is fatal or not


def Run(benchmark_spec: bm_spec.BenchmarkSpec):
  """Run wrk against the target URL and collect results."""
  vm = benchmark_spec.vm_groups['default'][0]
  results = []

  # Build the wrk command using flags defined for this benchmark
  # These flags are populated from the benchmark config YAML or command line overrides
  target_url = FLAGS.wrk_target_url
  if not target_url:
    raise ValueError('wrk_target_url must be specified.')

  cmd = [
      wrk.WRK_PATH,  # Use the path directly, it already points to the executable
      f'--connections={FLAGS.wrk_num_conns}',
      f'--threads={FLAGS.wrk_num_threads}',
      f'--duration={FLAGS.wrk_duration}s' # Add 's' suffix for wrk
  ]
  if FLAGS.wrk_script_local_path:
      cmd.append(f'--script={FLAGS.wrk_script_remote_path}')
  if FLAGS.wrk_flags:
      cmd.append(FLAGS.wrk_flags)

  cmd.append(target_url) # URL is the last argument for wrk

  logging.info('Running wrk command: %s', ' '.join(cmd))
  stdout, stderr, retcode = vm.RemoteCommandWithReturnCode(' '.join(cmd), ignore_failure=False)

  logging.info('wrk command finished with return code %d', retcode)
  logging.info('wrk stdout:\n%s', stdout)
  logging.info('wrk stderr:\n%s', stderr)

  # Check return code BEFORE parsing
  if retcode != 0:
      logging.error('wrk command failed with return code %d', retcode)
      # Return empty results on failure
      return []

  # Parse wrk output (this is a basic example, needs more robust parsing)
  metadata = {
      'wrk_threads': FLAGS.wrk_num_threads,
      'wrk_connections': FLAGS.wrk_num_conns,
      'wrk_duration': FLAGS.wrk_duration,
      'wrk_target_url': target_url,
      'wrk_script': FLAGS.wrk_script_remote_path if FLAGS.wrk_script_local_path else 'None',
      'command_return_code': retcode,
      'wrk_custom_flags': FLAGS.wrk_flags or 'None'
  }

  def parse_and_add_sample(metric_name, regex_pattern, unit, results_list, metadata_dict, stdout_text):
    match = re.search(regex_pattern, stdout_text)
    if match:
      try:
        value = float(match.group(1))
        results_list.append(sample.Sample(metric_name, value, unit, metadata_dict))
        logging.info(f"Parsed {metric_name}: {value} {unit}")
      except (ValueError, IndexError):
        logging.warning(f"Could not parse value for {metric_name} from match: {match.group(0)}")
    else:
        logging.warning(f"Could not find metric '{metric_name}' in wrk output.")


  # Parse the metrics printed by the Lua done() function
  parse_and_add_sample('Latency p50', r'PKB_METRIC_Latency_p50:\s+([\d.]+)\s+ms', 'ms', results, metadata, stdout)
  parse_and_add_sample('Latency p90', r'PKB_METRIC_Latency_p90:\s+([\d.]+)\s+ms', 'ms', results, metadata, stdout)
  parse_and_add_sample('Latency p95', r'PKB_METRIC_Latency_p95:\s+([\d.]+)\s+ms', 'ms', results, metadata, stdout)
  parse_and_add_sample('Latency p99', r'PKB_METRIC_Latency_p99:\s+([\d.]+)\s+ms', 'ms', results, metadata, stdout)
  parse_and_add_sample('Latency p99.9', r'PKB_METRIC_Latency_p999:\s+([\d.]+)\s+ms', 'ms', results, metadata, stdout)

  # You might want to keep the overall RPS and Error count from wrk's default output too
  # Adjust the regex based on wrk's standard output format
  rps_match = re.search(r'Requests/sec:\s+([\d.]+)', stdout)
  if rps_match:
      results.append(sample.Sample('Requests Per Second', float(rps_match.group(1)), 'req/s', metadata))

  errors_match = re.search(r'Socket errors: connect (\d+), read (\d+), write (\d+), timeout (\d+)', stdout)
  status_errors_match = re.search(r'Non-2xx or 3xx responses:\s+(\d+)', stdout) # Example for status errors
  total_errors = 0
  if errors_match:
      total_errors += sum(int(count) for count in errors_match.groups())
  if status_errors_match:
      total_errors += int(status_errors_match.group(1))
  # Add a consolidated error sample
  results.append(sample.Sample('Total Errors', total_errors, 'count', metadata))

  # Add completed requests if needed
  requests_match = re.search(r'(\d+)\s+requests in', stdout)
  if requests_match:
      results.append(sample.Sample('Completed Requests', int(requests_match.group(1)), 'requests', metadata))

  return results # Return the list containing all parsed samples


def Cleanup(benchmark_spec: bm_spec.BenchmarkSpec):
  """Cleanup wrk on the VMs."""
  # PKB handles VM deletion. Cleanup usually involves removing installed packages
  # if necessary, but often left to VM teardown.
  pass 