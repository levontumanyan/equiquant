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
