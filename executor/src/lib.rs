//! agentmesh execution & edge layer.
//!
//! The compute engine of the mesh: safe sandboxed evaluation, fast tokenization
//! and CSV aggregation, exposed as small pure functions (here) and over HTTP
//! (see `main.rs`). Everything is dependency-light and deterministic.

pub mod csv_ops;
pub mod sandbox;
pub mod tokenizer;
