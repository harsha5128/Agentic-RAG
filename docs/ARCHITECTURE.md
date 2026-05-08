# Agentic RAG Platform - Architecture Guide

## System Architecture Overview

The Agentic RAG Platform is built on a modern microservices architecture with the following principles:

1. **Separation of Concerns** - Each service has a single responsibility
2. **Async Processing** - Long-running tasks use message queues
3. **Scalability** - Horizontally scalable microservices
4. **Observability** - Comprehensive logging, tracing, and metrics
5. **Resilience** - Circuit breakers, retries, and failover mechanisms

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        API Gateway (Nginx)                  │
└────────┬────────┬────────┬────────┬────────┬────────┬────────┘
         │        │        │        │        │        │
    ┌────▼──┐ ┌──▼────┐ ┌─▼────┐ ┌┴────┐ ┌─▼────┐ ┌┴─────┐
    │Ingest │ │Parse  │ │Embed  │ │Retr │ │Orch  │ │Query │
    │Service│ │Service│ │Service│ │Service│ │Service│ │Service│
    └────┬──┘ └──┬────┘ └─┬────┘ └┬────┘ └─┬────┘ └┬─────┘
         │       │        │       │        │        │
    ┌────▼───────▼────────▼───────▼────────▼────────▼──┐
    │            Message Queue (RabbitMQ/SQS)         │
    └──────────────────────────────────────────────────┘
         │              │               │
    ┌────▼──────┐  ┌───▼────────┐  ┌──▼──────┐
    │  MongoDB  │  │   Redis    │  │  Vector │
    │           │  │   Cache    │  │   DB    │
    │(Documents)│  │  (State)   │  │ (Index) │
    └───────────┘  └────────────┘  └─────────┘
```

## Service Responsibilities

### 1. Document Ingestion Service
**Responsibility**: Handle document uploads and initial validation

**Key Functions**:
- Receive file uploads via HTTP/Multipart
- Validate file size and type
- Upload to S3
- Publish to SQS for async processing
- Return ingestion status

**Tech Stack**: FastAPI, boto3, Pydantic

### 2. Document Parsing Service
**Responsibility**: Extract and parse document content

**Key Functions**:
- Download from S3
- Parse based on file type (PDF, DOCX, XLSX, etc.)
- Apply OCR for scanned documents
- Support multilingual content
- Chunk text with overlap
- Publish parsed content

**Tech Stack**: PyPDF2, python-docx, openpyxl, pytesseract, Pillow

### 3. Embedding Service
**Responsibility**: Generate embeddings for text chunks

**Key Functions**:
- Receive text chunks
- Generate embeddings using OpenAI API
- Cache embeddings in Redis
- Track token usage
- Return embedding vectors

**Tech Stack**: OpenAI API, Redis, LangChain

### 4. Retrieval Service
**Responsibility**: Manage vector search and metadata retrieval

**Key Functions**:
- Index document embeddings in vector DB
- Perform similarity search
- Apply metadata filters
- Support multiple vector DB backends
- Cache frequent queries

**Tech Stack**: Pinecone/Weaviate/Milvus, Redis, MongoDB

### 5. Agent Orchestration Service
**Responsibility**: Coordinate multi-agent workflows

**Key Functions**:
- Build and execute LangGraph workflows
- Manage agent states
- Implement memory and context
- Handle tool/function calls
- Persist workflow state
- Support agent communication

**Tech Stack**: LangGraph, CrewAI, AutoGen, LangChain

### 6. Query Processing Service
**Responsibility**: Process queries and generate responses

**Key Functions**:
- Receive and parse queries
- Build context from retrieved documents
- Call LLM for response generation
- Track token usage
- Handle response formatting

**Tech Stack**: LangChain, OpenAI/Anthropic, FastAPI

### 7. Evaluation Service
**Responsibility**: Evaluate result quality

**Key Functions**:
- Calculate evaluation metrics
- Store feedback and ratings
- Track system performance
- Generate quality reports

**Tech Stack**: RAGAS, Pandas, MongoDB

## Data Flow

### Document Upload & Indexing Flow

```
1. User uploads document
   ↓
