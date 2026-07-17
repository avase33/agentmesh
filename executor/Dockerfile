FROM rust:1.79-slim AS build
WORKDIR /app
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release --bin agentmesh-executor

FROM debian:bookworm-slim
RUN useradd -m app
COPY --from=build /app/target/release/agentmesh-executor /usr/local/bin/agentmesh-executor
USER app
ENV EXECUTOR_ADDR=0.0.0.0:8082
EXPOSE 8082
CMD ["agentmesh-executor"]
