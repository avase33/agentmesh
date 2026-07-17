// Command agentmesh-gateway is the front door of the mesh: it authenticates
// clients, holds their WebSocket connections, and load-balances agent runs to the
// Python intelligence workers, relaying the streamed events back.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"sync/atomic"

	"github.com/gorilla/websocket"

	"github.com/avase33/agentmesh/gateway/internal/config"
	"github.com/avase33/agentmesh/gateway/internal/hub"
	"github.com/avase33/agentmesh/gateway/internal/upstream"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

var connSeq uint64

type clientMsg struct {
	Type     string          `json:"type"`
	Token    string          `json:"token"`
	RunID    string          `json:"runId"`
	Workflow json.RawMessage `json:"workflow"`
	Input    string          `json:"input"`
}

type runBody struct {
	RunID    string          `json:"runId"`
	Workflow json.RawMessage `json:"workflow"`
	Input    string          `json:"input"`
}

type Server struct {
	cfg config.Config
	hub *hub.Hub
	bal *upstream.Balancer
}

func (s *Server) handleWS(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer conn.Close()

	id := fmt.Sprintf("c%d", atomic.AddUint64(&connSeq, 1))
	writeC := make(chan []byte, 256)
	s.hub.Add(hub.NewClient(id, writeC))
	defer s.hub.Remove(id)

	// single writer goroutine — the only place the socket is written, so
	// concurrent run streams can't corrupt frames.
	done := make(chan struct{})
	go func() {
		for {
			select {
			case msg := <-writeC:
				if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
					return
				}
			case <-done:
				return
			}
		}
	}()

	send := func(v any) {
		b, err := json.Marshal(v)
		if err != nil {
			return
		}
		select {
		case writeC <- b:
		default: // slow client: drop rather than block the mesh
		}
	}

	authed := false
	runs := make(map[string]context.CancelFunc)
	var mu sync.Mutex

	for {
		_, data, err := conn.ReadMessage()
		if err != nil {
			break
		}
		var m clientMsg
		if json.Unmarshal(data, &m) != nil {
			send(map[string]any{"type": "error", "message": "bad json"})
			continue
		}

		switch m.Type {
		case "auth":
			authed = m.Token == s.cfg.Token
			send(map[string]any{"type": "authed", "ok": authed})

		case "ping":
			send(map[string]string{"type": "pong"})

		case "run":
			if !authed {
				send(map[string]any{"type": "error", "message": "unauthorized"})
				continue
			}
			target := s.bal.Next()
			if target == "" {
				send(map[string]any{"type": "error", "message": "no upstream available"})
				continue
			}
			wf := m.Workflow
			if len(wf) == 0 {
				wf = json.RawMessage("{}")
			}
			body, _ := json.Marshal(runBody{RunID: m.RunID, Workflow: wf, Input: m.Input})

			ctx, cancel := context.WithCancel(context.Background())
			mu.Lock()
			runs[m.RunID] = cancel
			mu.Unlock()

			go func(runID string) {
				defer func() {
					mu.Lock()
					delete(runs, runID)
					mu.Unlock()
				}()
				err := upstream.StreamRun(ctx, target, body, func(ev []byte) {
					send(map[string]any{"type": "event", "runId": runID, "event": json.RawMessage(ev)})
				})
				if err != nil && ctx.Err() == nil {
					send(map[string]any{"type": "error", "runId": runID, "message": err.Error()})
				}
			}(m.RunID)

		case "cancel":
			mu.Lock()
			if c, ok := runs[m.RunID]; ok {
				c()
			}
			mu.Unlock()
		}
	}

	close(done)
	mu.Lock()
	for _, c := range runs {
		c()
	}
	mu.Unlock()
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"status":      "ok",
		"service":     "gateway",
		"connections": s.hub.Count(),
		"upstreams":   s.cfg.Upstreams,
	})
}

func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintf(w, "agentmesh_active_connections %d\n", s.hub.Count())
	fmt.Fprintf(w, "agentmesh_upstreams %d\n", len(s.cfg.Upstreams))
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func main() {
	cfg := config.Load()
	s := &Server{cfg: cfg, hub: hub.New(), bal: upstream.NewBalancer(cfg.Upstreams)}

	mux := http.NewServeMux()
	mux.HandleFunc("/ws", s.handleWS)
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/metrics", s.handleMetrics)

	log.Printf("agentmesh gateway listening on %s -> upstreams %v", cfg.Addr, cfg.Upstreams)
	if err := http.ListenAndServe(cfg.Addr, mux); err != nil {
		log.Fatal(err)
	}
}
