# Contributing to Agentic RAG Platform

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and inclusive in all interactions.

## How to Contribute

### 1. Fork and Clone
```bash
git clone https://github.com/harsha5128/Agentic-RAG.git
cd Agentic-RAG
git checkout -b feature/your-feature-name
```

### 2. Setup Development Environment
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install
```

### 3. Make Changes

#### Code Style
- Follow PEP 8 guidelines
- Use Black for formatting: `black services/`
- Use isort for imports: `isort services/`
- Type hints required for functions

#### Testing
```bash
# Run tests
pytest tests/ -v

# Check coverage
pytest --cov=services --cov-report=html

# Run specific test
pytest tests/test_embedding_service.py::test_generate_embedding -v
```

#### Linting
```bash
flake8 services/
mypy services/
pylint services/
```

### 4. Commit and Push
```bash
git add .
git commit -m "feat: add document versioning support"
git push origin feature/your-feature-name
```

### 5. Create Pull Request
- Fill out the PR template
- Link related issues
- Add description of changes
- Include screenshots if UI changes

## Contribution Areas

### Priority Areas
- [ ] Improving test coverage
- [ ] Performance optimization
- [ ] Documentation improvements
- [ ] Bug fixes
- [ ] New vector database support

### Service-Specific Contributions

#### Document Processing
- [ ] Add new file format support
- [ ] Improve OCR accuracy
- [ ] Better table detection
- [ ] Multilingual improvements

#### Embedding & Retrieval
- [ ] New embedding models
- [ ] Hybrid search improvements
- [ ] Vector DB backends (Weaviate, Milvus)
- [ ] Caching strategies

#### Agentic Features
- [ ] New agent types
- [ ] Tool integrations
- [ ] Memory management
- [ ] Workflow optimization

#### Observability
- [ ] Custom metrics
- [ ] Dashboard templates
- [ ] Alert rules
- [ ] Log analysis

## Pull Request Process

1. **Title Format**: `type(scope): description`
   - Types: feat, fix, docs, style, refactor, test, chore
   - Scope: service name or component
   - Example: `feat(agent-orchestration): add memory persistence`

2. **Description**: Explain the what and why, not the how

3. **Testing**: Include test cases for new features

4. **Documentation**: Update relevant docs

5. **Review**: Respond to feedback promptly

## Development Workflow

### Local Testing

```bash
# Run all tests
pytest tests/

# Run specific service tests
pytest tests/test_embedding_service.py -v

# Run with coverage
pytest --cov=services --cov-report=term-missing
```

### Manual Testing

```bash
# Start services
docker-compose up -d

# Test endpoint
curl http://localhost:8001/health

# Check logs
docker-compose logs -f document-ingestion
```

## Project Structure Conventions

```
services/
├── service_name/
│   ├── __init__.py
│   ├── Dockerfile
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app
│   │   ├── models.py        # Pydantic models
│   │   ├── utils.py         # Helper functions
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── service_routes.py
│   └── tests/
│       ├── __init__.py
│       └── test_service.py
```

## Commit Message Convention

```
<type>(<scope>): <subject>

<body>

<footer>
```

Examples:
```
feat(embedding-service): add Redis caching for embeddings

Add Redis cache layer to reduce API calls and improve performance.
Implements LRU eviction with 1-hour TTL.

Closes #123
```

## Documentation

### Code Comments
```python
def generate_embedding(self, text: str) -> List[float]:
    """
    Generate embedding for text using OpenAI.
    
    Args:
        text: Text to embed
    
    Returns:
        List of float values representing the embedding
    
    Raises:
        ValueError: If text is empty
        OpenAIError: If API call fails
    """
```

### Docstring Format
Use Google-style docstrings for all public methods.

## Testing Guidelines

### Unit Tests
```python
def test_generate_embedding():
    service = EmbeddingService()
    result = service.generate_embedding("test text")
    assert isinstance(result, list)
    assert len(result) == 1536
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_end_to_end_query():
    # Test full query pipeline
    pass
```

## Performance Considerations

- Use async/await for I/O operations
- Implement caching for frequently accessed data
- Profile code for bottlenecks
- Monitor memory usage
- Test with realistic data volumes

## Security Considerations

- Never commit API keys or secrets
- Use environment variables for configuration
- Validate all user inputs
- Use parameterized queries for databases
- Follow OWASP guidelines

## Building and Releasing

### Version Numbering
Use semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Process
```bash
# Update version in pyproject.toml
# Create git tag
git tag v1.2.3
git push origin v1.2.3

# Build and push Docker images
docker build -t image:v1.2.3 .
docker push image:v1.2.3
```

## Getting Help

- 📖 Check [README.md](../README.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
- 💬 Open a Discussion for questions
- 🐛 Create an Issue for bugs
- 👥 Join community Discord

## Reporting Bugs

Include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details
- Relevant logs/screenshots

## Suggesting Features

Include:
- Clear description of the feature
- Use cases and benefits
- Potential implementation approach
- Related issues

---

Thank you for contributing! 🙏
