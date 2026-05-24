#!/usr/bin/env bash
# Usage: restore.sh [FILE]
# Restores equiquant.db from FILE, or auto-selects the latest backup in BACKUP_DIR.
# Prompts for confirmation before overwriting the live database.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="$PROJECT_ROOT/equiquant.db"

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"

if [ -z "${1:-}" ]; then
	FILE=$(ls -t "$BACKUP_DIR"/equiquant_*.db 2>/dev/null | head -1)
	if [ -z "$FILE" ]; then
		echo "No backups found in $BACKUP_DIR. Usage: restore.sh path/to/backup.db" >&2
		exit 1
	fi
else
	FILE="$1"
fi

if [ ! -f "$FILE" ]; then
	echo "Error: File '$FILE' not found." >&2
	exit 1
fi

echo "About to restore equiquant.db from: $FILE"
printf "This will overwrite your local database. Continue? [y/N] "
read -r CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
	echo "Restore cancelled."
	exit 0
fi

sqlite3 "$DB_PATH" ".restore '$FILE'"
echo "Database restored successfully from $FILE."
