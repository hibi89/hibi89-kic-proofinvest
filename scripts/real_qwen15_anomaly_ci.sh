#!/usr/bin/env bash
# P234 Stop & Pivot: after two wrong 0.5B anomaly responses, use a stronger
# genuinely DIFFERENT 1.5B model; do not replay the failed 0.5B approach.
# Only three PUBLIC derived percentages, two locally gated requests, no user data.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -B -m unittest tests.test_apple_qwen_anomaly_screen -v
container="kuodra-p234-qwen15-$$"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
image="ollama/ollama:0.12.10@sha256:e8c3d1f6ad16323bc40dc63eff0701d4fc32113f75a86b54b3e836eef8290de6"
docker run --detach --name "$container" \
  --publish 127.0.0.1:11435:11434 \
  --memory 5g --cpus 2 --pids-limit 256 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /root/.ollama:rw,nosuid,nodev,size=1700m \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  --env OLLAMA_HOST=0.0.0.0:11434 \
  --env OLLAMA_NUM_PARALLEL=1 \
  --env OLLAMA_MAX_LOADED_MODELS=1 \
  "$image" serve >/dev/null
for attempt in $(seq 1 60); do
  if python3 -B -c '
import urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open("http://127.0.0.1:11435/api/version",timeout=1.5) as r:
    assert r.status==200
' >/dev/null 2>&1; then break; fi
  if [ "$attempt" -eq 60 ]; then echo P234_OLLAMA_NOT_READY >&2; exit 1; fi
  sleep 1
done
# Public Ollama registry 1.5B Instruct ~986MB Apache-2.0.
docker exec "$container" ollama pull qwen2.5:1.5b-instruct
docker exec "$container" ollama list | grep -E "qwen2.5:1.5b-instruct[[:space:]]+65ec06548149" >/dev/null || {
  echo P234_WRONG_OFFICIAL_MODEL_DIGEST >&2; exit 1;
}
python3 -B -m scripts.real_qwen_anomaly_ci_smoke
