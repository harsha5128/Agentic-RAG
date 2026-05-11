# Agent Orchestration Service

This service orchestrates AI agents for complex query processing using various agent frameworks.

## Supported Frameworks

- LangGraph for workflow orchestration
- CrewAI for role-based agents
- AutoGen for multi-agent conversations
- LangChain for tool integration

## Development Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set API keys for LLM providers (OpenAI, Anthropic)

3. Run the service:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

- `POST /orchestrate`: Execute agent workflow
- `GET /agents`: List available agents
- `GET /health`: Health check

## Features

- Multi-framework agent support
- Tool calling capabilities
- Workflow state management