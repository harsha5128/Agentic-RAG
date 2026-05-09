"""
MongoDB database models and schemas
Provides type-safe access to document stores
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pymongo import UpdateOne
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection


class DocumentModel:
    """Document metadata model"""
    
    collection_name = "documents"
    
    @staticmethod
    async def create_indexes(db: AsyncIOMotorDatabase):
        """Create necessary indexes"""
        collection = db[DocumentModel.collection_name]
        
        # Document ID index
        await collection.create_index("document_id", unique=True)
        
        # Content hash index for duplicate detection
        await collection.create_index("metadata.content_hash")
        
        # Status index for filtering
        await collection.create_index("status")
        
        # Creation time index for sorting
        await collection.create_index("created_at")
        
        # Composite index for status and creation time
        await collection.create_index([("status", 1), ("created_at", -1)])
        
        # TTL index for old documents (expire after 90 days)
        await collection.create_index("created_at", expireAfterSeconds=7776000)
    
    @staticmethod
    async def insert_one(db: AsyncIOMotorDatabase, document: Dict[str, Any]) -> str:
        """Insert a document"""
        collection = db[DocumentModel.collection_name]
        result = await collection.insert_one(document)
        return result.inserted_id
    
    @staticmethod
    async def find_by_id(db: AsyncIOMotorDatabase, document_id: str) -> Optional[Dict]:
        """Find document by ID"""
        collection = db[DocumentModel.collection_name]
        return await collection.find_one({"document_id": document_id})
    
    @staticmethod
    async def find_by_hash(db: AsyncIOMotorDatabase, content_hash: str) -> Optional[Dict]:
        """Find document by content hash"""
        collection = db[DocumentModel.collection_name]
        return await collection.find_one({"metadata.content_hash": content_hash})
    
    @staticmethod
    async def update_status(db: AsyncIOMotorDatabase, document_id: str, status: str) -> bool:
        """Update document status"""
        collection = db[DocumentModel.collection_name]
        result = await collection.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    @staticmethod
    async def add_chunks(db: AsyncIOMotorDatabase, document_id: str, chunks: List[str]) -> bool:
        """Add chunks to document"""
        collection = db[DocumentModel.collection_name]
        result = await collection.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "chunks": chunks,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    @staticmethod
    async def add_embeddings(db: AsyncIOMotorDatabase, document_id: str, embeddings: List[List[float]]) -> bool:
        """Add embeddings to document"""
        collection = db[DocumentModel.collection_name]
        result = await collection.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "embeddings": embeddings,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0


class ParsedContentModel:
    """Parsed document content model"""
    
    collection_name = "parsed_contents"
    
    @staticmethod
    async def create_indexes(db: AsyncIOMotorDatabase):
        """Create necessary indexes"""
        collection = db[ParsedContentModel.collection_name]
        
        await collection.create_index("document_id", unique=True)
        await collection.create_index("created_at")
        await collection.create_index("content_hash")  # For deduplication
    
    @staticmethod
    async def insert_one(db: AsyncIOMotorDatabase, parsed_content: Dict[str, Any]) -> str:
        """Insert parsed content"""
        collection = db[ParsedContentModel.collection_name]
        result = await collection.insert_one(parsed_content)
        return result.inserted_id
    
    @staticmethod
    async def find_by_document_id(db: AsyncIOMotorDatabase, document_id: str) -> Optional[Dict]:
        """Find parsed content by document ID"""
        collection = db[ParsedContentModel.collection_name]
        return await collection.find_one({"document_id": document_id})


class WorkflowStateModel:
    """Workflow state model for query processing"""
    
    collection_name = "workflow_states"
    
    @staticmethod
    async def create_indexes(db: AsyncIOMotorDatabase):
        """Create necessary indexes"""
        collection = db[WorkflowStateModel.collection_name]
        
        await collection.create_index("workflow_id", unique=True)
        await collection.create_index("query_id")
        await collection.create_index("created_at")
        await collection.create_index("current_stage")
        
        # TTL index: workflow states expire after 24 hours
        await collection.create_index("created_at", expireAfterSeconds=86400)
    
    @staticmethod
    async def insert_one(db: AsyncIOMotorDatabase, state: Dict[str, Any]) -> str:
        """Insert workflow state"""
        collection = db[WorkflowStateModel.collection_name]
        result = await collection.insert_one(state)
        return result.inserted_id
    
    @staticmethod
    async def find_by_id(db: AsyncIOMotorDatabase, workflow_id: str) -> Optional[Dict]:
        """Find workflow state by ID"""
        collection = db[WorkflowStateModel.collection_name]
        return await collection.find_one({"workflow_id": workflow_id})
    
    @staticmethod
    async def update_stage(db: AsyncIOMotorDatabase, workflow_id: str, stage: str, agent_states: Dict) -> bool:
        """Update workflow stage"""
        collection = db[WorkflowStateModel.collection_name]
        result = await collection.update_one(
            {"workflow_id": workflow_id},
            {
                "$set": {
                    "current_stage": stage,
                    "agent_states": agent_states,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0


class EvaluationMetricsModel:
    """Evaluation metrics model"""
    
    collection_name = "evaluation_metrics"
    
    @staticmethod
    async def create_indexes(db: AsyncIOMotorDatabase):
        """Create necessary indexes"""
        collection = db[EvaluationMetricsModel.collection_name]
        
        await collection.create_index("query_id")
        await collection.create_index("created_at")
        await collection.create_index([("query_id", 1), ("created_at", -1)])
    
    @staticmethod
    async def insert_one(db: AsyncIOMotorDatabase, metrics: Dict[str, Any]) -> str:
        """Insert evaluation metrics"""
        collection = db[EvaluationMetricsModel.collection_name]
        result = await collection.insert_one(metrics)
        return result.inserted_id
    
    @staticmethod
    async def find_by_query_id(db: AsyncIOMotorDatabase, query_id: str) -> List[Dict]:
        """Find metrics by query ID"""
        collection = db[EvaluationMetricsModel.collection_name]
        cursor = collection.find({"query_id": query_id}).sort("created_at", -1)
        return await cursor.to_list(length=100)


class AgentToolRegistryModel:
    """Agent tool registry model"""
    
    collection_name = "agent_tool_registry"
    
    @staticmethod
    async def create_indexes(db: AsyncIOMotorDatabase):
        """Create necessary indexes"""
        collection = db[AgentToolRegistryModel.collection_name]
        
        await collection.create_index("tool_id", unique=True)
        await collection.create_index("tool_name")
        await collection.create_index("agent_role")
    
    @staticmethod
    async def insert_one(db: AsyncIOMotorDatabase, tool: Dict[str, Any]) -> str:
        """Insert tool"""
        collection = db[AgentToolRegistryModel.collection_name]
        result = await collection.insert_one(tool)
        return result.inserted_id
    
    @staticmethod
    async def find_by_agent_role(db: AsyncIOMotorDatabase, agent_role: str) -> List[Dict]:
        """Find tools available for an agent role"""
        collection = db[AgentToolRegistryModel.collection_name]
        cursor = collection.find(
            {
                "agent_role": agent_role,
                "enabled": True
            }
        ).sort("priority", -1)
        return await cursor.to_list(length=50)
    
    @staticmethod
    async def find_by_name(db: AsyncIOMotorDatabase, tool_name: str) -> Optional[Dict]:
        """Find tool by name"""
        collection = db[AgentToolRegistryModel.collection_name]
        return await collection.find_one({"tool_name": tool_name})


class QueryCacheModel:
    """Query cache model (in MongoDB for persistence)"""
    
    collection_name = "query_cache"
    
    @staticmethod
    async def create_indexes(db: AsyncIOMotorDatabase):
        """Create necessary indexes"""
        collection = db[QueryCacheModel.collection_name]
        
        await collection.create_index("query_hash", unique=True)
        await collection.create_index("created_at")
        
        # TTL index: cache expires after 7 days
        await collection.create_index("created_at", expireAfterSeconds=604800)
    
    @staticmethod
    async def find_by_hash(db: AsyncIOMotorDatabase, query_hash: str) -> Optional[Dict]:
        """Find cached result by query hash"""
        collection = db[QueryCacheModel.collection_name]
        return await collection.find_one({"query_hash": query_hash})
    
    @staticmethod
    async def insert_one(db: AsyncIOMotorDatabase, cache_entry: Dict[str, Any]) -> str:
        """Insert cache entry"""
        collection = db[QueryCacheModel.collection_name]
        result = await collection.insert_one(cache_entry)
        return result.inserted_id


async def initialize_all_indexes(db: AsyncIOMotorDatabase):
    """Initialize all database indexes"""
    await DocumentModel.create_indexes(db)
    await ParsedContentModel.create_indexes(db)
    await WorkflowStateModel.create_indexes(db)
    await EvaluationMetricsModel.create_indexes(db)
    await AgentToolRegistryModel.create_indexes(db)
    await QueryCacheModel.create_indexes(db)
