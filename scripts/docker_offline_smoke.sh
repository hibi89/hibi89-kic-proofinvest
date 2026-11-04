#!/usr/bin/env bash
# P175: isolated, zero-external-network demonstration; no user originals/trade.
set -euo pipefail
image="kuodra-local-offline-smoke:${GITHUB_SHA:-p175}"
name="kuodra-smoke-$$"
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker build --pull=false -t "$image" .
docker run --detach --name "$name" \
  --network none --read-only \
  --tmpfs /tmp:rw,nosuid,noexec,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 96 --memory 768m --cpus 1 \
  --user 10001:10001 "$image" >/dev/null
# The server is reachable only from inside the network-isolated container;
# no host port is published and no real SEC or vendor traffic can escape.
for attempt in $(seq 1 60); do
  if docker exec "$name" python -B -c '
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=2) as r:
    assert r.status == 200
' >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    docker logs --tail 50 "$name" >&2
    echo "KUODRA_ISOLATED_HEALTH_FAILED" >&2
    exit 1
  fi
  sleep 1
done
docker exec "$name" python -B -c '
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:8501", timeout=5) as r:
    body = r.read(256000).lower()
    assert r.status == 200 and b"streamlit" in body
'
docker exec "$name" python -B -c '
import json, subprocess, sys
p = subprocess.run(
    [sys.executable, "-B", "-m", "proofinvest", "--claim-revenue-growth-pct", "20"],
    capture_output=True, text=True, check=True, timeout=10
)
result = json.loads(p.stdout)
assert result["source_kind"] == "SYNTHETIC_FIXTURE"
assert result["status"] == "demo_not_real"
'
test "$(docker inspect --format '{{.HostConfig.NetworkMode}}' "$name")" = "none"
test "$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$name")" = "true"
test "$(docker inspect --format '{{.HostConfig.SecurityOpt}}' "$name")" = "[no-new-privileges]"
if [ -n "$(docker inspect --format '{{json .NetworkSettings.Ports}}' "$name" | grep -E '[1-9][0-9]*:' || true)" ]; then
  echo "KUODRA_UNEXPECTED_PORT_PUBLICATION" >&2
  exit 1
fi
echo 'KUODRA_P175_ISOLATED_CONTAINER_HTTP_SYNTHETIC_PASS'
