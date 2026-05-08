# Document Ingestion Architecture Explained

## The Problem: Why We Need Message Queues

### Without a Queue System (Synchronous)
```
User uploads PDF
    ↓
App processes it immediately
    ↓
OCR → Chunking → Embedding → Vector DB
    ↓
User waits 2-3 minutes for response
    ↓
Server is blocked during entire process
```

**Issues:**
- User experience is terrible (long wait)
- If process fails halfway, document is lost
- If 100 users upload at same time, server crashes
- Can't retry failed uploads easily
- No history of what failed and why

### With a Queue System (Asynchronous)
```
User uploads PDF
    ↓
App stores it in S3, saves metadata
    ↓
Sends message to queue: "Process document ABC123"
    ↓
Returns immediately: "Your document is queued!"
    ↓
[Background Worker picks up message when ready]
    ↓
OCR → Chunking → Embedding → Vector DB
    ↓
User can check status: "Processing... 40% complete"
```

**Advantages:**
- User gets instant response (UX is great)
- System can handle 1000s of uploads
- Failed uploads can be retried automatically
- Full audit trail of what was processed

---

## Document Ingestion Flow (What We Built)

```
1. UPLOAD PHASE (Synchronous)
   User → FastAPI Endpoint (/ingest)
        → Validate file (size, format)
        → Upload to S3
        → Save metadata to MongoDB
        → Publish message to SQS
        → Return: "Document queued!"

2. QUEUE PHASE (Asynchronous)
   Message waits in SQS queue
   [Can wait minutes, hours, even days]

3. PROCESSING PHASE (When worker is ready)
   Worker 1 picks up message
        → Download from S3
        → Run OCR on PDF
        → Chunk into 512-token pieces
        → Check MongoDB for duplicates (DVC versioning)
        → Skip if identical chunk exists
        → Generate embeddings
        → Store in Pinecone/Weaviate
        → Update MongoDB with status: "Completed"
        → Delete message from queue

4. USER CHECKS STATUS (Any time)
   User → Query MongoDB for document status
        → See: "Processing: 60% complete"
        → Or: "Complete! 145 chunks indexed"
```

---

## SQS vs Kafka vs RabbitMQ: The Comparison

| Feature | SQS | RabbitMQ | Kafka |
|---------|-----|----------|-------|
| **Setup** | AWS managed (1 click) | You install & manage | You install & manage |
| **Learning** | Easy (5 minutes) | Medium (1 hour) | Hard (2-3 hours) |
| **Scale** | Automatic (AWS handles) | Manual (add servers) | Manual (add brokers) |
| **Price** | Pay per message ($0.40 per 1M) | Free (self-hosted) | Free (self-hosted) |
| **Persistence** | 14 days retention | Configurable | Configurable |
| **Message Delivery** | At-least-once | Exactly-once | Exactly-once |
| **Real-time Streaming** | Not ideal | Good | Excellent |
| **Topic Support** | No (only queues) | Yes (exchange + queues) | Yes (topics + partitions) |
| **Complexity** | Very simple | Medium | Complex |

---

## Why We Use Each (In This Architecture)

### SQS for Document Ingestion ✅
**Why SQS?**
- Documents arrive at unpredictable times (not streaming)
- We don't need extreme real-time processing
- We want minimal DevOps overhead
- AWS manages all scaling/failures

**Example use case:**
- Monday 3 PM: 1 document uploaded → SQS handles it
- Tuesday 10 AM: 500 documents uploaded → SQS automatically scales
- Wednesday 2 AM: 0 documents → No costs

**Interview answer:**
"We use SQS for document ingestion because it's cloud-native, requires no infrastructure management, and handles variable document arrival patterns perfectly. Documents can wait in queue without degradation."

### RabbitMQ as Fallback ✅
**Why have RabbitMQ too?**
- Local development: Don't want to use AWS (cost + complexity)
- Air-gapped environments: Can't access AWS
- Private data: Can't send docs to AWS

**In docker-compose.yml:**
```yaml
rabbitmq:
  image: rabbitmq:latest
  # Developers can switch SQS to RabbitMQ in .env
```

