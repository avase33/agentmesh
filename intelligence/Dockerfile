FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY agentmesh_intelligence ./agentmesh_intelligence
RUN pip install --no-cache-dir ".[server,http]"
ENV AGENTMESH_LLM=mock
EXPOSE 8081
CMD ["agentmesh-intel", "serve", "--host", "0.0.0.0", "--port", "8081"]
