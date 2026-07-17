package hub

import "testing"

func TestHubCount(t *testing.T) {
	h := New()
	h.Add(NewClient("a", make(chan []byte, 1)))
	h.Add(NewClient("b", make(chan []byte, 1)))
	if h.Count() != 2 {
		t.Fatalf("want 2 got %d", h.Count())
	}
	h.Remove("a")
	if h.Count() != 1 {
		t.Fatalf("want 1 got %d", h.Count())
	}
}

func TestClientSendNonBlocking(t *testing.T) {
	ch := make(chan []byte, 1)
	c := NewClient("x", ch)
	c.Send([]byte("1"))
	c.Send([]byte("2")) // buffer full -> dropped, must not block
	if len(ch) != 1 {
		t.Fatalf("want 1 buffered got %d", len(ch))
	}
}
