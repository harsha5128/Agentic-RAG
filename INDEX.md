# Agentic RAG Platform - Complete Index

## 🎯 Start Here

### First Time Setup
1. Read: [PROJECT_SETUP_COMPLETE.md](PROJECT_SETUP_COMPLETE.md)
2. Review: [README.md](README.md)
3. Configure: `.env` (copy from `.env.example`)
4. Start: `docker-compose up -d`

### Quick Links
- **Main README**: [README.md](README.md) - Overview and getting started
- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design details
- **Deployment**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - How to deploy
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md) - Development guidelines
- **Setup Complete**: [PROJECT_SETUP_COMPLETE.md](PROJECT_SETUP_COMPLETE.md) - What was created
- **Inventory**: [COMPLETE_INVENTORY.md](COMPLETE_INVENTORY.md) - Detailed file listing

---

## 📁 Project Structure Map

### Core Application
```
Agentic RAG/
├── common/                    # Shared utilities
│   ├── config/               # Settings & configuration
│   ├── observability/        # Logging & tracing
│   └── schemas/              # Data models
├── services/                 # 7 Microservices
│   ├── document_ingestion/
│   ├── document_parsing/
│   ├── embedding_service/
│   ├── retrieval_service/
│   ├── agent_orchestration/
│   ├── query_processing/
│   └── evaluation_service/
└── tests/                    # Testing
```

### Infrastructure & DevOps
```
infrastructure/
├── terraform/               # AWS Infrastructure as Code
│   ├── main.tf             # VPC, RDS, ElastiCache, S3, SQS, ECR
│   └── variables.tf        # Configuration variables
├── kubernetes/             # Kubernetes manifests
│   └── deployment.yaml     # Service deployments
├── ansible/                # Ansible playbooks
│   └── deploy.yml          # Server configuration
├── nginx.conf              # API Gateway
└── mongodb-init/           # Database setup
    └── init.js
```

### Monitoring & Observability
```
monitoring/
├── prometheus.yml          # Metrics collection
├── alert_rules.yml         # Alert definitions
└── grafana-datasources.yml # Dashboard data sources
```

### Documentation
```
docs/
├── ARCHITECTURE.md         # System design & patterns
└── DEPLOYMENT.md           # Deployment procedures
```

---

## 🚀 Getting Started by Role

### For Developers
1. Clone the repo
2. Copy `.env.example` to `.env`
3. Set API keys in `.env`
4. Run: `docker-compose up -d`
5. Read: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
6. Check: [CONTRIBUTING.md](CONTRIBUTING.md)

### For DevOps/Infrastructure
1. Review: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
2. For AWS: See `infrastructure/terraform/`
3. For Kubernetes: See `infrastructure/kubernetes/`
4. For Ansible: See `infrastructure/ansible/`
5. Update environment variables in `.env`

### For Data Scientists
1. Review data schemas: [common/schemas/workflow.py](common/schemas/workflow.py)
2. Check embedding service: [services/embedding_service/app/main.py](services/embedding_service/app/main.py)
3. Review evaluation service: [services/evaluation_service/app/main.py](services/evaluation_service/app/main.py)
4. Explore agent orchestration: [services/agent_orchestration/app/main.py](services/agent_orchestration/app/main.py)

### For Operations/DevSecOps
1. Review: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
2. Check monitoring: `monitoring/` folder
3. Review Terraform: `infrastructure/terraform/`
4. Security settings: [common/config/settings.py](common/config/settings.py)

---

## 🔧 Common Tasks

### Start Development Environment
```bash
docker-compose up -d
docker-compose logs -f
```

### Run Tests
```bash
pytest tests/ -v --cov=services
```

### Deploy to AWS
```bash
cd infrastructure/terraform
terraform init
terraform plan
terraform apply
```

### Deploy to Kubernetes
```bash
kubectl apply -f infrastructure/kubernetes/deployment.yaml
```

### Deploy to Servers
```bash
ansible-playbook infrastructure/ansible/deploy.yml -i inventory.ini
```

### Access Monitoring
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Jaeger: http://localhost:16686
- OpenSearch: http://localhost:5601

---

## 📚 Documentation Map

| Document | Purpose | For | Time |
|----------|---------|-----|------|
| [README.md](README.md) | Overview & setup | Everyone | 5 min |
| [PROJECT_SETUP_COMPLETE.md](PROJECT_SETUP_COMPLETE.md) | What was created | Everyone | 10 min |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design | Architects & Devs | 20 min |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | How to deploy | DevOps/Ops | 30 min |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development guidelines | Developers | 15 min |
| [COMPLETE_INVENTORY.md](COMPLETE_INVENTORY.md) | Detailed file listing | Reference | 10 min |
| [common/config/settings.py](common/config/settings.py) | Configuration options | DevOps/Developers | 10 min |

---

## 🎯 Features Overview

### ✅ Document Processing
- PDF, DOCX, XLSX, CSV, TXT, Images
- OCR for scanned documents
- Multilingual support
- Table extraction
- Document versioning

