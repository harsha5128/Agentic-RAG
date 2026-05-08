# Agentic RAG Platform

A production-grade, end-to-end Retrieval Augmented Generation (RAG) system with multi-agent orchestration, built on AWS and microservices architecture.

## 📋 Overview

This project implements a sophisticated RAG platform that combines:
- **Document Ingestion Pipeline**: SQS-based async document uploads
- **Multi-Agent Orchestration**: LangGraph + CrewAI + AutoGen for complex workflows
- **Vector Search**: Pinecone/Weaviate/Milvus for semantic search
- **LLM Integration**: OpenAI and Anthropic models
- **Observability**: Prometheus, Grafana, Jaeger, ELK stack
- **Infrastructure as Code**: Terraform, Kubernetes, Ansible
- **Enterprise Features**: Caching, token tracking, evaluations, memory management

## 🏗️ Architecture

### Microservices

1. **Document Ingestion Service** - Uploads and manages document lifecycle
2. **Document Parsing Service** - Extracts text, handles OCR, multilingual support
3. **Embedding Service** - Generates embeddings using OpenAI models
4. **Retrieval Service** - Vector database operations and similarity search
5. **Agent Orchestration Service** - Multi-agent workflow coordination (LangGraph)
6. **Query Processing Service** - Query routing and LLM response generation
7. **Evaluation Service** - Quality metrics and feedback collection

### Data Flow

```
Documents → Ingestion → Parsing → Chunking → Embedding → Vector DB
                                                             ↓
Query → Processing → Retrieval → Agent Orchestration → LLM → Response
                                                             ↓
                                                        Evaluation
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.10+
- AWS Account (for cloud deployment)
- OpenAI API Key
- Pinecone API Key (optional, for vector search)

### Local Development

1. **Clone Repository**
```bash
git clone https://github.com/harsha5128/Agentic-RAG.git
cd Agentic-RAG
```

2. **Setup Environment**
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. **Start Services**
```bash
docker-compose up -d
```

4. **Verify Services**
```bash
# Check health of all services
curl http://localhost:8001/health  # Document Ingestion
curl http://localhost:8003/health  # Embedding Service
curl http://localhost:3000         # Grafana
curl http://localhost:9090         # Prometheus
```

5. **Access Dashboards**
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Jaeger: http://localhost:16686
- OpenSearch Dashboards: http://localhost:5601

## 📚 API Examples

### Upload Document
```bash
curl -X POST http://localhost:8001/ingest \
  -F "file=@document.pdf" \
  -F "user_id=user123"
```

### Query RAG System
```bash
curl -X POST http://localhost:8005/execute-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "wf-123",
    "query": {
      "query_id": "q-123",
      "query_text": "What is the main topic?"
    }
  }'
```

### Evaluate Query Results
```bash
curl -X POST http://localhost:8007/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "query_id": "q-123",
    "retrieved_count": 5,
    "answer_length": 250,
    "user_rating": 4
  }'
```

## 🔧 Configuration

### Environment Variables

Key environment variables (see `.env.example` for complete list):

```bash
# LLM & APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=claude-...
PINECONE_API_KEY=...

# AWS
AWS_REGION=us-east-1
S3_BUCKET_NAME=rag-documents
AWS_SQS_QUEUE_URL=...

# Database
MONGODB_URI=mongodb://admin:pass@mongodb:27017/rag_db
REDIS_HOST=redis

# Services
LLM_MODEL_NAME=gpt-4-turbo-preview
EMBEDDING_MODEL_NAME=text-embedding-3-large
MAX_TOKENS=4096
TEMPERATURE=0.7
```

## 📊 Features

### Document Processing
- ✅ PDF, DOCX, XLSX, CSV, TXT, Images
- ✅ OCR for scanned documents
- ✅ Multilingual support (langdetect)
- ✅ Table extraction
- ✅ Document versioning (DVC)

### Advanced RAG
- ✅ Semantic chunking with overlap
- ✅ Embedding caching (Redis)
- ✅ Multi-vector database support
- ✅ Hybrid search (BM25 + Vector)
- ✅ Reranking for relevance

### Agentic Features
- ✅ Multi-agent orchestration (LangGraph)
- ✅ State persistence and memory
- ✅ Tool/function calling
- ✅ Agent communication
- ✅ Workflow scheduling

### Observability
- ✅ Structured logging (JSON)
- ✅ Distributed tracing (Jaeger)
- ✅ Metrics (Prometheus)
- ✅ Dashboards (Grafana)
- ✅ Log aggregation (ELK)

### Production Ready
- ✅ Rate limiting & retry logic
- ✅ Token tracking & cost monitoring
- ✅ Query evaluations (RAGAS)
- ✅ Caching strategies
- ✅ Circuit breakers

## 🚢 Deployment

### Docker Compose (Development)
```bash
docker-compose up -d
```

### Kubernetes (Production)
```bash
# Deploy to Kubernetes
kubectl apply -f infrastructure/kubernetes/deployment.yaml

# Check deployment
kubectl get pods -n agentic-rag
kubectl logs -n agentic-rag pod/agent-orchestration-xxx
```

### Terraform (AWS Infrastructure)
```bash
cd infrastructure/terraform
terraform init
terraform plan
terraform apply
```

### Ansible (Server Setup)
```bash
ansible-playbook infrastructure/ansible/deploy.yml -i inventory.ini
```

## 📈 Monitoring & Observability

### Prometheus Metrics
- HTTP request latency
- Error rates by service
- Token usage tracking
- Cache hit/miss rates
- Document processing time

### Grafana Dashboards
- Service health overview
- Request metrics
- Error tracking
- Database performance
- Cost analysis

### Jaeger Tracing
- Request tracing across services
- Latency analysis
- Error tracking

## 🧪 Testing

### Run Tests
```bash
pytest tests/ -v --cov=services
```

### Load Testing
```bash
# Using locust
locust -f tests/load_test.py --host=http://localhost:80
```

## 📖 Documentation

- [Architecture Guide](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## 🔐 Security

- Environment variable management (python-dotenv)
- JWT authentication
- API key rotation
- Network security groups
- VPC isolation
- Database encryption
- Audit logging

## 💾 Data Management

### Document Versioning
- DVC integration for document version control
- S3 backend for storage
- Automatic version tracking

### Cache Management
- Redis caching layer (3600s TTL)
- Embedding cache
- Query result cache
- Cache invalidation strategies

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md)

## 📝 License

MIT License - see LICENSE file

## 👥 Support

- 📧 Email: team@ragplatform.com
- 💬 Discord: [Join our community](https://discord.gg/...)
- 📄 Documentation: [Full Docs](docs/README.md)

## 🗺️ Roadmap

- [ ] GraphQL API layer
- [ ] Fine-tuning pipeline
- [ ] Real-time document streaming
- [ ] Advanced reranking models
- [ ] Multi-modal support (video, audio)
- [ ] Federated learning capabilities
- [ ] Advanced guardrails framework

---

**Built with ❤️ by the Agentic RAG Team**
