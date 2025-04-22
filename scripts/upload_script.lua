-- scripts/upload_script.lua
-- Lua script for wrk to generate multipart/form-data POST requests.
-- Reads 'sample.jpg' from the current directory on the client VM.
-- Includes done() function to print latency percentiles for PKB parsing.

local file_path = "sample.jpg" -- Relative path on the client VM
local file_content
local file = io.open(file_path, "rb")
if not file then
  -- Try alternative path if PKB places data differently
  file = io.open("./" .. file_path, "rb")
end

if not file then
  print("Error: Could not open file: " .. file_path .. " in current dir or ./")
  -- Return a basic GET request or error indicator if file is missing
  -- This prevents the entire wrk run from failing immediately
  return wrk.format("GET", "/error-file-not-found")
else
  file_content = file:read("*a")
  file:close()
  -- Avoid printing this in the final version unless debugging, it can clutter stdout
  -- print("Successfully read " .. #file_content .. " bytes from " .. file_path)
end

-- Generate a unique boundary for each request (good practice)
local function generate_boundary()
    -- Using math.random for potentially better uniqueness across quick runs
    return "---------------------------" .. string.format("%x", os.time()) .. string.format("%x", math.random(0, 0xFFFFFFFF))
end

request = function()
  local boundary = generate_boundary()
  local body = {}

  table.insert(body, "--" .. boundary .. "\r\n")
  table.insert(body, "Content-Disposition: form-data; name=\"file\"; filename=\"" .. file_path .. "\"\r\n")
  table.insert(body, "Content-Type: image/jpeg\r\n\r\n") -- Assume JPEG for the sample
  table.insert(body, file_content .. "\r\n")
  table.insert(body, "--" .. boundary .. "--\r\n")
  body = table.concat(body)

  wrk.headers["Content-Type"] = "multipart/form-data; boundary=" .. boundary
  -- wrk usually handles Content-Length correctly for POST bodies generated this way

  -- Path is usually part of the URL passed to wrk command line,
  -- so the path argument here is often nil or just "/".
  -- If your URL already includes /upload, use nil or "/".
  return wrk.format("POST", nil, nil, body)
end

-- Optional: Log response status if needed for debugging specific errors
-- response = function(status, headers, body)
--   if status ~= 200 and status ~= 201 and status ~= 204 then -- Add expected success codes
--     print(string.format("Non-Success Response: %d", status))
--     -- You could potentially print parts of the body or headers for debugging
--     -- print("Headers:", serpent.block(headers)) -- Requires serpent library installed on VM
--     -- print("Body:", body)
--   end
-- end

-- **** NEW PART: done() function ****
-- This function executes *after* the benchmark finishes.
-- wrk passes summary, latency, and requests objects.
done = function(summary, latency, requests)
  -- The 'latency' object contains the distribution. Use :percentile(N)
  -- Latency values from wrk are typically in microseconds.

  -- Convert microseconds to milliseconds for easier reading
  local p50_ms = latency:percentile(50.0) / 1000.0
  local p90_ms = latency:percentile(90.0) / 1000.0 -- Added p90
  local p95_ms = latency:percentile(95.0) / 1000.0
  local p99_ms = latency:percentile(99.0) / 1000.0
  local p999_ms = latency:percentile(99.9) / 1000.0 -- Added p99.9

  -- Print these values in a unique format for the PKB Python script to parse
  -- Using "PKB_METRIC_" prefix makes them easy to find in stdout
  print(string.format("PKB_METRIC_Latency_p50: %.3f ms", p50_ms))
  print(string.format("PKB_METRIC_Latency_p90: %.3f ms", p90_ms))
  print(string.format("PKB_METRIC_Latency_p95: %.3f ms", p95_ms))
  print(string.format("PKB_METRIC_Latency_p99: %.3f ms", p99_ms))
  print(string.format("PKB_METRIC_Latency_p999: %.3f ms", p999_ms))

  -- You can also print other stats from the summary or latency objects if needed
  -- print(string.format("PKB_METRIC_Latency_Avg: %.3f ms", latency.mean / 1000.0))
  -- print(string.format("PKB_METRIC_Latency_Stdev: %.3f ms", latency.stdev / 1000.0))
  -- print(string.format("PKB_METRIC_Latency_Max: %.3f ms", latency.max / 1000.0))
  -- print(string.format("PKB_METRIC_Completed_Requests_Check: %d", summary.requests))
  -- print(string.format("PKB_METRIC_Total_Errors: %d", summary.errors.connect + summary.errors.read + summary.errors.write + summary.errors.timeout + summary.errors.status))

end 