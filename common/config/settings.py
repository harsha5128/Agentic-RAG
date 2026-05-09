"""
Configuration settings for Agentic RAG Platform
Using Pydantic Settings for environment variable management
"""

from enum import Enum
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Environment(str, Enum):
    """Environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class VectorDBType(str, Enum):
    """Supported vector database types"""
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    MILVUS = "milvus"


class MemoryType(str, Enum):
    """Memory backend types"""
    REDIS = "redis"
    MONGODB = "mongodb"


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ============================================
    # Service Configuration
    # ============================================
    SERVICE_NAME: str = Field(default="agentic-rag", description="Service name")
    SERVICE_VERSION: str = Field(default="1.0.0", description="Service version")
    ENVIRONMENT: Environment = Field(default=Environment.DEVELOPMENT, description="Environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    DEBUG: bool = Field(default=False, description="Debug mode")
    
    # ============================================
    # API Keys and Credentials
    # ============================================
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API key")
    PINECONE_API_KEY: Optional[str] = Field(default=None, description="Pinecone API key")
    PINECONE_ENVIRONMENT: Optional[str] = Field(default=None, description="Pinecone environment")
    
    # ============================================
    # AWS Configuration
    # ============================================
    AWS_REGION: str = Field(default="us-east-1", description="AWS region")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, description="AWS access key")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, description="AWS secret key")
    AWS_SQS_QUEUE_URL: Optional[str] = Field(default=None, description="SQS queue URL")
    S3_BUCKET_NAME: str = Field(default="rag-documents", description="S3 bucket name")
    
    # ============================================
    # Database Configuration
    # ============================================
    MONGODB_URI: str = Field(
        default="mongodb://admin:changeme@localhost:27017/rag_db?authSource=admin",
        description="MongoDB connection URI"
    )
    MONGODB_DATABASE: str = Field(default="rag_db", description="MongoDB database name")
    
    # ============================================
    # Redis Configuration
    # ============================================
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_PASSWORD: str = Field(default="redispass123", description="Redis password")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    
    # ============================================
    # RabbitMQ Configuration
    # ============================================
    RABBITMQ_HOST: str = Field(default="localhost", description="RabbitMQ host")
    RABBITMQ_PORT: int = Field(default=5672, description="RabbitMQ port")
    RABBITMQ_USER: str = Field(default="admin", description="RabbitMQ user")
    RABBITMQ_PASSWORD: str = Field(default="rabbitmqpass123", description="RabbitMQ password")
    RABBITMQ_VHOST: str = Field(default="/", description="RabbitMQ virtual host")
    
    # ============================================
    # Vector Database Configuration
    # ============================================
    VECTOR_DB_TYPE: VectorDBType = Field(default=VectorDBType.PINECONE, description="Vector DB type")
    VECTOR_DB_DIMENSION: int = Field(default=1536, description="Vector dimension")
    WEAVIATE_URL: Optional[str] = Field(default=None, description="Weaviate URL")
    MILVUS_HOST: Optional[str] = Field(default=None, description="Milvus host")
    MILVUS_PORT: Optional[int] = Field(default=19530, description="Milvus port")
    
    # ============================================
    # Observability and Monitoring
    # ============================================
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(default="http://localhost:4317", description="OTEL endpoint")
    JAEGER_AGENT_HOST: str = Field(default="localhost", description="Jaeger agent host")
    JAEGER_AGENT_PORT: int = Field(default=6831, description="Jaeger agent port")
    PROMETHEUS_PUSHGATEWAY_URL: Optional[str] = Field(default=None, description="Prometheus pushgateway")
    OPENSEARCH_HOST: str = Field(default="localhost", description="OpenSearch host")
    OPENSEARCH_PORT: int = Field(default=9200, description="OpenSearch port")
    OPENSEARCH_USER: str = Field(default="admin", description="OpenSearch user")
    OPENSEARCH_PASSWORD: str = Field(default="admin", description="OpenSearch password")
    
    # ============================================
    # Document Processing
    # ============================================
    MAX_FILE_SIZE_MB: int = Field(default=100, description="Max file size in MB")
    SUPPORTED_FORMATS: str = Field(
        default="pdf,docx,xlsx,csv,txt,jpg,png",
        description="Supported file formats"
    )
    OCR_ENABLED: bool = Field(default=True, description="Enable OCR")
    MULTILINGUAL_SUPPORT: bool = Field(default=True, description="Enable multilingual support")
    
    # ============================================
    # Agentic Configuration
    # ============================================
    MAX_AGENTS: int = Field(default=10, description="Maximum number of agents")
    AGENT_TIMEOUT_SECONDS: int = Field(default=300, description="Agent timeout in seconds")
    STATE_PERSISTENCE_ENABLED: bool = Field(default=True, description="Enable state persistence")
    MEMORY_TYPE: MemoryType = Field(default=MemoryType.REDIS, description="Memory backend type")
    MEMORY_LAST_K: int = Field(default=5, description="Number of recent memories to inject")
    AGENT_ORCHESTRATION_URL: str = Field(default="http://localhost:8005", description="Agent Orchestration Service URL")
    EVALUATION_SERVICE_URL: str = Field(default="http://localhost:8007", description="Evaluation Service URL")
    EMBEDDING_SERVICE_URL: str = Field(default="http://localhost:8003", description="Embedding Service URL")
    RETRIEVAL_SERVICE_URL: str = Field(default="http://localhost:8004", description="Retrieval Service URL")
    
    # ============================================
    # LLM Configuration
    # ============================================
    LLM_MODEL_NAME: str = Field(default="gpt-4-turbo-preview", description="LLM model name")
    EMBEDDING_MODEL_NAME: str = Field(default="text-embedding-3-large", description="Embedding model")
    MAX_TOKENS: int = Field(default=4096, description="Max tokens for LLM")
    TEMPERATURE: float = Field(default=0.7, description="Temperature for LLM")
    TOP_P: float = Field(default=0.9, description="Top P for LLM")
    
    # ============================================
    # RAG Configuration
    # ============================================
    CHUNK_SIZE: int = Field(default=512, description="Document chunk size")
    CHUNK_OVERLAP: int = Field(default=100, description="Chunk overlap")
    RETRIEVAL_K: int = Field(default=5, description="Number of retrieved documents")
    RERANKER_ENABLED: bool = Field(default=True, description="Enable reranker")
    
    # ============================================
    # Performance and Caching
    # ============================================
    CACHE_TTL_SECONDS: int = Field(default=3600, description="Cache TTL in seconds")
    CACHE_ENABLED: bool = Field(default=True, description="Enable caching")
    BATCH_SIZE: int = Field(default=32, description="Batch size for processing")
    
    # ============================================
    # Security
    # ============================================
    JWT_SECRET_KEY: str = Field(default="your-secret-key-change-in-production", description="JWT secret")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    API_KEY_AUTH_ENABLED: bool = Field(default=True, description="Enable API key auth")
    
    # ============================================
    # DVC Configuration
    # ============================================
    DVC_REMOTE: str = Field(default="s3", description="DVC remote type")
    DVC_S3_ENDPOINTURL: Optional[str] = Field(default=None, description="DVC S3 endpoint")
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL"""
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def rabbitmq_url(self) -> str:
        """Construct RabbitMQ URL"""
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{self.RABBITMQ_VHOST}"
    
    @property
    def opensearch_url(self) -> str:
        """Construct OpenSearch URL"""
        return f"https://{self.OPENSEARCH_USER}:{self.OPENSEARCH_PASSWORD}@{self.OPENSEARCH_HOST}:{self.OPENSEARCH_PORT}"
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT == Environment.DEVELOPMENT


# Global settings instance
settings = Settings()
