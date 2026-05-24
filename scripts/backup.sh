#!/usr/bin/env bash
# Usage: backup.sh [BACKUP_DIR]
# Backs up equiquant.db to BACKUP_DIR (arg > env > ./backups).
# Prints the resulting backup path to stdout on success.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="$PROJECT_ROOT/equiquant.db"

BACKUP_DIR="${1:-${BACKUP_DIR:-$PROJECT_ROOT/backups}}"

if [ ! -f "$DB_PATH" ]; then
	echo "Error: equiquant.db not found at $DB_PATH" >&2
	exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/equiquant_$TIMESTAMP.db"

sqlite3 "$DB_PATH" ".backup '$DEST'"

echo "$DEST"
