#!/usr/bin/env python3
import subprocess
import sys


def main():
	if len(sys.argv) < 2:
		print("Usage: scripts/db_inspect.py <view>")
		sys.exit(1)

	view = sys.argv[1]
	subprocess.run([sys.executable, "analyze.py", "--db", view])


if __name__ == "__main__":
	main()
