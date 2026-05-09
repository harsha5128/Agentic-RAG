"""
Hash Utilities - Content hashing and deduplication
"""

import hashlib
from typing import Optional, Dict, Any

from common.observability import get_logger

logger = get_logger(__name__)


class HashUtils:
    """Utilities for content hashing and deduplication"""

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Compute SHA256 hash of byte data"""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def compute_md5(data: bytes) -> str:
        """Compute MD5 hash of byte data"""
        return hashlib.md5(data).hexdigest()

    @staticmethod
    async def compute_file_hash(file_bytes: bytes, algorithm: str = "sha256") -> str:
        """
        Compute hash of file content

        Args:
            file_bytes: File content as bytes
            algorithm: Hash algorithm ('sha256', 'md5')

        Returns:
            Hexadecimal hash string
        """
        try:
            if algorithm == "sha256":
                return HashUtils.compute_sha256(file_bytes)
            elif algorithm == "md5":
                return HashUtils.compute_md5(file_bytes)
            else:
                raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        except Exception as e:
            logger.error(f"Hash computation failed: {str(e)}")
            raise

    @staticmethod
    def generate_content_hash(content: str, encoding: str = "utf-8") -> str:
        """Generate hash from string content"""
        try:
            data = content.encode(encoding)
            return HashUtils.compute_sha256(data)
        except Exception as e:
            logger.error(f"Content hash generation failed: {str(e)}")
            raise

    @staticmethod
    def hash_metadata(metadata: Dict[str, Any]) -> str:
        """Generate hash from metadata dictionary"""
        try:
            # Sort keys for consistent hashing
            sorted_metadata = json.dumps(metadata, sort_keys=True)
            return HashUtils.compute_sha256(sorted_metadata.encode())
        except Exception as e:
            logger.error(f"Metadata hash generation failed: {str(e)}")
            raise


class DeduplicationUtils:
    """Utilities for document deduplication"""

    @staticmethod
    async def check_content_duplicate(
        content_hash: str,
        collection,
        exclude_document_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if content hash already exists in database

        Args:
            content_hash: SHA256 hash of content
            collection: MongoDB collection
            exclude_document_id: Document ID to exclude from check

        Returns:
            Existing document if duplicate found, None otherwise
        """
        try:
            query = {"metadata.content_hash": content_hash}
            if exclude_document_id:
                query["document_id"] = {"$ne": exclude_document_id}

            existing_doc = await collection.find_one(query)
            return existing_doc
        except Exception as e:
            logger.error(f"Duplicate check failed: {str(e)}")
            return None

    @staticmethod
    def generate_similarity_hash(content: str, window_size: int = 100) -> str:
        """
        Generate rolling hash for similarity detection

        Args:
            content: Text content
            window_size: Size of rolling window

        Returns:
            Hash representing content similarity
        """
        try:
            # Simple implementation - take hash of first N characters
            window = content[:window_size] if len(content) > window_size else content
            return HashUtils.generate_content_hash(window)
        except Exception as e:
            logger.error(f"Similarity hash generation failed: {str(e)}")
            return ""

    @staticmethod
    def compare_hashes(hash1: str, hash2: str) -> float:
        """
        Compare two hashes for similarity (simple Hamming distance)

        Returns:
            Similarity score between 0 and 1
        """
        try:
            if len(hash1) != len(hash2):
                return 0.0

            # Simple character-by-character comparison
            matches = sum(1 for a, b in zip(hash1, hash2) if a == b)
            return matches / len(hash1)
        except Exception as e:
            logger.error(f"Hash comparison failed: {str(e)}")
            return 0.0