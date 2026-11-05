#!/usr/bin/env bash
# P233: distinct real Qwen model route, not a repeat of P191 SmolLM2 failures.
# Model download only; never upload owner inputs or financial original documents.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -B -m unittest tests.test_apple_qwen_public_claim -v
container="kuodra-p233-qwen-real-$$"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
image="ollama/ollama:0.12.10@sha256:e8c3d1f6ad16323bc40dc63eff0701d4fc32113f75a86b54b3e836eef8290de6"
docker run --detach --name "$container" \
  --publish 127.0.0.1:11435:11434 \
  --memory 3g --cpus 2 --pids-limit 256 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /root/.ollama:rw,nosuid,nodev,size=960m \
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
  if [ "$attempt" -eq 60 ]; then echo "P233_OLLAMA_NOT_READY" >&2; exit 1; fi
  sleep 1
done
docker exec "$container" ollama pull qwen2.5:0.5b-instruct
docker exec "$container" ollama list | grep -E "qwen2.5:0.5b-instruct[[:space:]]+a8b0c5157701" >/dev/null || {
  echo "P233_MODEL_DIGEST_DOES_NOT_MATCH_OFFICIAL_REGISTRY" >&2; exit 1;
}
python3 -B -m scripts.real_qwen_public_facts_ci_smoke