2. Ingestion Service stores in S3, publishes to SQS
   ↓
3. Parsing Service consumes message, extracts text
   ↓
4. Creates chunks with metadata
   ↓
5. Embedding Service generates vectors
   ↓
6. Retrieval Service indexes in vector DB
   ↓
7. Document marked as INDEXED in MongoDB
```

### Query & Response Flow

```
1. User submits query
   ↓
2. Query Processing Service receives query
   ↓
3. Calls Embedding Service for query embedding
   ↓
4. Retrieval Service searches vector DB
   ↓
5. Agent Orchestration Service builds workflow state
   ↓
6. Multiple agents process retrieved context
   ↓
7. LLM generates response
   ↓
8. Evaluation Service computes metrics
   ↓
9. Response returned to user
```

## State Management

### Workflow State (LangGraph)

```python
class WorkflowState:
    workflow_id: str
    query: Query
    retrieved_documents: List[RetrievedDocument]
    agent_states: Dict[str, AgentState]
    current_stage: str
    intermediate_results: Dict
    final_answer: Optional[str]
    token_count: int
```

### Agent State

```python
class AgentState:
    agent_id: str
    agent_role: AgentRole
    status: str  # active, idle, paused, error
    current_task: Optional[str]
    memory: Dict  # Agent memory for context
    tools_available: List[str]
    performance_metrics: Dict
```

## Scalability Considerations

### Horizontal Scaling
- Each service can be scaled independently based on load
- Services are stateless (state in Redis/MongoDB)
- Load balancing via API Gateway (Nginx)

### Vertical Scaling
- Increase CPU/memory for resource-intensive services
- Embedding Service benefits from GPU acceleration
- Retrieval Service benefits from larger cache

### Performance Optimization
- Redis caching for frequently accessed data
- Batch processing for embeddings
- Connection pooling to databases
- Async/await for I/O operations

## Security Architecture

### API Security
- JWT authentication
- API key validation
- Rate limiting per service
- Request validation (Pydantic)

### Data Security
- Encryption at rest (S3, databases)
- Encryption in transit (HTTPS)
- Database credentials from environment variables
- Audit logging for all operations

### Network Security
- VPC isolation
- Security groups for inter-service communication
- Private subnets for databases
- Public ALB for API Gateway only

## Observability Stack

### Metrics (Prometheus)
- HTTP latency histograms
- Error rates by service
- Token usage tracking
- Cache hit/miss rates
- Document processing metrics

### Tracing (Jaeger)
- Distributed request tracing
- Service-to-service latency
- Error tracking with context
- Span annotations for business logic

### Logging (ELK Stack)
- Structured JSON logging
- Centralized log aggregation
- Full-text search capabilities
- Alert on error patterns

### Dashboards (Grafana)
- Service health overview
- Performance trends
- Cost analysis
- Custom business metrics

## High Availability Strategy

### Service Redundancy
- Multiple replicas per service (Kubernetes)
- Health checks and auto-recovery
- Rolling updates for zero downtime

### Data Redundancy
- MongoDB replication
- Redis persistence options
- S3 cross-region replication
- Vector DB backup strategies

### Disaster Recovery
- Database snapshots
- S3 versioning enabled
- Infrastructure as Code for quick recovery
- Multi-region deployment capability

## Cost Optimization

### Resource Efficiency
- Right-sizing compute resources
- Spot instances for non-critical workloads
- Reserved instances for predictable load
- Auto-scaling based on metrics

### API Cost Management
- Token tracking per operation
- Batch requests to LLM APIs
- Caching to reduce API calls
- Local model options where applicable

---

For deployment guidance, see [DEPLOYMENT.md](DEPLOYMENT.md)
