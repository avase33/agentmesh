.PHONY: up down test test-rust test-python test-go demo intel-demo build-web

# Bring the whole mesh up (Rust + Python + Go + Next.js) via Docker.
up:
	docker compose up --build

down:
	docker compose down

# Run every language's test suite.
test: test-rust test-python test-go

test-rust:
	cd executor && cargo test

test-python:
	cd intelligence && pip install -e ".[dev]" && pytest -q

test-go:
	cd gateway && go test ./...

# Run the intelligence layer's demo workflow offline (no services needed).
intel-demo:
	cd intelligence && python -m agentmesh_intelligence.cli run --input "How does the Go gateway scale?"

# End-to-end smoke test against a running stack (needs `make up` first).
demo:
	python scripts/verify.py
