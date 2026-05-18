#!/usr/bin/env bash
# DAIMASUsystem DB バックアップ — SQLite WAL-aware backup
#
# 使い方:
#   ./scripts/backup.sh              # ./backups/ に YYYYMMDD-HHMMSS.db で保存
#   ./scripts/backup.sh /path/dir    # 指定ディレクトリに保存
#
# cron 例 (毎日 03:00):
#   0 3 * * * cd /Users/mr.fu/DAIMASUsystem && ./scripts/backup.sh
#
# 復元 (圧縮 .db.gz から):
#   gunzip -c backups/dining-YYYYMMDD-HHMMSS.db.gz > /tmp/restore.db
#   sqlite3 api/dining.db ".restore '/tmp/restore.db'"
#   (もしくは API server を止めてから cp /tmp/restore.db api/dining.db)
#
# 非圧縮版なら:
#   sqlite3 api/dining.db ".restore 'backups/dining-YYYYMMDD-HHMMSS.db'"
#   ただし本スクリプトは保存後すぐ gzip するので通常はこの形式は存在しない。
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# codex P2: DATABASE_URL env を honor。sqlite:///path の形式から path を抽出する。
# DATABASE_URL 未設定なら api/models/database.py の default (<project>/api/dining.db) を使う。
DEFAULT_DB_PATH="${PROJECT_ROOT}/api/dining.db"

if [[ -n "${DATABASE_URL:-}" ]]; then
  case "${DATABASE_URL}" in
    sqlite:///*)
      DB_PATH="${DATABASE_URL#sqlite:///}"
      ;;
    sqlite:*)
      # sqlite:relative_path 形式
      DB_PATH="${DATABASE_URL#sqlite:}"
      ;;
    *)
      echo "[backup] DATABASE_URL='${DATABASE_URL}' is not a SQLite URL; this script only supports sqlite://" >&2
      echo "[backup] Use database-specific backup tools (pg_dump 等) for other engines." >&2
      exit 3
      ;;
  esac
else
  DB_PATH="${DEFAULT_DB_PATH}"
fi
BACKUP_DIR="${1:-${PROJECT_ROOT}/backups}"
MAX_BACKUPS=30  # 30 世代以上は古いものから削除

if [[ ! -f "${DB_PATH}" ]]; then
  echo "[backup] DB not found: ${DB_PATH}" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
TS=$(date -u +%Y%m%d-%H%M%S)
OUT="${BACKUP_DIR}/dining-${TS}.db"

echo "[backup] ${DB_PATH} -> ${OUT}"

# WAL-aware backup using sqlite3 .backup (consistent snapshot, no need to stop server)
sqlite3 "${DB_PATH}" ".backup '${OUT}'"

# Verify backup integrity
INTEGRITY=$(sqlite3 "${OUT}" "PRAGMA integrity_check;")
if [[ "${INTEGRITY}" != "ok" ]]; then
  echo "[backup] integrity check FAILED: ${INTEGRITY}" >&2
  rm -f "${OUT}"
  exit 2
fi

# Compress to save space
gzip -f "${OUT}"
OUT_GZ="${OUT}.gz"
SIZE=$(du -h "${OUT_GZ}" | cut -f1)
echo "[backup] OK: ${OUT_GZ} (${SIZE})"

# Rotate — 30 世代より古いものを消す (BSD xargs 互換、macOS で動かす)
cd "${BACKUP_DIR}"
TO_REMOVE=$(ls -1t dining-*.db.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) || true)
if [[ -n "${TO_REMOVE}" ]]; then
  echo "${TO_REMOVE}" | while IFS= read -r f; do
    [[ -n "${f}" ]] && rm -f -- "${f}"
  done
fi
REMAINING=$(ls -1 dining-*.db.gz 2>/dev/null | wc -l | tr -d ' ')
echo "[backup] kept ${REMAINING} / ${MAX_BACKUPS} backups"
