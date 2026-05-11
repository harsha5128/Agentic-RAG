# Embedding Service

This service generates vector embeddings for text chunks using OpenAI's embedding models.

## Development Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   - `OPENAI_API_KEY`: Your OpenAI API key

3. Run the service:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

- `POST /embed`: Generate embeddings for text
- `GET /health`: Health check

## Features

- OpenAI text-embedding-ada-002 model
- Redis caching for embeddings
- Retry logic with exponential backoff