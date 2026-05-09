# Developer Quick Start Guide

## Setting Up Development Environment

### Prerequisites
- Python 3.11+
- MongoDB (local or Atlas)
- Redis (local or cloud)
- AWS credentials (for S3/SQS)
- OpenAI API key

### Installation

```bash
# Clone repository
cd "Agentic RAG"

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

### Running Services Locally

**Start MongoDB and Redis**:
```bash
docker-compose up -d mongo redis
```

**Start Document Ingestion Service**:
```bash
cd services/document_ingestion
uvicorn app.main:app --reload --port 8001
```

**Start Document Parsing Service**:
```bash
cd services/document_parsing
uvicorn app.main:app --reload --port 8002
```

**Start Agent Orchestration Service**:
```bash
cd services/agent_orchestration
uvicorn app.main:app --reload --port 8003
```

### Testing Services

**Check if service is ready**:
```bash
curl http://localhost:8001/ready
curl http://localhost:8002/ready
curl http://localhost:8003/ready
```

**Check service health**:
```bash
curl http://localhost:8001/health
```

## Adding a New Parser to Document Parsing Service

### Step 1: Create Parser Class

```python
# services/document_parsing/app/main.py

class XMLParser(DocumentParser):
    """Parse XML documents"""
    
    async def parse(self, file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
        """Extract text and metadata from XML"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(file_bytes)
            text = self._extract_text_from_xml(root)
            
            metadata = {
                "root_tag": root.tag,
                "element_count": len(list(root.iter())),
                "depth": self._get_xml_depth(root),
            }
            
            return text, metadata
        except Exception as e:
            logger.error(f"XML parsing failed: {str(e)}")
            raise DocumentParsingError(
                ErrorCode.PARSE_FAILED,
                "Failed to parse XML",
                {"original_error": str(e)},
                e,
            )
    
    def _extract_text_from_xml(self, element) -> str:
        """Recursively extract text from XML"""
        text = []
        if element.text and element.text.strip():
            text.append(element.text.strip())
        for child in element:
            text.append(self._extract_text_from_xml(child))
        if element.tail and element.tail.strip():
            text.append(element.tail.strip())
        return "\n".join(filter(None, text))
    
    def _get_xml_depth(self, element, depth=0) -> int:
        """Get depth of XML tree"""
        max_depth = depth
        for child in element:
            child_depth = self._get_xml_depth(child, depth + 1)
            max_depth = max(max_depth, child_depth)
        return max_depth
```

### Step 2: Register Parser

```python
# In DocumentParsingService.__init__()

self.parsers = {
    DocumentType.PDF: PDFParser(),
    DocumentType.DOCX: DOCXParser(),
    DocumentType.XLSX: SpreadsheetParser(),
    DocumentType.CSV: SpreadsheetParser(),
    DocumentType.TXT: TextParser(),
    DocumentType.IMAGE: ImageParser(),
    DocumentType.XML: XMLParser(),  # Add here
}
```

### Step 3: Add Document Type

```python
# common/schemas/workflow.py

class DocumentType(str, Enum):
    """Document type"""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    TXT = "txt"
    IMAGE = "image"
    XML = "xml"  # Add here
```

## Adding a New Tool to Agent Orchestration

### Step 1: Create Tool Function

```python
# In AgentOrchestrationService or separate file

async def search_web(query: str) -> str:
    """Search the web for information"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        # Make API call
        result = await session.get(f"https://api.example.com/search?q={query}")
        return await result.text()
```

### Step 2: Register Tool

```python
# In AgentOrchestrationService._setup_default_tools()

web_search_tool = Tool(
    tool_id="web-search-001",
    tool_name="web_search",
    description="Search the web for information",
    available_for_roles=[AgentRole.RETRIEVER, AgentRole.ANALYZER],
    execute_fn=search_web,
    input_schema={
        "query": {
            "type": "string",
            "description": "Search query"
        }
    },
    output_schema={
        "type": "string",
        "description": "Search results"
    }
)

self.tool_registry.register_tool(web_search_tool)
```

### Step 3: Use Tool in Agent

```python
# Tool is now available for agents with RETRIEVER or ANALYZER role
tools = service.tool_registry.get_tools_for_agent(AgentRole.RETRIEVER)
for tool in tools:
    result = await tool.execute(query="what is RAG?")
```

## Implementing New Service from Scratch

### Template

```python
"""
MyNewService - Production Grade
Description of what this service does
"""

import uuid
from typing import Dict, List, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.base_service import BaseService
from common.config import settings
from common.observability import get_logger
from common.exceptions import RAGException, ErrorCode


logger = get_logger(__name__)


class MyNewService(BaseService):
    """Production-grade implementation"""
    
    def __init__(self):
        super().__init__("my-new-service")
    
    async def _initialize_dependencies(self) -> None:
        """Initialize dependencies"""
        # Register health checks
        self.register_dependency(
            "mongodb",
            lambda: self._check_mongodb_health(),
        )
    
    async def _check_mongodb_health(self) -> bool:
        """Check MongoDB connectivity"""
        try:
            await self.mongodb_db.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {str(e)}")
            return False
    
    async def do_something(self, param: str) -> Dict[str, Any]:
        """Main operation"""
        return await self.with_error_handling(
            self._do_something_impl,
            "do_something",
            param,
        )
    
    async def _do_something_impl(self, param: str) -> Dict[str, Any]:
        """Implementation with error handling"""
        try:
            logger.info(f"Processing: {param}")
            # Your business logic here
            return {"status": "success", "result": None}
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            raise RAGException(
                ErrorCode.INTERNAL_ERROR,
                "Operation failed",
                {"original_error": str(e)},
                e,
            )


# Global service instance
service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycle"""
    global service
    service = MyNewService()
    await service.initialize()
    yield
    await service.close()


app = FastAPI(
    title="My New Service",
    description="Service description",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/operation")
async def operation_endpoint(param: str):
    """Operation endpoint"""
    try:
        result = await service.do_something(param)
        return {"status": "success", **result}
    except RAGException as e:
        logger.error(f"Operation failed: {str(e)}")
        raise HTTPException(status_code=422, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail={"error": "Internal server error"})


@app.get("/health")
async def health_check():
    """Health check"""
    return await service.check_health()


@app.get("/ready")
async def readiness():
    """Readiness probe"""
    return await service.readiness_probe()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8004,
    )
```

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_parsing.py

# Run with coverage
pytest --cov=services

# Run async tests
pytest -v tests/test_async_operations.py
```

## Debugging Tips

### Enable Debug Logging

```python
# In environment variables
LOG_LEVEL=DEBUG

# Or in code
from common.observability import get_logger
logger = get_logger(__name__)
logger.debug(f"Debug info: {value}")
```

### Database Query Debugging

```bash
# Connect to MongoDB
mongosh "mongodb://admin:changeme@localhost:27017/rag_db?authSource=admin"

# List collections
show collections

# Query documents
db.documents.find().limit(5)
db.documents.findOne()
```

### View Service Logs

```bash
# Docker logs
docker logs <container_id>

# Docker logs with follow
docker logs -f <container_id>

# Get last 100 lines
docker logs --tail=100 <container_id>
```

### Health Check Debugging

```bash
# Detailed health check
curl -s http://localhost:8001/health | jq .

# Check readiness
curl -s http://localhost:8001/ready | jq .

# Check liveness
curl -s http://localhost:8001/live | jq .
```

## Common Issues & Solutions

### MongoDB Connection Failed
```bash
# Check if MongoDB is running
docker ps | grep mongo

# Verify connection string
echo $MONGODB_URI

# Test connection
python -c "from pymongo import MongoClient; print(MongoClient('mongodb://...').server_info())"
```

### S3 Authentication Issues
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check S3 bucket access
aws s3 ls s3://your-bucket --region us-east-1
```

### Service Startup Failures
```bash
# Check dependencies are running
docker ps

# View detailed error logs
uvicorn app.main:app --log-level debug

# Check port is not in use
lsof -i :8001  # On Linux/Mac
netstat -ano | findstr :8001  # On Windows
```

## Performance Tuning

### Optimize Chunking
```python
# Adjust chunk size for better performance
CHUNK_SIZE=2048  # Larger chunks = fewer vectors
CHUNK_OVERLAP=256  # More overlap = better context
```

### Enable Caching
```python
# Cache expensive operations
result = await service.get_from_cache("query_hash")
if result:
    return json.loads(result)

# Store result
await service.set_in_cache("query_hash", json.dumps(result), ttl_seconds=3600)
```

### Database Optimization
```python
# Ensure indexes are created
from common.database_models import initialize_all_indexes
async with service.get_db_session() as db:
    await initialize_all_indexes(db)
```

## Code Style Guide

### Follow These Patterns

1. **Async Functions**: Always async unless sync-only operation
2. **Error Handling**: Use custom exceptions with error codes
3. **Logging**: Use logger.info/warning/error with context
4. **Type Hints**: Always include input/output types
5. **Docstrings**: Document functions with examples
6. **Constants**: Use uppercase for module-level constants
7. **Configuration**: Always use environment variables

### Example

```python
async def process_document(
    document_id: str,
    s3_path: str,
) -> Dict[str, Any]:
    """
    Process a document through parsing pipeline
    
    Args:
        document_id: Unique document identifier
        s3_path: S3 path to document (s3://bucket/key)
    
    Returns:
        Dictionary with processing results
    
    Raises:
        DocumentParsingError: If parsing fails
    """
    logger.info(f"Processing document: {document_id}")
    
    try:
        # Implementation
        result = await do_processing(s3_path)
        logger.info(f"Document processed: {document_id}")
        return result
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        raise DocumentParsingError(
            ErrorCode.PARSE_FAILED,
            "Failed to process document",
            {"document_id": document_id},
            e,
        )
```

## Useful Commands

```bash
# Format code
black services/ common/

# Check code style
flake8 services/ common/

# Type checking
mypy services/ common/

# Run all checks
pre-commit run --all-files

# Generate requirements
pip freeze > requirements.txt

# Update dependencies
pip install --upgrade -r requirements.txt
```

## Resources

- FastAPI Docs: https://fastapi.tiangolo.com/
- Pydantic: https://docs.pydantic.dev/latest/
- Motor (Async MongoDB): https://motor.readthedocs.io/
- OpenTelemetry: https://opentelemetry.io/docs/
- Loguru: https://loguru.readthedocs.io/

## Getting Help

1. Check the logs for error messages
2. Review relevant documentation files
3. Check health/readiness endpoints
4. Verify environment variables
5. Test with curl/Postman

Good luck with development! 🚀
