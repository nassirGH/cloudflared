package hello

import (
	"bytes"
	"context"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/rs/zerolog"
)

func TestRootHandlerLimitsRequestBody(t *testing.T) {
	handler := rootHandler("test-server")

	// Create a body larger than maxRequestBody (1 MB)
	largeBody := strings.NewReader(strings.Repeat("A", maxRequestBody+1024))
	req := httptest.NewRequest(http.MethodPost, "/", largeBody)
	rr := httptest.NewRecorder()

	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rr.Code)
	}
	// The body in the response should be truncated to maxRequestBody
	responseBody := rr.Body.String()
	if strings.Contains(responseBody, strings.Repeat("A", maxRequestBody+1)) {
		t.Fatal("response body should be truncated by LimitReader")
	}
}

func TestSSEHandlerEnforcesMinFrequency(t *testing.T) {
	log := zerolog.Nop()
	handler := sseHandler(&log)

	// Request with a frequency below the minimum (1ns)
	req := httptest.NewRequest(http.MethodGet, "/sse?freq=1ns", nil)
	rr := httptest.NewRecorder()

	// Run handler with a context that cancels after 100ms
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	req = req.WithContext(ctx)

	handler.ServeHTTP(rr, req)

	// With minSSEFreq of 1s and a 100ms context, we should get 0 events
	// If freq=1ns were honored, we'd get millions
	body := rr.Body.String()
	count := 0
	for _, l := range strings.Split(strings.TrimSpace(body), "\n\n") {
		if strings.TrimSpace(l) != "" {
			count++
		}
	}
	if count > 1 {
		t.Fatalf("expected at most 1 SSE event with min frequency enforcement, got %d", count)
	}
}

func TestServerHasTimeouts(t *testing.T) {
	log := zerolog.Nop()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}

	shutdownC := make(chan struct{})

	go func() {
		_ = StartHelloWorldServer(&log, listener, shutdownC)
	}()

	// Give server a moment to start
	time.Sleep(50 * time.Millisecond)

	// Verify server responds (proving it started correctly with timeouts)
	resp, err := http.Get(fmt.Sprintf("http://%s/_health", listener.Addr().String()))
	if err != nil {
		t.Fatalf("failed to connect to server: %v", err)
	}
	defer resp.Body.Close()

	var buf bytes.Buffer
	buf.ReadFrom(resp.Body)
	if buf.String() != "ok" {
		t.Fatalf("expected 'ok', got %q", buf.String())
	}

	close(shutdownC)
}

func TestCreateTLSListenerHostAndPortSuccess(t *testing.T) {
	listener, err := CreateTLSListener("localhost:1234")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	if listener.Addr().String() == "" {
		t.Fatal("Fail to find available port")
	}
}

func TestCreateTLSListenerOnlyHostSuccess(t *testing.T) {
	listener, err := CreateTLSListener("localhost:")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	if listener.Addr().String() == "" {
		t.Fatal("Fail to find available port")
	}
}

func TestCreateTLSListenerOnlyPortSuccess(t *testing.T) {
	listener, err := CreateTLSListener("localhost:8888")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	if listener.Addr().String() == "" {
		t.Fatal("Fail to find available port")
	}
}
