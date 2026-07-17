# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/);
versioning: [SemVer](https://semver.org/).

## [0.1.0] - 2026-07-16

Initial release — a four-language polyglot AI agent mesh.

### Added
- **Rust executor** (axum): sandboxed arithmetic/logic DSL evaluator (no arbitrary
  code), fast sub-word tokenizer, and one-pass CSV aggregation, over HTTP.
- **Python intelligence layer**: LangGraph-style DAG engine with topological
  execution + cycle detection, streaming mock/OpenAI LLM providers, hashing-embed
  RAG store, and an executor client with a pure-Python offline mirror. FastAPI
  service streams runs as SSE.
- **Go gateway**: WebSocket front door with token auth, per-connection writer
  goroutine, round-robin load-balancing across intelligence workers, and SSE
  relay. `/health` + `/metrics`.
- **Next.js dashboard**: drag-and-drop workflow node canvas (SVG), live WebSocket
  event streaming, per-node status, streamed answer + event log.
- Shared JSON wire protocol (`proto/protocol.md`) decoupling every layer.
- Docker + docker-compose for the whole mesh, per-language Dockerfiles, GitHub
  Actions CI (Rust/Python/Go/Web), Makefile, offline verifier, MIT license.
