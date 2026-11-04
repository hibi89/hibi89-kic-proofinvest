# KUODRA: local-only Docker browser demo

Run `bash scripts/run_local_demo.sh` on a machine with Docker Engine, Bash and Python 3 (Linux / macOS or Bash-compatible Docker CLI).
Default browser URL: `http://127.0.0.1:18501`. Set `KUODRA_LOCAL_PORT=18501` to choose another port. The script runs until Ctrl+C, then cleans its own temporary Docker network/container.

This **does not** deploy to a cloud or create an externally reachable service. It builds the image from explicit checked-in source/public fixtures only, with no private PDF, original SEC/NDX data, secret, mounted host directory, or account change.

The container uses an internal Docker bridge without Internet route, a host-only Python TCP relay bound to 127.0.0.1 with no Docker published port, nonroot UID 10001, read-only filesystem, no Linux capabilities, no-new-privileges, resource limits, and temporary scratch. The UI uses synthetic/local upload modes; live SEC or paid vendor data is not available. Browser uploads are user-initiated; never put confidential data in the public repository.

CI runs `bash scripts/docker_loopback_smoke.sh` after the P175 fully network-disconnected container smoke test. It checks actual host-to-container local HTTP, Docker internal network, localhost bind and nonroot/read-only settings, then removes test resources. This is **not** Production, real SEC origin authentication, source-data licensing, human approval of KIC submission or a DAKER receipt. RELEASE HOLD.
