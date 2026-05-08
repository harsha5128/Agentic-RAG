#!/usr/bin/env python3
"""
Agentic RAG Platform - Application entry point and configuration
"""

import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

__version__ = "1.0.0"
__app_name__ = "Agentic RAG Platform"
__author__ = "RAG Team"

# Import core modules
from common.config import settings
from common.observability import setup_logging, setup_tracing

# Configure logging and tracing at module load time
setup_logging(settings.LOG_LEVEL)
setup_tracing(settings.SERVICE_NAME, settings.ENVIRONMENT)
