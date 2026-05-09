"""
Base Parser Classes for Document Parsing
"""

from typing import Dict, Any, Tuple
from abc import ABC, abstractmethod


class DocumentParser(ABC):
    """Abstract base parser"""

    @abstractmethod
    async def parse(self, file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        Parse document

        Returns:
            Tuple of (content, metadata)
        """
        raise NotImplementedError