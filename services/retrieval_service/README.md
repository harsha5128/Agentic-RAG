# Retrieval Service

This service handles vector search and document retrieval from various vector databases.

## Supported Vector Databases

- Pinecone
- Weaviate
- Milvus

## Development Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure vector database settings in environment variables

3. Run the service:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

- `POST /search`: Perform vector search
- `GET /documents/{id}`: Retrieve document by ID
- `GET /health`: Health check

## Features

- Multi-vector database support
- Redis caching for search results
- Metadata filtering