**How switching works:**
```env
QUEUE_TYPE=rabbitmq      # Use RabbitMQ locally
# or
QUEUE_TYPE=sqs           # Use AWS SQS in production
```

**Interview answer:**
"We have RabbitMQ as backup for local development and air-gapped deployments where AWS access isn't available."

### Why NOT Kafka?
**When you'd use Kafka:**
- 1000+ documents per second (real-time streaming)
- Need 3+ year data retention
- Build a real-time analytics platform
- Have dedicated DevOps team

**Why we didn't choose Kafka:**
- Document ingestion is batch-oriented, not streaming
- Overkill complexity for our use case
- Too much operational burden
- Kafka is "fire hose" (always running), SQS is "on-demand" (pay for what you use)

**Interview answer:**
"Kafka is excellent for high-throughput streaming scenarios, but document ingestion is typically batch-based with irregular arrivals. SQS is more cost-effective and easier to manage for this use case."

---

## Document Versioning & Deduplication (DVC + MongoDB)

### The Challenge
```
Day 1: Upload "finance_guide_v1.pdf" (100 pages)
       → Generate embeddings (takes 5 minutes)
       → Cost: $2.50 in OpenAI calls

Day 3: Upload "finance_guide_v1.pdf" again (accidental duplicate)
       → Should we re-embed and waste $2.50?
```

### Our Solution

**Step 1: File Hash (DVC)**
```
When document arrives:
1. Calculate MD5 hash of file
2. Store in DVC (version control)
3. Check: "Have we seen this hash before?"
   - Yes? Skip re-processing
   - No? Process it
```

**Step 2: Chunk Deduplication (MongoDB)**
```
After chunking text:
1. Generate hash of each chunk
2. Query MongoDB: "Does this chunk hash exist?"
3. If YES → Skip embedding (save money)
4. If NO → Generate embedding and store

Example:
chunk = "Financial regulations state that..."
hash = sha256(chunk) = "abc123def456"
query = db.chunks.findOne({chunk_hash: "abc123def456"})
```

**Step 3: Full Document Versioning (Git-like)**
```
finance_guide.pdf
├── v1.0 (Jan 1) - 5000 chunks, 450 embeddings generated
├── v1.1 (Feb 15) - Updated, 5200 chunks, 150 new chunks only
├── v2.0 (Mar 20) - Completely revised, 3000 chunks, full re-embed
```

**Interview answer:**
"We use DVC to track file versions and prevent re-processing identical documents. At the chunk level, we calculate hashes and query MongoDB to skip embeddings for duplicate content. This reduces API costs significantly while maintaining freshness."

---

## Handling Bad Documents

### What is a "Bad Document"?

```
1. CORRUPTED PDF
   - Damaged file header
   - Encrypted without password
   - Wrong format (says .pdf but is .zip)

2. SCANNED IMAGE (No text layer)
   - User scanned book with camera
   - OCR fails or gives gibberish
   
3. WRONG CONTENT TYPE
   - Binary file (image/video)
   - Executable (.exe)
   
4. OVERSIZED
   - 500MB file when limit is 100MB

5. LANGUAGE NOT SUPPORTED
   - Mongolian text when we only support English/Spanish
```

### How We Handle Bad Docs

**Stage 1: Upload Validation**
```python
# services/document_ingestion/app/main.py

def validate_document(file):
    # Check 1: File size
    if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise Error("File too large")
    
    # Check 2: File type
    allowed_types = ['.pdf', '.docx', '.xlsx', '.txt', '.png', '.jpg']
    if file.extension not in allowed_types:
        raise Error("Unsupported format")
    
    # Check 3: File header (magic bytes)
    magic_bytes = read_first_bytes(file)
    if not is_valid_pdf(magic_bytes):
        raise Error("File is corrupted")
    
    return "OK"
```

