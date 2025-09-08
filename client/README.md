## MCP Playground (Client)

A Streamlit-based playground UI for multiple models and providers.

### Dependencies
- Python 3.11
- See `requirements.txt` (key libs: `streamlit`, `langchain`, `langgraph`, `boto3`, `python-dotenv`, etc.)

### Environment Variables
Create a `.env` file under `client` (use `.env-example.txt` as a reference). Common keys:
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`
- `GOOGLE_API_KEY`, `GOOGLE_BASE_URL`
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `GROQ_API_KEY`, `GROQ_BASE_URL`

Optional: `servers_config.json` (MCP server/services config). The app reads `client/servers_config.json`.

Notes:
- `.env-example.txt` only shows OpenAI keys as a sample; add other provider keys as needed.
- Bedrock (AWS) requires valid AWS credentials and region.

### Run Locally
From the `client` directory:

```bash
# 1) Create and activate a virtualenv (example: venv)
python3.11 -m venv .venv
source .venv/bin/activate

# 2) Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3) Start (pick one)
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
# or use the script (port 8502)
chmod +x run.sh
./run.sh
```

Default ports:
- `Dockerfile`: 8501
- `run.sh`: 8502

Logs:
- Printed to console and saved under `logs/` (handled by the app’s logging system).

Tip: You can override ports using Streamlit flags or environment variables, e.g. `STREAMLIT_SERVER_PORT` and `STREAMLIT_SERVER_ADDRESS` (the `run.sh` script sets these before starting).

### Run with Docker
From the `client` directory:

```bash
# Build image (example tag)
docker build -t mcp-playground-client:latest .

# Run container (map 8501)
docker run --rm -it \
  -p 8501:8501 \
  --env-file .env \
  mcp-playground-client:latest
```

The container starts with:
```bash
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```

### Directory Overview (partial)
- `app.py`: entry point
- `services/`, `utils/`, `apps/`: business logic and UI
- `.streamlit/style.css`: styling
- `servers_config.json`: MCP/services configuration
- `icons/`, `static/`, `logs/`: assets and logs

### FAQ
- If the port is busy, change `--server.port`.
- If environment variables are missing, ensure `.env` is in `client` and keys are correct.

