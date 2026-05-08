import sys
from unittest.mock import MagicMock

from analyze import main


def test_cli_background_flag(mocker):
	"""Test that the --background flag triggers daemonize."""
	# Mock sys.argv to simulate command line arguments
	mocker.patch.object(sys, "argv", ["analyze.py", "AAPL", "--background"])

	# Mock dependencies in analyze.py to prevent actual execution
	mocker.patch("analyze.setup_logging")
	mocker.patch("analyze.DatabaseManager")
	mocker.patch("analyze.DatabaseRepository")
	# Mock daemonize to check if it's called
	mock_daemonize = mocker.patch("analyze.daemonize")

	# Mock stats and other logic to prevent errors
	mocker.patch("analyze.run_bulk_analysis", return_value=[])
	mock_stats = mocker.patch("analyze.stats")
	mock_stats.get_total_time.return_value = 0.5

	# Mock display functions
	mocker.patch("analyze.display_run_summary")
	mocker.patch("analyze.display_summary_table")

	# We expect main() to run through and finish
	main()

	# Check if daemonize was called
	mock_daemonize.assert_called_once()


def test_daemonize_logic(mocker):
	"""Test the daemonize function's forking logic (partially)."""
	from analyze import daemonize

	# Mock os.fork
	# To simulate the child process flow, we make fork() return 0
	mock_fork = mocker.patch("os.fork", return_value=0)
	mocker.patch("os.setsid")
	mocker.patch("os.umask")
	mocker.patch("os.dup2")
	mocker.patch("sys.exit")

	# Mock open to avoid actual file operations
	mock_open = mocker.patch("builtins.open")
	mock_file = MagicMock()
	mock_file.fileno.return_value = 10
	mock_open.return_value = mock_file

	# Mock sys.stdin.fileno() etc to avoid pytest issues
	mocker.patch("sys.stdin.fileno", return_value=0)
	mocker.patch("sys.stdout.fileno", return_value=1)
	mocker.patch("sys.stderr.fileno", return_value=2)
	mocker.patch("sys.stdout.flush")
	mocker.patch("sys.stderr.flush")

	# We need to mock LOG_FILE too
	mocker.patch("analyze.LOG_FILE", "test.log")

	daemonize()

	# os.fork should be called twice (double fork)
	assert mock_fork.call_count == 2
