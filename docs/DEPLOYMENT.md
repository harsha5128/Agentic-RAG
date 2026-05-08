# Deployment Guide

## Prerequisites

- Docker & Docker Compose
- Python 3.10+
- AWS Account with appropriate permissions
- Kubernetes cluster (for production)
- Terraform (for infrastructure)
- Ansible (for server setup)

## Development Deployment

### Local Docker Compose

1. **Setup Environment**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

2. **Start Services**
```bash
docker-compose up -d
```

3. **Verify Deployment**
```bash
# Check service health
for port in 8001 8002 8003 8004 8005 8006 8007; do
  curl http://localhost:$port/health
done

# View logs
docker-compose logs -f
```

4. **Access Services**
- API Gateway: http://localhost:80
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Jaeger: http://localhost:16686
- OpenSearch Dashboards: http://localhost:5601

## Staging Deployment

### Using Kubernetes Locally (Minikube)

```bash
# Start Minikube
minikube start --memory=4096 --cpus=4

# Create namespace
kubectl create namespace agentic-rag

# Deploy services
kubectl apply -f infrastructure/kubernetes/deployment.yaml -n agentic-rag

# Check deployment
kubectl get deployments -n agentic-rag
kubectl get pods -n agentic-rag

# Port forward to test
kubectl port-forward -n agentic-rag svc/embedding-service 8003:80
```

## Production Deployment

### AWS Infrastructure Setup

1. **Provision Infrastructure with Terraform**

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var="environment=production"

# Apply configuration
terraform apply -var="environment=production"

# Save outputs
terraform output > deployment.json
```

2. **Build and Push Docker Images**

```bash
# Create ECR repositories (if not done via Terraform)
aws ecr create-repository --repository-name agentic-rag/document-ingestion

# Build and push images
for service in document-ingestion document-parsing embedding-service retrieval-service agent-orchestration query-processing evaluation-service; do
  docker build -t $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/agentic-rag/$service:latest services/$service
  docker push $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/agentic-rag/$service:latest
done
```

3. **Deploy to ECS**

```bash
# Update task definitions
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Update services
aws ecs update-service --cluster agentic-rag --service document-ingestion --force-new-deployment
```

### Kubernetes Deployment on EKS

1. **Create EKS Cluster**

```bash
# Create cluster (if not using Terraform)
eksctl create cluster \
  --name agentic-rag \
  --region us-east-1 \
  --nodegroup-name ng-1 \
  --node-type t3.medium \
  --nodes 3

# Get kubeconfig
aws eks update-kubeconfig --region us-east-1 --name agentic-rag
```

2. **Deploy Services**

```bash
# Update image references in deployment.yaml
sed -i 's/<ECR_URI>/'"$AWS_ACCOUNT"'.dkr.ecr.us-east-1.amazonaws.com/g' infrastructure/kubernetes/deployment.yaml

# Apply deployment
kubectl apply -f infrastructure/kubernetes/deployment.yaml

# Setup Ingress
kubectl apply -f infrastructure/kubernetes/ingress.yaml
```

3. **Configure Monitoring**

```bash
# Install Prometheus Operator
helm install prometheus prometheus-community/kube-prometheus-stack

# Apply custom dashboards
kubectl apply -f monitoring/grafana-dashboards/
```

### Server Setup with Ansible

1. **Prepare Inventory**

```ini
# inventory.ini
[rag_servers]
prod-server-1 ansible_host=10.0.1.100
prod-server-2 ansible_host=10.0.1.101
prod-server-3 ansible_host=10.0.1.102

[rag_servers:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/key.pem
```

2. **Run Deployment Playbook**

```bash
ansible-playbook infrastructure/ansible/deploy.yml -i inventory.ini
```

3. **Verify Deployment**

```bash
ansible rag_servers -i inventory.ini -m shell -a "docker-compose ps"
```

## Configuration Management

### Environment Variables

1. **Create Secure Secrets Storage**

```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name rag/openai-api-key \
  --secret-string sk-xxxxx

# Kubernetes Secrets
kubectl create secret generic rag-secrets \
  --from-literal=openai-api-key=sk-xxxxx \
  --from-literal=pinecone-api-key=xxxxx \
  -n agentic-rag
```

2. **Load Secrets in Services**

Services should fetch secrets from AWS Secrets Manager or Kubernetes at startup.

## Database Migration

### MongoDB Initialization

```bash
# For local deployment (automatic via init.js)
# For AWS DocumentDB
mongorestore --uri="mongodb://admin:pass@cluster.mongodb.net/rag_db" /path/to/backup
```

### Document Versioning

1. **Initialize DVC**

```bash
dvc init
dvc remote add -d s3 s3://rag-documents/dvc-storage
dvc remote modify s3 endpointurl https://s3.amazonaws.com
```

2. **Track Documents**

```bash
dvc add documents/
git add documents/.gitignore documents.dvc
git commit -m "Track documents with DVC"
```

## Health Checks and Monitoring

### Service Health Verification

```bash
#!/bin/bash
services=("8001" "8002" "8003" "8004" "8005" "8006" "8007")
for port in "${services[@]}"; do
  status=$(curl -s http://localhost:$port/health | jq .status)
  echo "Service on port $port: $status"
done
```

### Monitoring Setup

1. **Prometheus Scrape Targets**: Configured in `monitoring/prometheus.yml`

2. **Grafana Dashboards**: Import from `monitoring/grafana-dashboards/`

3. **Alert Rules**: Configured in `monitoring/alert_rules.yml`

## Backup and Recovery

### Database Backups

```bash
# MongoDB backup
mongodump --uri="mongodb://admin:pass@localhost:27017/rag_db" --out=./backups

# Restore
mongorestore --uri="mongodb://admin:pass@localhost:27017/rag_db" ./backups/rag_db
```

### S3 Backup

```bash
# Enable versioning
aws s3api put-bucket-versioning \
  --bucket rag-documents \
  --versioning-configuration Status=Enabled

# Backup to another bucket
aws s3 sync s3://rag-documents s3://rag-documents-backup
```

## Scaling

### Horizontal Scaling

```bash
# Update replica count in Kubernetes
kubectl set replicas deployment/embedding-service --replicas=5 -n agentic-rag

# Update Docker Compose
docker-compose up -d --scale embedding-service=5
```

### Auto-scaling Configuration

```bash
# Kubernetes HPA
kubectl autoscale deployment embedding-service \
  --min=2 --max=10 \
  --cpu-percent=70 \
  -n agentic-rag
```

## Troubleshooting

### Common Issues

1. **Service won't start**
   - Check logs: `docker-compose logs service-name`
   - Verify environment variables
   - Check database connectivity

2. **High latency**
   - Monitor CPU/Memory usage
   - Check database query performance
   - Review Prometheus metrics

3. **Memory leaks**
   - Monitor memory usage over time
   - Check for unclosed connections
   - Review async/await patterns

### Debug Commands

```bash
# Check service health
curl -v http://localhost:8001/health

# View logs
docker-compose logs -f --tail=100 embedding-service

# Check database
mongosh "mongodb://admin:pass@localhost:27017/rag_db"

# Verify Redis
redis-cli -a redispass123 ping
```

## Performance Tuning

1. **Database Indexing**
   - Ensure proper indexes on MongoDB
   - Monitor query performance

2. **Caching**
   - Configure Redis eviction policies
   - Set appropriate TTLs

3. **Connection Pooling**
   - Configure connection pool sizes
   - Monitor pool utilization

---

For architecture details, see [ARCHITECTURE.md](docs/ARCHITECTURE.md)
