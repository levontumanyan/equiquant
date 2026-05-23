import logging

from core.logger import setup_logging


def test_setup_logging_basic():
	"""Verify basic logging setup with file handler."""
	setup_logging(verbose=False)
	root_logger = logging.getLogger()

	# Should have at least the FileHandler
	handlers = root_logger.handlers
	assert any(isinstance(h, logging.FileHandler) for h in handlers)

	# We want to ensure OUR StreamHandler (logging.StreamHandler) isn't there.
	# Pytest might add its own LogCaptureHandler which might inherit from StreamHandler.
	# So we check for EXACT type or exclusion of our specific setup.
	our_stream_handlers = [h for h in handlers if type(h) is logging.StreamHandler]
	assert len(our_stream_handlers) == 0


def test_setup_logging_verbose():
	"""Verify verbose mode adds a StreamHandler."""
	setup_logging(verbose=True)
	root_logger = logging.getLogger()

	handlers = root_logger.handlers
	our_stream_handlers = [h for h in handlers if type(h) is logging.StreamHandler]
	assert len(our_stream_handlers) == 1


def test_setup_logging_force_console():
	"""Verify force_console adds a StreamHandler even if verbose is False."""
	setup_logging(verbose=False, force_console=True)
	root_logger = logging.getLogger()

	handlers = root_logger.handlers
	our_stream_handlers = [h for h in handlers if type(h) is logging.StreamHandler]
	assert len(our_stream_handlers) == 1


def test_setup_logging_idempotency():
	"""Verify setup_logging clears previous handlers."""
	setup_logging(verbose=True)
	initial_count = len(logging.getLogger().handlers)

	# Run again, count should be the same (not doubled)
	setup_logging(verbose=True)
	assert len(logging.getLogger().handlers) == initial_count


def test_log_queue_dispatcher():
	"""Verify LogQueueDispatcher dispatches records to the correct logger."""
	from unittest.mock import MagicMock, patch

	from core.logger import LogQueueDispatcher

	dispatcher = LogQueueDispatcher()
	record = logging.LogRecord(
		name="test_logger",
		level=logging.INFO,
		pathname="test_file.py",
		lineno=10,
		msg="Test log message",
		args=(),
		exc_info=None,
	)

	with patch("logging.getLogger") as mock_get_logger:
		mock_logger = MagicMock()
		mock_get_logger.return_value = mock_logger

		dispatcher.emit(record)

		mock_get_logger.assert_called_once_with("test_logger")
		mock_logger.handle.assert_called_once_with(record)
