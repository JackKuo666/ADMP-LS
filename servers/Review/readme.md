# Review Service (Bio-Agent)

This service generates long-form biomedical literature reviews with streaming (SSE) and MCP mounts.

## Features
- Iterative research and planning loops
- Streaming SSE responses
- MCP mounts: `/review`, `/check`
- Configurable LLM providers (OpenAI-compatible, Qianwen/DashScope)

## Requirements
- Python 3.11+
- `.env` (see `env_example.txt`)
- Optional: Docker

## Configuration
Common env keys:
- `OPENAI_BASE_URL`, `OPENAI_API_KEY`
- `QIANWEN_BASE_URL`, `QIANWEN_API_KEY`
- `SEARCH_URL` (e.g., `http://localhost:9487`)
- `LOG_DIR`, `LOG_LEVEL`, `LOG_MAX_SIZE`, `LOG_BACKUP_COUNT`, `LOG_ENABLE_CONSOLE`, `LOG_ENABLE_FILE`
- `DEBUG_MODE` (true shows `/docs`)

## Run Locally
Option A (uv):
```
cd servers/Review
uv sync
uv run uvicorn Review.main:app --host 0.0.0.0 --port 8880
```

Option B (script):
```
cd servers/Review
chmod +x run.sh
./run.sh
```

Endpoints:
- MCP: `http://localhost:8880/review`, `http://localhost:8880/check`
- Docs (if DEBUG_MODE=true): `http://localhost:8880/docs`

## API
- `GET /health` (SSE)
- `GET /review_generate?query=...` (SSE)

Example:
```
curl -N "http://localhost:8880/review_generate?query=generate+review+about+rna-seq"
```

## Docker
Build (repo root):
```
docker build -t review_mcp:local -f servers/Review/Dockerfile servers/Review
```
Run:
```
docker run --rm -p 8880:8880 --env-file .env review_mcp:local
```

Notes:
- Uses `uv` with `uv.lock` for reproducible installs.
- Pipeline may take tens of minutes; progress is streamed via SSE.
