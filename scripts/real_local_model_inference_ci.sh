#!/usr/bin/env bash
# One-time, explicitly tagged public CI proof of actual CPU-only local model.
# No secrets or owner originals. Downloaded model stays on disposable tmpfs.
set -euo pipefail
cd "$(dirname "$0")/.."
container="kuodra-p181-smollm2-real-$$"
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT
# Pinned to an Ollama official published release, not mutable :latest.
# This consumes only a public model (~105MB) and an official Docker image
# in a disposable GitHub Ubuntu runner; never send a customer payload.
image="ollama/ollama:0.12.10@sha256:e8c3d1f6ad16323bc40dc63eff0701d4fc32113f75a86b54b3e836eef8290de6"
docker run --detach --name "$container" \
  --publish 127.0.0.1:11435:11434 \
  --memory 3g --cpus 2 --pids-limit 256 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /root/.ollama:rw,nosuid,nodev,size=450m \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  --env OLLAMA_HOST=0.0.0.0:11434 \
  --env OLLAMA_NUM_PARALLEL=1 \
  --env OLLAMA_MAX_LOADED_MODELS=1 \
  "$image" serve >/dev/null
for attempt in $(seq 1 50); do
  if python3 -B -c '
import urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open("http://127.0.0.1:11435/api/version", timeout=1.5) as r:
    assert r.status == 200
' >/dev/null 2>&1; then break; fi
  if [ "$attempt" -eq 50 ]; then
    docker logs "$container" --tail 40 >&2
    echo P181_LOCAL_OLLAMA_NOT_READY >&2
    exit 1
  fi
  sleep 1
done
# Model only: no owner SEC/NDX/peer files, no credentials. Ollama official
# registry artifact tag 105 MB, Apache 2.0 per public published model page.
docker exec "$container" ollama pull smollm2:135m-instruct-q4_K_M
KUODRA_P181_PUBLIC_SYNTHETIC_ONLY=1 \
  python3 -B -m scripts.real_local_model_inference_smoke