**Stage 2: Processing Failure Handling**
```python
# services/document_parsing/app/main.py

async def parse_document(doc_id):
    try:
        pdf = PyPDF2.PdfReader(file)
        # Extract text
    except Exception as e:
        # Log the error
        log_error(doc_id, str(e))
        
        # Mark in MongoDB
        db.documents.update_one(
            {"_id": doc_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )
        
        # Publish to DLQ (Dead Letter Queue)
        # Re-queue up to 3 times
        if retry_count < 3:
            sqs.send_message(
                Queue="document-parsing-dlq",
                Body=message,
                MessageAttributes={"retry_count": retry_count + 1}
            )
```

**Stage 3: User Notification**
```
User checks status in UI:
✅ Document uploaded
⏳ Processing (20% complete)
❌ FAILED: Corrupted PDF file
    → Reason: "File header invalid"
    → Suggestion: "Try re-uploading or contact support"
```

**Interview answer:**
"We validate documents at upload (file size, format, corruption checks). If processing fails, we catch exceptions, log them, store the error in MongoDB, and optionally retry using a Dead Letter Queue. Users get immediate feedback on failures."

---

## Batch vs Real-Time: When to Use Each

### Batch Processing (Biweekly) ✅
**Use when:**
- Documents arrive in bulk on schedule
- Processing delay of 1-7 days is acceptable
- Want to minimize infrastructure

**Example: Finance Banking Chatbot**
```
Every Monday 9 AM:
- Download all new documents from vendor
- Upload 1000 documents
- SQS queues them
- Processing happens throughout the day
- Available for search by Tuesday morning
```

**Advantages:**
- Single infrastructure (no real-time components)
- Lower costs
- Predictable load

**Problems:**
- If customer asks "What's new in today's policy?" - can't help
- Regulatory docs need faster updates

### Real-Time Processing ✅
**Use when:**
- Documents arrive unpredictably (24/7)
- Need to search new content within minutes
- Can't wait for batch window

**Example: News Aggregator Chatbot**
```
News article published at 2:47 PM
    ↓ (Upload API)
    ↓ (SQS immediately picks it up)
    ↓ 2 minutes later
Available in search results
    ↓
User can ask: "What's the latest on this topic?"
```

**Setup:** Same SQS setup, just no batch window - always processing

### Hybrid Approach ✅✅✅ (What We Recommend for Finance)
```
CRITICAL DOCS (Regulatory, Compliance)
    → Real-time (minutes)
    → Use SQS with priority queue
    
STANDARD DOCS (Policy updates, FAQs)
    → Batch weekly (Mondays)
    → Lower priority queue
    
HISTORICAL DOCS (Archive, old versions)
    → Batch monthly
    → Lowest priority
```

**Interview answer:**
"For finance banking chatbots, we'd recommend a hybrid approach: critical regulatory documents in real-time (SQS priority queue), standard updates on weekly batch, and archives on monthly batch. This balances freshness with cost."

---

## What If We Don't Use Message Queues?

### Scenario 1: Synchronous Only (No Queue)
```
def upload_document(file):
    # Validate
    # Upload to S3
    # Parse immediately ← BLOCKING
    # Generate embeddings ← BLOCKING (5 min wait)
    # Store in DB
    # Return to user

# Problems:
# 1. User waits 5 minutes → 70% abandon
# 2. Server can't handle 100 simultaneous uploads
# 3. One failure crashes entire process
# 4. Can't scale without buying 10x servers
```

### Scenario 2: Using Threads (No Queue)
```
def upload_document(file):
    # Validate and upload to S3
    # Spawn thread for processing
    # Return immediately
    
    # In background thread:
    # Parse → Embed → Store
    # If thread crashes, no retry mechanism
```

