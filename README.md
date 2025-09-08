---
title: ADMP-LS
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

# ADMP-LS

A multi-service MCP (Model Context Protocol) application containing independent MCP servers and a Streamlit client.

## Description & Citation

ADMP-LS is an agent-based platform for life sciences that unifies literature review, evidence-grounded QA, and parameter extraction with transparent provenance.


![](assets/main_pic.png)

![](assets/main_pic_review.png)

![](assets/extract1.png)
![](assets/extract2.png)
## Service Architecture

- **Streamlit Client** (Port 7860, Python 3.11): Main user interface
- **Retrieve Service** (Port 9487, Python 3.11): Biomedical RAG service
- **Review Service** (Port 8880, Python 3.11): Biomedical Review service

Related docs:
- Client details: `client/README.md`
- Retrieve server: `servers/Retrieve/readme.md`
- Review server (EN): `servers/Review/readme.md`

## Technical Features

- ✅ Multi-stage Docker build
- ✅ Multi-Python version support (3.11 + 3.12)
- ✅ Virtual environment isolation
- ✅ HF Spaces compliant
- ✅ GPU support (optional)

## Deployment

This Space uses Docker deployment, with all services running in the same container but using independent Python virtual environments to avoid dependency conflicts.

## Environment Variables

You can set the following environment variables through HF Spaces:

### Basic Configuration
- `PORT`: Streamlit client port (default 7860)
- `RETRIEVE_PORT`: Retrieve service port (default 9487)
- `REVIEW_PORT`: Review service port (default 8880)

### Retrieve Service LLM Configuration
- `QA_LLM_MAIN_API_KEY`: QA main model API key
- `QA_LLM_MAIN_BASE_URL`: QA main model base URL
- `QA_LLM_BACKUP_API_KEY`: QA backup model API key
- `QA_LLM_BACKUP_BASE_URL`: QA backup model base URL
- `REWRITE_LLM_MAIN_API_KEY`: Rewrite main model API key
- `REWRITE_LLM_MAIN_BASE_URL`: Rewrite main model base URL
- `REWRITE_LLM_BACKUP_API_KEY`: Rewrite backup model API key
- `REWRITE_LLM_BACKUP_BASE_URL`: Rewrite backup model base URL

### Retrieve Service Web Search Configuration
- `SERPER_API_KEY`: Serper API key (for web search)

### Review Service Configuration
- `OPENAI_BASE_URL`: OpenAI API base URL
- `OPENAI_API_KEY`: OpenAI API key
- `QIANWEN_BASE_URL`: Qianwen API base URL
- `QIANWEN_API_KEY`: Qianwen API key
- `SEARCH_URL`: Search service URL
- `LOG_DIR`: Log directory
- `LOG_LEVEL`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_MAX_SIZE`: Log file maximum size (bytes)
- `LOG_BACKUP_COUNT`: Log backup file count
- `LOG_ENABLE_CONSOLE`: Enable console logging (true/false)
- `LOG_ENABLE_FILE`: Enable file logging (true/false)
- `DEBUG_MODE`: Debug mode (true/false)

### Client Configuration (providers)
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`
- `GOOGLE_API_KEY`, `GOOGLE_BASE_URL`
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `GROQ_API_KEY`, `GROQ_BASE_URL`

Note: place a `.env` file under `client/` (see `client/.env-example.txt`). The client also reads `client/servers_config.json` for MCP/server integration.

## Ports
- Space app port (client UI): `PORT` (default 7860)
- Internal Retrieve service: 9487 (HTTP APIs: `/retrieve`, `/stream-chat`)
- Internal Review service: 8880 (HTTP APIs: `/health`, `/review_generate`; MCP mounts: `/review`, `/check`)

## Quick Links
- Start client locally: see `client/README.md`
- Start Retrieve locally or with Docker: see `servers/Retrieve/readme.md`
- Start Review locally or with Docker: see `servers/Review/readme.md`

## 🔗 Links
- **GitHub**: [https://github.com/JackKuo666/ADMP-LS](https://github.com/JackKuo666/ADMP-LS)
- **Hugging Face Spaces**: [https://huggingface.co/spaces/jackkuo/ADMP-LS](https://huggingface.co/spaces/jackkuo/ADMP-LS)


## 🙏 Acknowledgements

- [mcp-playground](https://github.com/Elkhn/mcp-playground)
- [LangChain](https://github.com/langchain-ai/langchain)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [Streamlit](https://github.com/streamlit/streamlit)

## Citation
Citation: Guo M., Sun Z., Xie S., Hu J., Sun S., Li X., Feng L., Jiang J. "ADMP-LS: Agent-based Dialogue and Mining Platform for Evidence-Grounded QA, Extraction, and Literature Review in Life Science," Zhejiang Lab & Western Carolina University.


