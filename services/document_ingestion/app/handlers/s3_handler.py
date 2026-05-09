"""
S3 Handler Utilities - S3 operations and event processing
"""

from typing import Dict, Any, Optional
import json

from common.observability import get_logger

logger = get_logger(__name__)


class S3EventHandler:
    """Handles S3 event processing and utilities"""

    @staticmethod
    def extract_s3_records(event: Dict[str, Any]) -> list[Dict[str, Any]]:
        """
        Extract S3 records from nested event structures (S3, SQS, SNS)

        Handles:
        - Direct S3 events
        - SQS wrapped S3 events
        - SNS wrapped S3 events
        - Nested combinations
        """
        records = event.get("Records", [])
        s3_records = []

        for record in records:
            # Direct S3 event
            if "s3" in record:
                s3_records.append(record)
                continue

            # SQS wrapped event
            sqs_body = record.get("body")
            if sqs_body:
                try:
                    nested_event = json.loads(sqs_body)
                    s3_records.extend(S3EventHandler.extract_s3_records(nested_event))
                    continue
                except json.JSONDecodeError:
                    logger.warning("Failed to parse SQS body as JSON")
                    continue

            # SNS wrapped event
            sns_message = record.get("Sns", {}).get("Message")
            if sns_message:
                try:
                    nested_event = json.loads(sns_message)
                    s3_records.extend(S3EventHandler.extract_s3_records(nested_event))
                    continue
                except json.JSONDecodeError:
                    logger.warning("Failed to parse SNS message as JSON")
                    continue

        return s3_records

    @staticmethod
    def validate_s3_record(record: Dict[str, Any]) -> bool:
        """Validate that S3 record has required fields"""
        try:
            s3_info = record.get("s3", {})
            bucket = s3_info.get("bucket", {}).get("name")
            key = s3_info.get("object", {}).get("key")

            if not bucket or not key:
                logger.warning("S3 record missing bucket or key")
                return False

            return True
        except Exception as e:
            logger.error(f"Error validating S3 record: {str(e)}")
            return False

    @staticmethod
    def get_event_type(record: Dict[str, Any]) -> str:
        """Get the type of S3 event"""
        return record.get("eventName", "Unknown")

    @staticmethod
    def is_create_event(event_name: str) -> bool:
        """Check if event is an object creation event"""
        return event_name.startswith("ObjectCreated:")

    @staticmethod
    def is_delete_event(event_name: str) -> bool:
        """Check if event is an object deletion event"""
        return event_name.startswith("ObjectRemoved:")


class S3ObjectUtils:
    """Utilities for S3 object operations"""

    @staticmethod
    def get_file_extension(key: str) -> str:
        """Extract file extension from S3 key"""
        parts = key.split('.')
        return parts[-1].lower() if len(parts) > 1 else ""

    @staticmethod
    def get_file_name(key: str) -> str:
        """Extract file name from S3 key"""
        return key.split('/')[-1]

    @staticmethod
    def get_directory_path(key: str) -> str:
        """Extract directory path from S3 key"""
        parts = key.split('/')
        return '/'.join(parts[:-1]) if len(parts) > 1 else ""

    @staticmethod
    def is_valid_file_size(size_bytes: int, max_size: int = 100 * 1024 * 1024) -> bool:
        """Check if file size is within acceptable limits"""
        return 0 < size_bytes <= max_size

    @staticmethod
    def generate_presigned_url(bucket: str, key: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for S3 object (placeholder)"""
        # Implementation would require boto3 client
        # This is a placeholder for future use
        logger.info(f"Would generate presigned URL for s3://{bucket}/{key}")
        return None