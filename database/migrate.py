"""Safe, idempotent SQL migration runner.

* Never drops the database or existing tables.
* Each migration is applied once and recorded in schema_migrations.
* Creates a timestamped mysqldump backup before the first change.
* Migrates legacy plaintext PINs to bcrypt hashes and clears the PIN column.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import bcrypt
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = Path(__file__).resolve().parent / "migrations"
BACKUPS = Path(__file__).resolve().parent / "backups"
load_dotenv(ROOT / ".env")

DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "bremer"),
    "charset": "utf8mb4",
}


def connect() -> pymysql.connections.Connection:
    return pymysql.connect(**DB, autocommit=True)


def split_statements(sql: str) -> list[str]:
    """Split on semicolons while respecting quotes and comments."""
    statements: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    escaped = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                buffer.append(ch)
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            buffer.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                if nxt == quote:  # doubled quote
                    buffer.append(nxt)
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            buffer.append(ch)
            i += 1
            continue
        if ch == "-" and nxt == "-":
            in_line_comment = True
            i += 2
            continue
        if ch == "#":
            in_line_comment = True
            i += 1
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            i += 1
            continue
        buffer.append(ch)
        i += 1
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def backup() -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUPS / f"bremer_pre_migration_{stamp}.sql"
    mysqldump = os.getenv("MYSQLDUMP_BIN", r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe")
    if not Path(mysqldump).exists():
        mysqldump = "mysqldump"
    cmd = [
        mysqldump,
        f"--host={DB['host']}",
        f"--port={DB['port']}",
        f"--user={DB['user']}",
        f"--password={DB['password']}",
        "--default-character-set=utf8mb4",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--databases",
        DB["database"],
    ]
    with target.open("wb") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"Backup failed: {proc.stderr.decode(errors='replace')}")
    return target


def ensure_history(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version VARCHAR(120) PRIMARY KEY,
              applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              checksum CHAR(64) NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )


def applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def migrate_legacy_pins(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM users LIKE 'pin_hash'")
        if not cur.fetchone():
            return 0
        cur.execute(
            "SELECT user_id, pin_code FROM users "
            "WHERE pin_code IS NOT NULL AND pin_code <> '' AND (pin_hash IS NULL OR pin_hash = '')"
        )
        rows = cur.fetchall()
        for user_id, pin in rows:
            hashed = bcrypt.hashpw(("pin:" + str(pin)).encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "UPDATE users SET pin_hash = %s, pin_code = NULL WHERE user_id = %s",
                (hashed, user_id),
            )
        return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = sorted(MIGRATIONS.glob("*.sql"))
    conn = connect()
    ensure_history(conn)
    done = applied_versions(conn)
    pending = [f for f in files if f.name not in done]
    print(f"Database: {DB['database']}@ {DB['host']}:{DB['port']}")
    print(f"Applied: {len(done)} | Pending: {len(pending)}")
    if not pending:
        print("Nothing to migrate.")
        return 0
    if args.dry_run:
        for f in pending:
            print(" would apply", f.name)
        return 0

    if not args.no_backup:
        path = backup()
        print("Backup:", path)

    for path in pending:
        sql = path.read_text(encoding="utf-8")
        print("Applying", path.name, "...")
        try:
            with conn.cursor() as cur:
                for statement in split_statements(sql):
                    cur.execute(statement)
            with conn.cursor() as cur:
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            print("  OK")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}")
            raise
    pins = migrate_legacy_pins(conn)
    print(f"Legacy PINs migrated to bcrypt: {pins}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
