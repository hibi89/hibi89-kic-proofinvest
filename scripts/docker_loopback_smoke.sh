#!/usr/bin/env bash
# Host-side HTTP, container permissions and internal-only network acceptance.
set -euo pipefail
cd "$(dirname "$0")/.."
port="${KUODRA_LOCAL_SMOKE_PORT:-18521}"
if [[ ! "$port" =~ ^[0-9]{4,5}$ ]] || (( 10#$port < 1024 || 10#$port > 65535 )); then
  echo "KUODRA_BAD_SMOKE_PORT" >&2
  exit 2
fi
image="kuodra-loopback-smoke:${GITHUB_SHA:-p176}"
network="kuodra-loopback-$$"
name="kuodra-loopback-test-$$"
cleanup() {
  if [ -n "${relay_pid:-}" ]; then kill "$relay_pid" >/dev/null 2>&1 || true; fi
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  rm -f "/tmp/kuodra-p176-relay-$.log"
}
trap cleanup EXIT
docker build --pull=false -t "$image" .
docker network create --internal "$network" >/dev/null
docker run -d --name "$name" \
  --network "$network" \
  --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 96 --memory 768m --cpus 1 --user 10001:10001 \
  "$image" python -B -m streamlit run streamlit_app.py \
  --server.address=0.0.0.0 --server.port=8501 --server.headless=true \
  --server.enableCORS=true --server.enableXsrfProtection=true \
  --browser.gatherUsageStats=false >/dev/null
test "$(docker network inspect --format '{{.Internal}}' "$network")" = "true"
test "$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$name")" = "true"
test "$(docker inspect --format '{{.Config.User}}' "$name")" = "10001:10001"
test "$(docker inspect --format '{{.HostConfig.Privileged}}' "$name")" = "false"
test "$(docker inspect --format '{{json .NetworkSettings.Ports}}' "$name")" = '{"8501/tcp":null}'
test "$(docker inspect --format '{{.HostConfig.CapDrop}}' "$name")" = "[ALL]"
ip="$(docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$name")"
python3 -B -m scripts.local_loopback_relay --container-ip "$ip" --listen-port "$port" >/tmp/kuodra-p176-relay-$.log 2>&1 &
relay_pid=$!
for attempt in $(seq 1 45); do
  if KUODRA_PORT="$port" python -B -c '
import os, urllib.request
url = "http://127.0.0.1:" + os.environ["KUODRA_PORT"]
with urllib.request.urlopen(url + "/_stcore/health", timeout=3) as r:
    assert r.status == 200
with urllib.request.urlopen(url, timeout=3) as r:
    assert r.status == 200 and b"streamlit" in r.read(256000).lower()
' >/dev/null 2>&1; then
    echo "KUODRA_P176_HOST_LOOPBACK_STREAMLIT_ISOLATED_PASS"
    exit 0
  fi
  sleep 1
done
docker logs --tail 60 "$name" >&2
echo "KUODRA_P176_HOST_LOOPBACK_HTTP_FAILED" >&2
exit 1
