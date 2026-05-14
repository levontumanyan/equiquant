#!/usr/bin/env python3
import subprocess  # nosec B404
import sys
from pathlib import Path


def main():
	if len(sys.argv) < 2:
		print("Usage: scripts/db_inspect.py <view>")
		sys.exit(1)

	view = sys.argv[1]
	# Resolve absolute path to analyze.py relative to this script
	analyze_path = Path(__file__).parent.parent / "analyze.py"
	# B603/B607 safe for local dev script using explicit absolute path.
	subprocess.run([sys.executable, str(analyze_path), "--db", view])  # nosec B603 B607


if __name__ == "__main__":
	main()
