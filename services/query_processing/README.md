# Query Processing Service

This service implements the complete RAG (Retrieval-Augmented Generation) pipeline.

## Architecture Components

- Query Processor: Main orchestration
- Context Manager: Retrieval and ranking
- Prompt Builder: Query enhancement
- Agent Orchestrator: Multi-agent processing
- Memory Manager: Conversation history
- Cache Manager: Multi-level caching
- Self-RAG Evaluator: Response quality assessment

## Development Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure all service URLs and API keys

3. Run the service:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

- `POST /query`: Process a user query
- `GET /history/{session_id}`: Get conversation history
- `GET /health`: Health check

## Features

- End-to-end RAG pipeline
- Agentic query enhancement
- Multi-level caching
- Self-evaluation of responses