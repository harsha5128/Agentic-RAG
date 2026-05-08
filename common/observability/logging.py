"""
Observability and logging configuration
"""

import logging
import sys
from typing import Optional
from pythonjsonlogger import jsonlogger
from loguru import logger as loguru_logger
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure logging with both standard logging and loguru
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Remove default handler
    loguru_logger.remove()
    
    # Add stdout handler with JSON formatting for production
    loguru_logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=log_level,
        colorize=True,
    )
    
    # Add JSON logging to stderr for structured logs
    loguru_logger.add(
        sys.stderr,
        format=lambda record: jsonlogger.JsonFormatter().format(
            logging.LogRecord(
                name=record["name"],
                level=record["level"].no,
                pathname=record["file"].path,
                lineno=record["line"],
                msg=record["message"],
                args=(),
                exc_info=None,
            )
        ),
        level=log_level,
        serialize=False,
    )
    
    # Configure standard logging to use loguru
    logging.basicConfig(
        handlers=[logging.StreamHandler(sys.stdout)],
        level=log_level,
        format="%(message)s",
    )
    
    # Bind loguru to standard logging
    for handler in logging.root.handlers:
        handler.setFormatter(logging.Formatter("%(message)s"))


def setup_tracing(
    service_name: str,
    environment: str,
    jaeger_host: str = "localhost",
    jaeger_port: int = 6831,
) -> None:
    """
    Configure OpenTelemetry tracing with Jaeger exporter
    
    Args:
        service_name: Name of the service
        environment: Environment (development, staging, production)
        jaeger_host: Jaeger agent host
        jaeger_port: Jaeger agent port
    """
    # Create Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port,
    )
    
    # Create resource with service name
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        "environment": environment,
    })
    
    # Create and set tracer provider
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    trace.set_tracer_provider(trace_provider)
    
    # Instrument libraries
    FastAPIInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    
    loguru_logger.info(f"Tracing configured for service: {service_name}")


def get_logger(name: str) -> "loguru_logger":
    """
    Get a logger instance with the given name
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return loguru_logger.bind(context=name)


def get_tracer(name: str) -> trace.Tracer:
    """
    Get a tracer instance
    
    Args:
        name: Tracer name (typically __name__)
    
    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)
