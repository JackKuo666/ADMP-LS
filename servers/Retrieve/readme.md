# Bio RAG Server

A FastAPI-based Biomedical RAG service that supports PubMed retrieval, web search, and vector DB queries, providing intelligent Q&A and document retrieval with streaming responses.

## 🚀 Features

- **Multi-source retrieval**: PubMed, Web search, personal vector DBs
- **Intelligent Q&A**: RAG-based answers with streaming SSE responses
- **Query rewrite**: Smart multi-query and rewrite to improve recall and precision
- **Primary/backup LLM**: Automatic failover between main and backup providers
- **Internationalization**: Chinese/English responses (87 i18n messages, 8 categories)
- **Logging & tracing**: Full request tracing with correlation IDs
- **CORS**: Easy frontend integration

## 🏗️ Project Structure (partial)

```
bio_rag_server/
├── bio_agent/
├── bio_requests/
├── config/
├── dto/
├── routers/
├── search_service/
├── service/
├── utils/
└── test/
```

## 📋 Requirements

- Python 3.11+
- LLM providers (OpenAI-compatible or others per your config)

## 🛠️ Setup

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Configure environment

Create a `.env` file (see `env_example.txt` for keys):

- `QA_LLM_MAIN_API_KEY`, `QA_LLM_MAIN_BASE_URL`
- `QA_LLM_BACKUP_API_KEY`, `QA_LLM_BACKUP_BASE_URL`
- `REWRITE_LLM_MAIN_API_KEY`, `REWRITE_LLM_MAIN_BASE_URL`
- `REWRITE_LLM_BACKUP_API_KEY`, `REWRITE_LLM_BACKUP_BASE_URL`
- `SERPER_API_KEY` (web search)
- `ENVIRONMENT` (e.g., dev)

### 3) Run the service

```bash
python main.py
```

Service runs at `http://localhost:9487`.

### Run with Docker

```bash
docker build -t bio-rag-server .
docker run --rm -p 9487:9487 --env-file .env bio-rag-server
```

Note: The Dockerfile pre-installs `crawl4ai` and runs basic setup checks during build.

## 📚 API

### 1) Document Retrieval

Endpoint: `POST /retrieve`

Request body:
```json
{
  "query": "cancer treatment",
  "top_k": 5,
  "search_type": "keyword",
  "is_rewrite": true,
  "data_source": ["pubmed"],
  "user_id": "user123",
  "pubmed_topk": 30
}
```

Response (example):
```json
[
  {
    "title": "Cancer Treatment Advances",
    "abstract": "Recent advances in cancer treatment...",
    "url": "https://pubmed.ncbi.nlm.nih.gov/...",
    "score": 0.95
  }
]
```

### 2) Streaming Chat (RAG)

Endpoint: `POST /stream-chat`

Request body:
```json
{
  "query": "What are the latest treatments for breast cancer?",
  "is_web": true,
  "is_pubmed": true,
  "language": "en"
}
```

Response: Server-Sent Events (SSE) streaming

### 3) Internationalization

All APIs support i18n via the `language` field:

- `zh` (default)
- `en`

Success response shape:
```json
{
  "success": true,
  "data": [...],
  "message": "Search successful",
  "language": "en"
}
```

Error response shape:
```json
{
  "success": false,
  "error": {
    "code": 500,
    "message": "Search failed",
    "language": "en",
    "details": "..."
  }
}
```

## 📊 Monitoring & Logs

- Log files: `logs/bio_rag_YYYY-MM-DD.log`
- Correlation ID tracing per request
- Processing time recorded via middleware

## 🔒 Security

- API key and endpoint configuration via environment variables
- Request logging
- CORS enabled
- Error handling with safe messages

## 🤝 Contributing

1. Fork
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add some AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

MIT (see `LICENSE`).

## 🆘 Support

1. Check Issues
2. Open a new Issue
3. Contact maintainers

## 🗺️ Roadmap

- [ ] More data sources
- [ ] Auth & permissions
- [ ] Vector search optimization
- [ ] More LLM providers
- [ ] Result caching
- [ ] API rate limiting

---

Note: Ensure all required API keys and provider endpoints are configured before use.