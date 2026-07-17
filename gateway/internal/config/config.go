// Package config loads gateway settings from the environment.
package config

import (
	"os"
	"strings"
)

type Config struct {
	Addr      string   // listen address, e.g. ":8080"
	Token     string   // shared auth token clients must present
	Upstreams []string // intelligence-layer base URLs to load-balance across
}

func Load() Config {
	return Config{
		Addr:      env("AGENTMESH_GATEWAY_ADDR", ":8080"),
		Token:     env("AGENTMESH_TOKEN", "dev-token"),
		Upstreams: splitCSV(env("AGENTMESH_INTEL_URLS", "http://localhost:8081")),
	}
}

func env(k, def string) string {
	if v, ok := os.LookupEnv(k); ok && v != "" {
		return v
	}
	return def
}

func splitCSV(s string) []string {
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}
