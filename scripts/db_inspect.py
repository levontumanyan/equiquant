#!/usr/bin/env python3
import subprocess  # nosec B404
import sys


def main():
	if len(sys.argv) < 2:
		print("Usage: scripts/db_inspect.py <view>")
		sys.exit(1)

	view = sys.argv[1]
	# B603/B607 safe for local dev script using explicit analyze.py path.
	subprocess.run([sys.executable, "analyze.py", "--db", view])  # nosec B603 B607


if __name__ == "__main__":
	main()
