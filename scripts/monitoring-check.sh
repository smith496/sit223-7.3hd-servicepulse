#!/usr/bin/env bash
set -euo pipefail

PROMETHEUS_URL="http://127.0.0.1:19090"
ALERTMANAGER_URL="http://127.0.0.1:19093"

for attempt in {1..20}; do
  if curl --fail --silent "${PROMETHEUS_URL}/-/ready" >/dev/null \
    && curl --fail --silent "${ALERTMANAGER_URL}/-/ready" >/dev/null; then
    break
  fi
  if [[ "${attempt}" == "20" ]]; then
    echo "Monitoring services did not become ready"
    exit 1
  fi
  sleep 2
done

curl --fail --silent --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=servicepulse_http_requests_total' > artifacts/prometheus-metric-query.json

docker stop servicepulse-prod >/dev/null
sleep 22

curl --fail --silent --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=ALERTS{alertname="ServicePulseDown",alertstate="firing"}' \
  > artifacts/prometheus-alert-query.json

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/prometheus-alert-query.json").read_text())
if not payload["data"]["result"]:
    raise SystemExit("ServicePulseDown did not enter the firing state")
print("Verified the ServicePulseDown alert in Prometheus")
PY

docker start servicepulse-prod >/dev/null
for attempt in {1..20}; do
  if curl --fail --silent http://127.0.0.1:18082/health >/dev/null; then
    break
  fi
  if [[ "${attempt}" == "20" ]]; then
    echo "Production did not recover after the alert test"
    exit 1
  fi
  sleep 1
done
