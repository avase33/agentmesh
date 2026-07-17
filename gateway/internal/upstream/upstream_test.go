package upstream

import "testing"

func TestBalancerRoundRobin(t *testing.T) {
	b := NewBalancer([]string{"a", "b", "c"})
	got := []string{b.Next(), b.Next(), b.Next(), b.Next()}
	want := []string{"a", "b", "c", "a"}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("index %d: want %s got %s", i, want[i], got[i])
		}
	}
}

func TestBalancerEmpty(t *testing.T) {
	if NewBalancer(nil).Next() != "" {
		t.Fatal("empty balancer should return empty string")
	}
}
