"""
Structured JSON Pipeline Logger.

Emits JSON-formatted log lines to stdout and optionally to a file.
Fields per log line: pipeline_name, stage, batch_id, timestamp, row_count, status, duration_ms
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": getattr(record, "levelname", "INFO"),
            "logger": record.name,
        }

        # Parse structured fields from the message
        if hasattr(record, "pipeline_name"):
            log_entry["pipeline_name"] = record.pipeline_name
        if hasattr(record, "stage"):
            log_entry["stage"] = record.stage
        if hasattr(record, "batch_id"):
            log_entry["batch_id"] = record.batch_id
        if hasattr(record, "row_count"):
            log_entry["row_count"] = record.row_count
        if hasattr(record, "status"):
            log_entry["status"] = record.status
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # Include any extra fields
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)

        if record.getMessage():
            log_entry["message"] = record.getMessage()

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class PipelineLogger:
    """Logger wrapper with structured fields per pipeline stage."""

    def __init__(
        self,
        name: str = "elyssa_imdb",
        pipeline_name: str = "imdb_pipeline",
        log_file: Optional[str] = None,
    ):
        self.logger = logging.getLogger(name)
        self.pipeline_name = pipeline_name
        self.logger.setLevel(logging.INFO)

        # Avoid duplicate handlers on re-init
        if not self.logger.handlers:
            # Stdout handler with JSON formatting
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(JSONFormatter())
            self.logger.addHandler(stdout_handler)

            # Optional file handler
            if log_file:
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(JSONFormatter())
                self.logger.addHandler(file_handler)

    def log_stage(
        self,
        stage: str,
        batch_id: str = "",
        status: str = "started",
        row_count: int = 0,
        duration_ms: int = 0,
        message: str = "",
    ):
        """Emit a structured pipeline log line."""
        self._emit(
            stage=stage,
            batch_id=batch_id,
            status=status,
            row_count=row_count,
            duration_ms=duration_ms,
            message=message,
        )

    def log_error(
        self,
        stage: str,
        error: str,
        batch_id: str = "",
    ):
        """Emit a structured error log line."""
        self._emit(
            stage=stage,
            batch_id=batch_id,
            status="error",
            message=error,
        )

    def log_warn(
        self,
        stage: str,
        message: str,
        batch_id: str = "",
    ):
        """Emit a structured warning log line."""
        self._emit(
            stage=stage,
            batch_id=batch_id,
            status="warn",
            message=message,
        )

    def _emit(
        self,
        stage: str,
        batch_id: str = "",
        status: str = "info",
        row_count: int = 0,
        duration_ms: int = 0,
        message: str = "",
    ):
        """Internal structured emit."""
        extra = {
            "pipeline_name": self.pipeline_name,
            "stage": stage,
            "batch_id": batch_id,
            "status": status,
            "row_count": row_count,
            "duration_ms": duration_ms,
            "message": message,
        }
        level_map = {"error": logging.ERROR, "warn": logging.WARNING}
        level = level_map.get(status, logging.INFO)

        record = logging.LogRecord(
            name=self.logger.name,
            level=level,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        # Attach structured fields
        for k, v in extra.items():
            setattr(record, k, v)
        self.logger.handle(record)


# Singleton instance
_logger: Optional[PipelineLogger] = None


def get_logger(pipeline_name: str = "imdb_pipeline", log_file: Optional[str] = None) -> PipelineLogger:
    """Get or create the singleton PipelineLogger."""
    global _logger
    if _logger is None:
        _logger = PipelineLogger(pipeline_name=pipeline_name, log_file=log_file)
    return _logger


def reset_logger():
    """Reset the singleton (for testing)."""
    global _logger
    _logger = None
