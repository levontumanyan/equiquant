import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime

from config import ROOT_DIR

LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Determine global log level from environment
DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
level_map = {
	"DEBUG": logging.DEBUG,
	"INFO": logging.INFO,
	"WARNING": logging.WARNING,
	"ERROR": logging.ERROR,
	"CRITICAL": logging.CRITICAL,
}
LOG_LEVEL = level_map.get(DEFAULT_LOG_LEVEL, logging.INFO)

# CLI uses a unique timestamped file per run; server overrides this explicitly
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"run_{RUN_TIMESTAMP}.log"
SERVER_LOG_FILE = LOG_DIR / "server.log"


class JSONFormatter(logging.Formatter):
	"""Formatter that outputs JSON strings after parsing the LogRecord."""

	def format(self, record):
		log_record = {
			"timestamp": datetime.now().isoformat() + "Z",
			"level": record.levelname,
			"name": record.name,
		}

		# If the message is a dict, merge it, otherwise use 'message' key
		if isinstance(record.msg, dict):
			log_record.update(record.msg)
		else:
			log_record["message"] = record.getMessage()

		if record.exc_info:
			log_record["exc_info"] = self.formatException(record.exc_info)
		return json.dumps(log_record)


def setup_logging(
	verbose: bool = False,
	force_console: bool = False,
	log_file=None,
):
	"""
	Initializes the root logger with a file handler and optional console handler.

	Args:
		verbose: Enable DEBUG-level console output.
		force_console: Always attach a console handler.
		log_file: Override the log file path. Defaults to the per-run timestamped
			file (LOG_FILE). Pass SERVER_LOG_FILE for the API server so CLI
			and server logs stay separate.
	"""
	root_logger = logging.getLogger()
	root_logger.setLevel(LOG_LEVEL)

	for handler in root_logger.handlers[:]:
		root_logger.removeHandler(handler)

	target = log_file if log_file is not None else LOG_FILE
	# CLI runs get a plain FileHandler (one file per run).
	# Server gets a RotatingFileHandler (persistent, rolls at 10 MB, keeps 20).
	if log_file is SERVER_LOG_FILE:
		file_handler = logging.handlers.RotatingFileHandler(
			target,
			maxBytes=10 * 1024 * 1024,
			backupCount=20,
			encoding="utf-8",
		)
	else:
		file_handler = logging.FileHandler(target, encoding="utf-8")
	file_handler.setFormatter(JSONFormatter())
	file_handler.setLevel(LOG_LEVEL)
	root_logger.addHandler(file_handler)

	# 2. Console Handler (Only if verbose or forced, standard text for readability)
	if verbose or force_console:
		console_handler = logging.StreamHandler(sys.stdout)
		console_fmt = logging.Formatter(
			"%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
		)
		console_handler.setFormatter(console_fmt)
		# Console shows INFO by default unless LOG_LEVEL is DEBUG
		console_level = min(LOG_LEVEL, logging.INFO)
		console_handler.setLevel(console_level)
		root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
	"""Return a logger with the specified name."""
	return logging.getLogger(name)


def set_log_level(level: str) -> str:
	"""
	Dynamically update the log level for the root logger and all its handlers.

	Args:
		level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL (case-insensitive).

	Returns:
		The normalized level name that was applied.

	Raises:
		ValueError: If the level string is not recognized.
	"""
	normalized = level.upper().strip()
	numeric = level_map.get(normalized)
	if numeric is None:
		raise ValueError(f"Unknown log level: {level!r}. Valid: {list(level_map)}")
	root = logging.getLogger()
	root.setLevel(numeric)
	for handler in root.handlers:
		handler.setLevel(numeric)
	for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
		lg = logging.getLogger(name)
		lg.setLevel(numeric)
		for handler in lg.handlers:
			handler.setLevel(numeric)
	return normalized


class LogQueueDispatcher(logging.Handler):
	"""
	Dispatches log records from a queue back into the main process's logging pipeline.
	"""

	def emit(self, record: logging.LogRecord) -> None:
		"""
		Emit a log record by passing it to the appropriate logger in the main process.

		Args:
			record (logging.LogRecord): The log record to dispatch.
		"""
		logging.getLogger(record.name).handle(record)
