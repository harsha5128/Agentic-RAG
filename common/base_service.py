"""
Base service class for all microservices
Provides common patterns: dependency management, error handling, lifecycle management
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from contextlib import asynccontextmanager
import boto3
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging

from common.config import settings
from common.observability import get_logger, get_tracer
from common.exceptions import RAGException, ErrorCode, DatabaseError, DependencyError, CacheError


logger = get_logger(__name__)
tracer = get_tracer(__name__)


class ServiceDependency:
    """Represents a service dependency with health check capability"""
    
    def __init__(self, name: str, health_check_fn: Callable):
        self.name = name
        self.health_check_fn = health_check_fn
        self.is_healthy = False
    
    async def check_health(self) -> bool:
        """Check if dependency is healthy"""
        try:
            self.is_healthy = await self.health_check_fn()
            return self.is_healthy
        except Exception as e:
            logger.error(f"Health check failed for {self.name}: {str(e)}")
            self.is_healthy = False
            return False


class BaseService(ABC):
    """
    Base class for all microservices
    Provides: lifecycle management, dependency injection, error handling, observability
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = get_logger(service_name)
        self.tracer = get_tracer(service_name)
        
        # Clients
        self.s3_client = None
        self.sqs_client = None
        self.mongodb_client = None
        self.mongodb_db = None
        self.redis_client = None
        
        # Dependencies
        self.dependencies: Dict[str, ServiceDependency] = {}
        
        # Metrics
        self.metrics = {
            "requests_total": 0,
            "requests_failed": 0,
            "average_latency_ms": 0.0,
        }
    
    async def initialize(self) -> None:
        """Initialize service and all dependencies"""
        try:
            self.logger.info(f"Initializing service: {self.service_name}")
            
            await self._initialize_aws_clients()
            await self._initialize_databases()
            await self._initialize_dependencies()
            
            # Check all dependencies
            await self.check_health()
            
            self.logger.info(f"Service {self.service_name} initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize service: {str(e)}")
            raise DependencyError(
                ErrorCode.DEPENDENCY_UNAVAILABLE,
                f"Failed to initialize {self.service_name}",
                {"original_error": str(e)},
                e,
            )
    
    async def _initialize_aws_clients(self) -> None:
        """Initialize AWS clients"""
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            
            self.sqs_client = boto3.client(
                'sqs',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            
            self.logger.info("AWS clients initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize AWS clients: {str(e)}")
            raise
    
    async def _initialize_databases(self) -> None:
        """Initialize database connections"""
        try:
            # MongoDB
            self.mongodb_client = AsyncIOMotorClient(settings.MONGODB_URI)
            self.mongodb_db = self.mongodb_client[settings.MONGODB_DATABASE]
            
            # Test MongoDB connection
            await self.mongodb_db.admin.command('ping')
            self.logger.info("MongoDB connected")
            
            # Redis
            self.redis_client = await redis.from_url(
                f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                decode_responses=True,
            )
            
            # Test Redis connection
            await self.redis_client.ping()
            self.logger.info("Redis connected")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize databases: {str(e)}")
            raise
    
    async def _initialize_dependencies(self) -> None:
        """Initialize service-specific dependencies (override in subclasses)"""
        pass
    
    async def close(self) -> None:
        """Clean up resources and close connections"""
        try:
            self.logger.info(f"Closing service: {self.service_name}")
            
            if self.redis_client:
                await self.redis_client.close()
            
            if self.mongodb_client:
                self.mongodb_client.close()
            
            self.logger.info(f"Service {self.service_name} closed successfully")
        except Exception as e:
            self.logger.error(f"Error during service shutdown: {str(e)}")
    
    async def check_health(self) -> Dict[str, Any]:
        """Check health of service and dependencies"""
        health_status = {
            "service": self.service_name,
            "healthy": True,
            "dependencies": {},
        }
        
        # Check each dependency
        for dep_name, dependency in self.dependencies.items():
            is_healthy = await dependency.check_health()
            health_status["dependencies"][dep_name] = {
                "healthy": is_healthy,
            }
            if not is_healthy:
                health_status["healthy"] = False
        
        return health_status
    
    async def readiness_probe(self) -> Dict[str, Any]:
        """Check if service is ready to accept requests"""
        health_status = await self.check_health()
        
        return {
            "ready": health_status["healthy"],
            "service": self.service_name,
            "status": health_status,
        }
    
    async def liveness_probe(self) -> Dict[str, Any]:
        """Check if service is alive"""
        return {
            "alive": True,
            "service": self.service_name,
        }
    
    def register_dependency(self, name: str, health_check_fn: Callable) -> None:
        """Register a dependency with health check"""
        self.dependencies[name] = ServiceDependency(name, health_check_fn)
    
    async def with_error_handling(
        self,
        operation_fn: Callable,
        operation_name: str,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute operation with comprehensive error handling and logging
        
        Args:
            operation_fn: Async function to execute
            operation_name: Name of operation for logging
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Result from operation_fn
        
        Raises:
            RAGException: On operation failure
        """
        with self.tracer.start_as_current_span(operation_name):
            try:
                self.logger.info(f"Starting operation: {operation_name}")
                result = await operation_fn(*args, **kwargs)
                self.logger.info(f"Completed operation: {operation_name}")
                return result
            except RAGException:
                raise
            except Exception as e:
                self.logger.error(f"Operation {operation_name} failed: {str(e)}")
                self.metrics["requests_failed"] += 1
                raise
    
    async def get_from_cache(self, key: str) -> Optional[str]:
        """Get value from Redis cache"""
        try:
            if not self.redis_client:
                return None
            return await self.redis_client.get(key)
        except Exception as e:
            self.logger.warning(f"Cache retrieval failed: {str(e)}")
            return None
    
    async def set_in_cache(self, key: str, value: str, ttl_seconds: int = 3600) -> bool:
        """Set value in Redis cache with TTL"""
        try:
            if not self.redis_client:
                return False
            await self.redis_client.setex(key, ttl_seconds, value)
            return True
        except Exception as e:
            self.logger.warning(f"Cache write failed: {str(e)}")
            return False
    
    async def delete_from_cache(self, key: str) -> bool:
        """Delete value from Redis cache"""
        try:
            if not self.redis_client:
                return False
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            self.logger.warning(f"Cache deletion failed: {str(e)}")
            return False
    
    @asynccontextmanager
    async def get_db_session(self):
        """Context manager for database operations with error handling"""
        session = None
        try:
            yield self.mongodb_db
        except Exception as e:
            self.logger.error(f"Database operation failed: {str(e)}")
            raise DatabaseError(
                ErrorCode.DB_OPERATION_FAILED,
                "Database operation failed",
                {"original_error": str(e)},
                e,
            )