**Problems:**
- No persistence (if server crashes, threads die)
- No visibility (user doesn't know status)
- No scaling across servers
- Hard to debug failures

### With SQS (What We Built)
```
def upload_document(file):
    # Validate and upload to S3
    # Publish to SQS
    # Return immediately: "Queued!"

# SQS guarantees:
# ✅ Message persists (14 days)
# ✅ Can scale to 1000s of workers
# ✅ Auto-retry on failure
# ✅ Dead Letter Queue for permanent failures
# ✅ Full audit trail
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    USER                                      │
│              (Web/Mobile/API)                                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓ POST /ingest
         ┌───────────────────┐
         │ API Gateway       │ (Synchronous - FAST)
         │ (FastAPI)         │
         └───────────────────┘
                 │
    ┌────────────┼────────────┐
    ↓            ↓            ↓
┌────────┐  ┌────────┐  ┌────────┐
│Validate│  │Upload  │  │Save    │
│File    │→ │to S3   │→ │Metadata│
└────────┘  └────────┘  └────────┘
                            │
                            ↓
                    ┌───────────────┐
                    │ Publish to    │
                    │ SQS Queue     │ (Asynchronous - SCALABLE)
                    └───────────────┘
                            │
           ┌────────────────┼────────────────┐
           ↓                ↓                ↓
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │Worker 1    │  │Worker 2    │  │Worker N    │
    │Processing  │  │Processing  │  │Processing  │
    └────────────┘  └────────────┘  └────────────┘
           │                ↓                ↓
           └────────────────┼────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
    ┌─────────┐       ┌──────────┐       ┌────────────┐
    │DVC       │       │MongoDB   │       │Pinecone/   │
    │Versioning│       │Chunks    │       │Weaviate    │
    └─────────┘       └──────────┘       └────────────┘
        │
        └──→ ┌───────────────────┐
             │User Status Check  │
             │GET /documents/{id}│
             └───────────────────┘
```

---

## Interview Questions (Prepare These Answers)

### Q1: "How do you handle document uploads at scale?"
**Answer:**
"We use an asynchronous queue-based architecture with SQS. Documents are uploaded to S3 with metadata saved to MongoDB, and then a message is published to SQS. Workers process messages independently, allowing us to scale both document uploads and processing independently. Failed uploads are retried automatically via Dead Letter Queues."

### Q2: "Why not use Kafka?"
**Answer:**
"Kafka is excellent for high-throughput real-time streaming, but document ingestion is typically event-driven with variable arrivals. SQS is more cost-effective, requires no infrastructure management, and automatically scales based on demand. For finance banking use cases where regulatory documents need versioning and deduplication, SQS + MongoDB + DVC is the ideal combination."

### Q3: "How do you prevent duplicate embeddings?"
**Answer:**
"We use a three-layer deduplication strategy. First, DVC tracks file hashes to identify duplicate uploads. Second, after chunking, we generate hashes of each chunk and query MongoDB to skip already-embedded content. Third, we maintain a versioning system so re-uploads of different versions are processed while identical versions are skipped. This significantly reduces API costs."

### Q4: "What happens if a document fails to process?"
**Answer:**
"When processing fails, we catch the exception, log it with full context, and update the document status in MongoDB to 'failed' with the error message. The message is moved to a Dead Letter Queue and retried up to 3 times. If it still fails, it remains in DLQ for manual investigation. Users can check the document status API to see if processing succeeded or what error occurred."

### Q5: "How would you handle a 24/7 finance chatbot needing real-time docs?"
**Answer:**
"I'd implement a hybrid strategy: critical regulatory documents (compliance, policy changes) go through a priority SQS queue with real-time processing (target <5 min), standard documents go through a secondary queue on hourly batches, and historical archives are processed nightly. This balances freshness, cost, and system load. We'd use MongoDB TTL indexes to auto-expire old versions and maintain DVC for audit trails."

---

## Summary Table: When to Use What

| Scenario | Use | Why |
|----------|-----|-----|
| Cloud-based RAG | SQS + S3 + MongoDB | Managed, scalable, cheap |
| Local dev | RabbitMQ + Docker | Free, self-contained |
| Real-time 1000s/sec | Kafka | Streaming backbone |
| Finance banking | Hybrid SQS + Batch | Balance freshness + cost |
| Document versioning | DVC + MongoDB | Dedup + audit trail |
| User experience | Async queue | Fast feedback |

---

## Next: Practical Setup

See `.env` configuration for:
- `QUEUE_TYPE=sqs` or `QUEUE_TYPE=rabbitmq`
- `AWS_SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/...`
- `MONGODB_URI=mongodb://localhost:27017/...`
- `DVC_REMOTE=s3://your-bucket/dvc`

Questions? Ask me about any of these concepts!
