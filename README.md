# 🤖 AI Service

> Production-ready AI platform for intelligent content moderation, multimodal analysis, and retrieval-augmented generation.

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/DP-2006/ai-service?style=flat-square&logo=github)](https://github.com/DP-2006/ai-service)

## ✨ Features

- **🛡️ Content Moderation** – Real-time text and image moderation powered by LLMs
- **💬 Chat Intelligence** – Monitor conversations and suggest safety interventions
- **🖼️ Vision Analysis** – Multi-modal image understanding and contextual analysis
- **🔍 Retrieval-Augmented Generation** – Index and query documents with semantic search
- **⚡ Production Ready** – Containerized with Docker, secured with webhook verification
- **🚀 Scalable** – Built on FastAPI with async support and local LLM inference

## 🏗️ Architecture

The service integrates three core components:

| Component | Role | Port |
|-----------|------|------|
| **FastAPI Service** | REST API gateway & orchestration | 9000 |
| **Ollama** | Local LLM inference engine (gemma3:27b) | 11434 |
| **ChromaDB** | Vector store for embeddings & retrieval | 8001 |

```
Client Request
     ↓
  FastAPI (9000)
     ├→ Moderation Service
     ├→ Chat Monitor
     ├→ RAG Engine → ChromaDB (8001)
     └→ Vision Analyzer
     ↓
  Ollama (11434)
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose (or Python 3.9+)
- GPU support optional (recommended for inference)

### Option 1: Docker (Recommended)

```bash
# Clone and navigate
git clone https://github.com/DP-2006/ai-service.git
cd ai-service

# Create .env file
cat > .env << EOF
OLLAMA_HOST=http://ollama:11434
CHROMA_HOST=chromadb
CHROMA_PORT=8000
APP_HOST=0.0.0.0
APP_PORT=9000
LOG_LEVEL=INFO
WEBHOOK_SECRET=your-secret-key-here
EOF

# Launch stack
docker compose up --build
```

Service will be live at `http://localhost:9000`

### Option 2: Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Start Ollama and ChromaDB
docker compose up ollama chromadb -d

# Run API
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 9000
```

## 📡 API Endpoints

### 🏥 Health & Status
```http
GET /health
```

### 🛡️ Moderation
```http
POST /moderate/text
Content-Type: application/json

{
  "content": "text to moderate",
  "context": "optional context"
}

POST /moderate/image
{
  "image_b64": "base64-encoded-image",
  "context": "optional context"
}
```

### 💬 Chat Monitoring
```http
POST /chat/monitor
{
  "messages": [{"role": "user", "content": "..."}],
  "chat_id": "chat-123",
  "user_id": "user-456"
}

POST /chat/hint
{
  "messages": [{"role": "user", "content": "..."}]
}
```

### 🔍 RAG (Retrieval-Augmented Generation)
```http
POST /rag/index
{
  "doc_id": "doc-001",
  "text": "document content here",
  "metadata": {"source": "docs", "type": "guide"}
}

POST /rag/query
{
  "question": "what is the refund policy?"
}
```

### 🖼️ Vision Analysis
```http
POST /vision/analyze
{
  "image_b64": "base64-encoded-image",
  "context": "optional context",
  "user_id": "user-123"
}
```

## 📦 Project Structure

```
ai-service/
├── app/
│   ├── core/              # Config, security, moderation logic
│   ├── routers/           # API endpoint definitions
│   ├── services/          # Business logic (chat, RAG, vision)
│   ├── schemas/           # Pydantic models
│   └── main.py            # FastAPI app factory
├── fine_tuning/           # Model fine-tuning workflows
├── scripts/               # Utility scripts
├── docker-compose.yml     # Multi-container orchestration
├── Dockerfile             # Container image
├── requirements.txt       # Python dependencies
└── README.md
```

## 🔧 Configuration

Edit `.env` to customize:

```env
# Models (from Ollama)
MODEL_TEXT=gemma3:27b
MODEL_VISION=gemma3:27b
MODEL_EMBED=nomic-embed-text

# Chroma Vector Store
CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_COLLECTION=org_knowledge

# API Security
WEBHOOK_SECRET=dev-secret
WEBHOOK_MAX_AGE_SECONDS=300

# Admin Alerts
ADMIN_ALERT_URL=https://your-webhook-url.com/alerts

# Logging
LOG_LEVEL=INFO
```

## 🔐 Security

- **Webhook Verification** – All routes protected with HMAC-SHA256 signature validation
- **Environment Secrets** – Sensitive data via `.env` and secure secret management
- **Role-Based Control** – Messages tagged by role (user, seller, admin)

## 📊 Response Format

Moderation endpoints return structured results:

```json
{
  "suggested_action": "block|allow|alert_admin",
  "categories": ["violence", "hate_speech"],
  "severity": "high|medium|low",
  "confidence": 0.95,
  "reason": "Content violates policy X",
  "admin_summary": "Human-readable summary for review"
}
```

## 🛠️ Development

### Running Tests
```bash
# (Add test suite)
pytest tests/ -v
```

### Linting & Formatting
```bash
# Format code
black app/

# Lint
flake8 app/ --max-line-length=100
```

### Building Models
```bash
cd fine_tuning
python generate_dataset.py
python setup_files.py
```

## 📈 Performance Tips

- **GPU Acceleration** – Ensure `nvidia-docker` is configured in `docker-compose.yml`
- **Model Selection** – Swap models in `.env` (gemma2, llama2, mistral) based on latency/quality tradeoff
- **Vector Indexing** – Pre-index documents via `/rag/index` for faster queries
- **Caching** – Implement response caching for high-volume moderation

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Ollama connection fails | Verify `OLLAMA_HOST` in `.env` and `docker compose ps` |
| ChromaDB empty responses | Ensure documents indexed via `/rag/index` before querying |
| High latency | Check GPU allocation; consider smaller models in `.env` |
| Webhook errors | Validate `WEBHOOK_SECRET` matches client; check request signature |

## 📝 License

This project is available as-is for development and commercial use.

## 🤝 Contributing

We welcome contributions! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For issues, questions, or suggestions:
- 🐛 [Open an Issue](https://github.com/DP-2006/ai-service/issues)
- 💬 [Start a Discussion](https://github.com/DP-2006/ai-service/discussions)

---

**Made with ❤️ by the AI Service team**

[![GitHub](https://img.shields.io/badge/GitHub-DP--2006/ai--service-white?style=flat-square&logo=github)](https://github.com/DP-2006/ai-service)