### ✅ Vector Search & RAG
- Multiple VDB backends (Pinecone, Weaviate, Milvus)
- Semantic similarity search
- Metadata filtering
- Redis caching
- Document versioning with DVC

### ✅ Agentic AI
- Multi-agent orchestration (LangGraph)
- State management & persistence
- Tool/function calling
- Memory management
- Workflow coordination

### ✅ LLM Integration
- OpenAI & Anthropic support
- Token tracking & limits
- Embedding caching
- Temperature & sampling control
- Cost monitoring

### ✅ Enterprise Features
- Comprehensive logging (JSON)
- Distributed tracing (Jaeger)
- Metrics collection (Prometheus)
- Monitoring dashboards (Grafana)
- Alert rules
- Rate limiting & retries
- Query evaluations (RAGAS)
- Performance monitoring

### ✅ Infrastructure
- Docker containerization
- Docker Compose orchestration
- Kubernetes support
- Terraform for AWS
- Ansible automation
- API Gateway (Nginx)

---

## 🔐 Security Features

- ✅ Environment variable management
- ✅ JWT authentication framework
- ✅ API key validation
- ✅ Network security groups
- ✅ Database encryption support
- ✅ Audit logging framework
- ✅ Secret management (AWS Secrets Manager)
- ✅ VPC isolation

---

## 📊 Configuration

### Key Configurations (50+ total)
- **50+ environment variables** in [common/config/settings.py](common/config/settings.py)
- **Pydantic validation** for all configs
- **Environment file template** in `.env.example`
- **Multi-environment support** (dev, staging, prod)

---

## 🐳 Docker Services

**Infrastructure (7)**
- MongoDB, Redis, RabbitMQ, OpenSearch, Prometheus, Grafana, Jaeger

**Application (7)**
- Document Ingestion, Document Parsing, Embedding, Retrieval, Agent Orchestration, Query Processing, Evaluation

**Gateway (1)**
- Nginx (API Gateway)

**Total: 15 services** with health checks and networking

---

## 📦 Key Technologies

### LLM & AI
- LangChain, LangGraph, CrewAI, AutoGen
- OpenAI, Anthropic APIs
- RAGAS evaluation framework

### Data Processing
- PyPDF2, python-docx, pytesseract
- Pinecone, Weaviate, Milvus
- pandas, numpy

### Infrastructure
- Docker, Docker Compose, Kubernetes
- Terraform, Ansible
- AWS (EC2, RDS, S3, SQS, ECR)

### Observability
- Prometheus, Grafana, Jaeger
- OpenTelemetry, ELK Stack
- python-json-logger

### API & Web
- FastAPI, Uvicorn, Pydantic
- Nginx

---

## 🚀 Deployment Paths

### Path 1: Local Development (5 min)
```bash
docker-compose up -d
curl http://localhost:8001/health
```

### Path 2: Kubernetes Locally (10 min)
```bash
minikube start
kubectl apply -f infrastructure/kubernetes/deployment.yaml
```

### Path 3: AWS with Terraform (30 min)
```bash
cd infrastructure/terraform
terraform apply
```

### Path 4: Kubernetes on EKS (45 min)
```bash
eksctl create cluster
kubectl apply -f infrastructure/kubernetes/deployment.yaml
```

---

## ✅ What's Included

- ✅ **7 Production Microservices**
- ✅ **Complete Docker Setup** (15 services)
- ✅ **Terraform AWS Infrastructure**
- ✅ **Kubernetes Manifests**
- ✅ **Ansible Playbooks**
- ✅ **Comprehensive Monitoring Stack**
- ✅ **Complete Documentation** (4 guides)
- ✅ **Testing Framework**
- ✅ **Security Features**
- ✅ **API Gateway**
- ✅ **50+ Configuration Options**
- ✅ **50+ Files** with 5000+ lines of code

---

## 🎓 Learning Path

### Week 1: Fundamentals
1. Read [README.md](README.md)
2. Review [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
3. Start services: `docker-compose up -d`
4. Test endpoints: Use curl/Postman

### Week 2: Development
1. Read [CONTRIBUTING.md](CONTRIBUTING.md)
2. Explore services code
3. Run tests: `pytest tests/ -v`
4. Make first contribution

### Week 3: Deployment
1. Read [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
2. Try local Kubernetes: `minikube`
3. Setup AWS account
4. Try Terraform deployment

### Week 4: Production
1. Configure monitoring
2. Setup auto-scaling
3. Create deployment pipeline
4. Monitor in production

---

## 📞 Need Help?

1. **Read Documentation**: Start with [PROJECT_SETUP_COMPLETE.md](PROJECT_SETUP_COMPLETE.md)
2. **Check Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
3. **Review Deployment**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
4. **Explore Code**: Browse `services/` folder
5. **Common Issues**: See troubleshooting in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 🎉 Ready to Build!

Your production-grade Agentic RAG platform is set up and ready to use.

**Next Steps:**
1. Configure `.env` with your API keys
2. Run `docker-compose up -d`
3. Access Grafana at http://localhost:3000
4. Start building your AI applications!

Happy coding! 🚀

---

*Last updated: May 8, 2026*
