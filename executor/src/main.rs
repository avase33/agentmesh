//! HTTP server for the agentmesh execution & edge layer (axum + tokio).
//!
//! Endpoints (see proto/protocol.md):
//!   GET  /health
//!   POST /v1/tokenize   { text }              -> { tokens, count }
//!   POST /v1/eval       { expr, vars }        -> { ok, value, error? }
//!   POST /v1/csv        { csv, op, column }   -> { ok, rows, result, error? }

use std::collections::HashMap;

use axum::{routing::{get, post}, Json, Router};
use serde::{Deserialize, Serialize};

use agentmesh_executor::{csv_ops, sandbox, tokenizer};

#[derive(Deserialize)]
struct TokReq {
    text: String,
}

#[derive(Serialize)]
struct TokResp {
    tokens: Vec<String>,
    count: usize,
}

async fn tokenize(Json(req): Json<TokReq>) -> Json<TokResp> {
    let tokens = tokenizer::tokenize(&req.text);
    let count = tokens.len();
    Json(TokResp { tokens, count })
}

#[derive(Deserialize)]
struct EvalReq {
    expr: String,
    #[serde(default)]
    vars: HashMap<String, f64>,
}

#[derive(Serialize)]
struct EvalResp {
    ok: bool,
    value: f64,
    is_bool: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

async fn eval(Json(req): Json<EvalReq>) -> Json<EvalResp> {
    match sandbox::eval(&req.expr, &req.vars) {
        Ok(v) => Json(EvalResp {
            ok: true,
            value: v.as_f64(),
            is_bool: matches!(v, sandbox::Value::Bool(_)),
            error: None,
        }),
        Err(e) => Json(EvalResp {
            ok: false,
            value: 0.0,
            is_bool: false,
            error: Some(e),
        }),
    }
}

#[derive(Deserialize)]
struct CsvReq {
    csv: String,
    op: String,
    column: String,
}

#[derive(Serialize)]
struct CsvResp {
    ok: bool,
    rows: usize,
    result: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

async fn csv(Json(req): Json<CsvReq>) -> Json<CsvResp> {
    match csv_ops::aggregate(&req.csv, &req.op, &req.column) {
        Ok(a) => Json(CsvResp {
            ok: true,
            rows: a.rows,
            result: a.result,
            error: None,
        }),
        Err(e) => Json(CsvResp {
            ok: false,
            rows: 0,
            result: 0.0,
            error: Some(e),
        }),
    }
}

async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({ "status": "ok", "service": "executor" }))
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt().with_target(false).init();

    let app = Router::new()
        .route("/health", get(health))
        .route("/v1/tokenize", post(tokenize))
        .route("/v1/eval", post(eval))
        .route("/v1/csv", post(csv));

    let addr = std::env::var("EXECUTOR_ADDR").unwrap_or_else(|_| "0.0.0.0:8082".to_string());
    let listener = tokio::net::TcpListener::bind(&addr).await.expect("bind");
    tracing::info!("agentmesh executor listening on {addr}");
    axum::serve(listener, app).await.expect("serve");
}
