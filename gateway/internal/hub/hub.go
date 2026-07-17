// Package hub tracks live WebSocket clients with goroutine-safe registration.
//
// This is the piece that makes Go the right tool for the gateway: one lightweight
// goroutine per connection, coordinated through channels, so tens of thousands of
// simultaneous streams cost only a few KB of stack each.
package hub

import "sync"

type Client struct {
	ID     string
	mu     sync.Mutex // serialises writes to the underlying socket
	writeC chan []byte
}

func NewClient(id string, writeC chan []byte) *Client {
	return &Client{ID: id, writeC: writeC}
}

// Send queues a text frame for the client's single writer goroutine. Never
// writes to the socket directly, so concurrent senders are safe.
func (c *Client) Send(msg []byte) {
	c.mu.Lock()
	defer c.mu.Unlock()
	select {
	case c.writeC <- msg:
	default:
		// drop if the client is too slow; keeps the mesh from stalling
	}
}

type Hub struct {
	mu      sync.RWMutex
	clients map[string]*Client
}

func New() *Hub {
	return &Hub{clients: make(map[string]*Client)}
}

func (h *Hub) Add(c *Client) {
	h.mu.Lock()
	h.clients[c.ID] = c
	h.mu.Unlock()
}

func (h *Hub) Remove(id string) {
	h.mu.Lock()
	delete(h.clients, id)
	h.mu.Unlock()
}

func (h *Hub) Count() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}
