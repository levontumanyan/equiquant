import subprocess
import sys


def test_cli_help():
	"""Verify that the CLI help command works."""
	result = subprocess.run(
		[sys.executable, "analyze.py", "--help"], capture_output=True, text=True
	)
	assert result.returncode == 0
	assert "Stock & ETF Fundamental Analyzer" in result.stdout


def test_cli_list_profiles():
	"""Verify that the --list-profiles flag works (even if DB is empty)."""
	result = subprocess.run(
		[sys.executable, "analyze.py", "--list-profiles"],
		capture_output=True,
		text=True,
	)
	# Even if DB doesn't exist yet, it should either exit 0 with nothing or create it.
	assert result.returncode == 0
