"""Loopback-only TCP relay for KUODRA internal-network Docker demo.

Only connects the local browser to a private Docker bridge address, never a
remote API. No HTTP reinterpretation; forwards WebSocket bytes unchanged.
"""
from __future__ import annotations

import argparse
import ipaddress
import select
import socket
import socketserver


class _Relay(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        host, port = self.server.target
        try:
            with socket.create_connection((host, port), timeout=5) as target:
                sockets = (self.request, target)
                while True:
                    readable, _, _ = select.select(sockets, (), (), 180)
                    if not readable:
                        return
                    for src in readable:
                        data = src.recv(65536)
                        if not data:
                            return
                        (target if src is self.request else self.request).sendall(data)
        except (ConnectionError, TimeoutError, OSError):
            return


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 16


def serve(container_ip: str, local_port: int) -> None:
    try:
        ip = ipaddress.ip_address(container_ip)
    except ValueError as exc:
        raise ValueError("KUODRA_INVALID_INTERNAL_IP") from exc
    if (ip.version != 4 or not ip.is_private or ip.is_loopback
            or ip.is_link_local or ip.is_multicast or ip.is_unspecified):
        raise ValueError("KUODRA_INVALID_INTERNAL_IP")
    if type(local_port) is not int or not 1024 <= local_port <= 65535:
        raise ValueError("KUODRA_INVALID_LOCAL_PORT")
    with _Server(("127.0.0.1", local_port), _Relay) as server:
        server.target = (str(ip), 8501)
        print(f"KUODRA_LOCAL_ONLY http://127.0.0.1:{local_port}", flush=True)
        server.serve_forever(poll_interval=0.25)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Internal Docker to localhost TCP relay")
    parser.add_argument("--container-ip", required=True)
    parser.add_argument("--listen-port", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        serve(args.container_ip, args.listen_port)
    except (OSError, ValueError) as exc:
        print(str(exc))
        return 2
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
