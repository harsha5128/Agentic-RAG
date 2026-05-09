"""
Document Ingestion Service Core - Business Logic
Handles S3 event processing, deduplication, and SQS publishing
"""

import hashlib
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from urllib.parse import unquote_plus

from common.base_service import BaseService
from common.config import settings
from common.observability import get_logger
from common.schemas import Document, DocumentStatus, DocumentType
from common.exceptions import (
    DocumentIngestionError,
    ErrorCode,
    ValidationError,
)

logger = get_logger(__name__)


class DocumentIngestionServiceCore:
    """
    Core business logic for document ingestion
    - Handles S3 event notifications
    - Extracts document metadata
    - Computes content hashes for deduplication
    - Publishes to SQS for document parsing
    """

    def __init__(self, base_service: BaseService):
        self.base_service = base_service
        self.sqs_queue_url = settings.AWS_SQS_QUEUE_URL

    async def process_s3_event(self, event: Dict[str, Any]) -> List[Document]:
        """Main entry point for processing S3 events"""
        return await self.base_service.with_error_handling(
            self._process_s3_event_impl,
            "process_s3_event",
            event,
        )

    async def _process_s3_event_impl(self, event: Dict[str, Any]) -> List[Document]:
        """Implementation of S3 event processing"""
        try:
            s3_records = self._extract_s3_records(event)
            if not s3_records:
                logger.warning("No S3 records found in event")
                return []

            logger.info(f"Processing {len(s3_records)} S3 record(s)")

            documents = []
            for record in s3_records:
                try:
                    event_name = record.get("eventName", "")
                    if not event_name.startswith("ObjectCreated:"):
                        logger.info(f"Skipping non-create event: {event_name}")
                        continue

                    document = await self._process_s3_object(record)
                    documents.append(document)

                except DocumentIngestionError as e:
                    logger.error(f"Failed to process record: {str(e)}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing record: {str(e)}")
                    continue

            logger.info(f"Successfully ingested {len(documents)} document(s)")
            return documents

        except Exception as e:
            logger.error(f"Error in S3 event processing: {str(e)}")
            raise DocumentIngestionError(
                ErrorCode.INVALID_S3_EVENT,
                "Failed to process S3 event",
                {"original_error": str(e)},
                e,
            )

    async def _process_s3_object(self, record: Dict[str, Any]) -> Document:
        """Process a single S3 object"""
        try:
            bucket = record.get("s3", {}).get("bucket", {}).get("name")
            key = unquote_plus(record.get("s3", {}).get("object", {}).get("key", ""))

            if not bucket or not key:
                raise ValueError("Missing bucket or key in S3 event")

            logger.info(f"Processing S3 object: s3://{bucket}/{key}")

            s3_metadata = self._get_s3_object_metadata(bucket, key)
            content_hash = await self._compute_s3_content_hash(bucket, key)
            is_duplicate = await self._check_duplicate(content_hash, bucket, key)

            if is_duplicate:
                logger.warning(f"Duplicate document detected: {content_hash}")
                raise DocumentIngestionError(
                    ErrorCode.DUPLICATE_DETECTED,
                    "Document already ingested (duplicate hash)",
                    {"content_hash": content_hash},
                )

            document = Document(
                document_id=str(uuid.uuid4()),
                file_name=key.split('/')[-1],
                document_type=self._get_document_type(key),
                status=DocumentStatus.INGESTED,
                metadata={
                    "s3_bucket": bucket,
                    "s3_key": key,
                    "s3_size_bytes": s3_metadata.get("size_bytes"),
                    "s3_etag": s3_metadata.get("etag"),
                    "s3_last_modified": s3_metadata.get("last_modified"),
                    "content_hash": content_hash,
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                },
                source_s3_path=f"s3://{bucket}/{key}",
            )

            await self._store_document_metadata(document)
            await self._publish_to_parsing_queue(document)

            logger.info(f"Successfully ingested document: {document.document_id}")
            return document

        except DocumentIngestionError:
            raise
        except Exception as e:
            logger.error(f"Error processing S3 object: {str(e)}")
            raise DocumentIngestionError(
                ErrorCode.S3_ACCESS_ERROR,
                "Failed to process S3 object",
                {"original_error": str(e)},
                e,
            )

    def _extract_s3_records(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract S3 records from nested event structures (S3, SQS, SNS)"""
        records = event.get("Records", [])
        s3_records = []

        for record in records:
            if "s3" in record:
                s3_records.append(record)
                continue

            sqs_body = record.get("body")
            if sqs_body:
                try:
                    nested_event = json.loads(sqs_body)
                    s3_records.extend(self._extract_s3_records(nested_event))
                    continue
                except json.JSONDecodeError:
                    logger.warning("Failed to parse SQS body")
                    continue

            sns_message = record.get("Sns", {}).get("Message")
            if sns_message:
                try:
                    nested_event = json.loads(sns_message)
                    s3_records.extend(self._extract_s3_records(nested_event))
                    continue
                except json.JSONDecodeError:
                    logger.warning("Failed to parse SNS message")
                    continue

        return s3_records

    def _get_s3_object_metadata(self, bucket: str, key: str) -> Dict[str, Any]:
        """Get object metadata from S3"""
        try:
            response = self.base_service.s3_client.head_object(Bucket=bucket, Key=key)
            return {
                "size_bytes": response.get("ContentLength", 0),
                "etag": response.get("ETag", ""),
                "last_modified": response.get("LastModified", "").isoformat() if response.get("LastModified") else None,
            }
        except Exception as e:
            logger.error(f"Failed to get S3 metadata: {str(e)}")
            return {"size_bytes": 0, "etag": "", "last_modified": None}

    async def _compute_s3_content_hash(self, bucket: str, key: str) -> str:
        """Compute SHA256 hash of S3 object content"""
        try:
            response = self.base_service.s3_client.get_object(Bucket=bucket, Key=key)
            file_bytes = response['Body'].read()
            content_hash = hashlib.sha256(file_bytes).hexdigest()
            logger.info(f"Computed content hash: {content_hash} for s3://{bucket}/{key}")
            return content_hash
        except Exception as e:
            logger.error(f"Failed to compute content hash: {str(e)}")
            raise DocumentIngestionError(
                ErrorCode.HASH_COMPUTATION_FAILED,
                "Failed to compute content hash",
                {"original_error": str(e)},
                e,
            )

    async def _check_duplicate(self, content_hash: str, bucket: str, key: str) -> bool:
        """Check if document with same hash already exists"""
        try:
            async with self.base_service.get_db_session() as db:
                collection = db.get_collection("documents")
                existing_doc = await collection.find_one({
                    "metadata.content_hash": content_hash
                })
                return existing_doc is not None
        except Exception as e:
            logger.error(f"Error checking for duplicates: {str(e)}")
            return False

    async def _store_document_metadata(self, document: Document) -> None:
        """Store document metadata in MongoDB"""
        try:
            async with self.base_service.get_db_session() as db:
                collection = db.get_collection("documents")
                await collection.insert_one(document.model_dump())
                logger.info(f"Stored document metadata: {document.document_id}")
        except Exception as e:
            logger.error(f"Failed to store metadata: {str(e)}")
            raise

    async def _publish_to_parsing_queue(self, document: Document) -> None:
        """Publish to SQS for parsing"""
        try:
            document_type = (
                document.document_type.value
                if hasattr(document.document_type, "value")
                else str(document.document_type)
            )
            message_body = {
                "document_id": document.document_id,
                "file_name": document.file_name,
                "document_type": document_type,
                "s3_path": document.source_s3_path,
                "metadata": document.metadata,
                "ingestion_timestamp": datetime.utcnow().isoformat(),
            }

            self.base_service.sqs_client.send_message(
                QueueUrl=self.sqs_queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    "document_id": {
                        "StringValue": document.document_id,
                        "DataType": "String",
                    },
                    "document_type": {
                        "StringValue": document_type,
                        "DataType": "String",
                    },
                },
            )
            logger.info(f"Published to SQS: {document.document_id}")
        except Exception as e:
            logger.error(f"Failed to publish to SQS: {str(e)}")
            raise DocumentIngestionError(
                ErrorCode.S3_ACCESS_ERROR,
                "Failed to publish to SQS",
                {"original_error": str(e)},
                e,
            )

    def _get_document_type(self, file_name: str) -> DocumentType:
        """Determine document type from file extension"""
        extension = file_name.split('.')[-1].lower()

        type_mapping = {
            'pdf': DocumentType.PDF,
            'docx': DocumentType.DOCX,
            'xlsx': DocumentType.XLSX,
            'csv': DocumentType.CSV,
            'txt': DocumentType.TXT,
            'jpg': DocumentType.IMAGE,
            'jpeg': DocumentType.IMAGE,
            'png': DocumentType.IMAGE,
        }

        return type_mapping.get(extension, DocumentType.TXT)
