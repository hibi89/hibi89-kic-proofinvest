#!/usr/bin/env bash
# User-invoked LOCAL demo; never binds a public interface.
set -euo pipefail
port="${KUODRA_LOCAL_PORT:-18501}"
if [[ ! "$port" =~ ^[0-9]{4,5}$ ]] || (( 10#$port < 1024 || 10#$port > 65535 )); then
  echo "KUODRA_INVALID_LOCAL_PORT (1024..65535)" >&2
  exit 2
fi
if ! command -v docker >/dev/null; then
  echo "KUODRA_DOCKER_NOT_FOUND" >&2
  exit 2
fi
cd "$(dirname "$0")/.."
image="kuodra-offline-local:p176"
suffix="$$"
network="kuodra-offline-$suffix"
container="kuodra-ui-$suffix"
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
# Internal Docker network has no Internet routing. Only host loopback is
# published; the container has no host file mounts.
docker build --pull=false -t "$image" .
docker network create --internal "$network" >/dev/null
echo "KUODRA_LOCAL_ONLY http://127.0.0.1:$port"
docker run --rm --name "$container" \
  --network "$network" --publish "127.0.0.1:$port:8501" \
  --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 96 --memory 768m --cpus 1 --user 10001:10001 \
  "$image" python -B -m streamlit run streamlit_app.py \
  --server.address=0.0.0.0 --server.port=8501 --server.headless=true \
  --server.enableCORS=true --server.enableXsrfProtection=true \
  --browser.gatherUsageStats=false
