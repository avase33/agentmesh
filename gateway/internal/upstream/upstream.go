// Package upstream load-balances run requests across intelligence-layer workers
// and relays their SSE event stream back to the caller.
package upstream

import (
	"bufio"
	"bytes"
	"context"
	"net/http"
	"strings"
	"sync/atomic"
)

// Balancer picks intelligence workers round-robin.
type Balancer struct {
	urls []string
	idx  uint64
}

func NewBalancer(urls []string) *Balancer { return &Balancer{urls: urls} }

func (b *Balancer) Next() string {
	if len(b.urls) == 0 {
		return ""
	}
	i := atomic.AddUint64(&b.idx, 1)
	return b.urls[int(i-1)%len(b.urls)]
}

// StreamRun POSTs the run body to baseURL/v1/run and invokes onEvent for every
// SSE `data:` line until the stream ends or ctx is cancelled.
func StreamRun(ctx context.Context, baseURL string, body []byte, onEvent func([]byte)) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, baseURL+"/v1/run", bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	sc := bufio.NewScanner(resp.Body)
	sc.Buffer(make([]byte, 0, 64*1024), 4*1024*1024) // SSE payloads can be large
	for sc.Scan() {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}
		line := sc.Text()
		if strings.HasPrefix(line, "data: ") {
			onEvent([]byte(strings.TrimPrefix(line, "data: ")))
		}
	}
	return sc.Err()
}
