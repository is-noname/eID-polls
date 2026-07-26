"""SQLite-Persistenz: Eligibility-Ledger, Vote-Ledger, Board-Hash-Kette.

Datenmodell nach MC-RFC-20260725-001 §6/§9 und dem Prototyp-Fund aus
PROTOTYPE_two-ledger/NOTES.md:

  eligibility  gehashte Pseudonyme - weiss "hat abgeholt", nicht "wie gestimmt"
  spent        verbrauchte Tokens - reiner Doppelabstimmungs-Index, KEINE Stimmen
  board        die Hash-Kette; traegt die Stimmen und ist die einzige
               Auszaehlungsquelle (§7)

Board-Payloads sind kanonisches JSON (sortierte Schluessel, keine Leerzeichen)
statt der String-Zeile des Prototyps. Damit faellt dessen Grenze weg, dass
Optionen kein Leerzeichen, '+' oder '=' enthalten duerfen.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GENESIS = "0" * 64

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS polls (
    poll_id  TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    options  TEXT NOT NULL,
    closed   INTEGER NOT NULL DEFAULT 0,
    created  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eligibility (
    poll_id   TEXT NOT NULL,
    voter_key TEXT NOT NULL,
    PRIMARY KEY (poll_id, voter_key)
);
CREATE TABLE IF NOT EXISTS spent (
    poll_id   TEXT NOT NULL,
    token_hex TEXT NOT NULL,
    PRIMARY KEY (poll_id, token_hex)
);
CREATE TABLE IF NOT EXISTS board (
    poll_id    TEXT NOT NULL,
    idx        INTEGER NOT NULL,
    prev_hash  TEXT NOT NULL,
    payload    TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    PRIMARY KEY (poll_id, idx)
);
"""


def canonical(payload: dict[str, Any]) -> str:
    """Kanonische Serialisierung einer Board-Zeile - Teil des oeffentlichen Boards."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(index: int, prev_hash: str, payload: str) -> str:
    return hashlib.sha256(f"{index}|{prev_hash}|{payload}".encode()).hexdigest()


@dataclass(frozen=True)
class BoardEntry:
    index: int
    prev_hash: str
    payload: str
    entry_hash: str

    @property
    def data(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.payload)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}  # manipulierte Zeile - die Kettenpruefung schlaegt ohnehin an

    @property
    def kind(self) -> str:
        return str(self.data.get("type", "UNPARSEABLE"))


@dataclass(frozen=True)
class PollRow:
    poll_id: str
    question: str
    options: list[str]
    closed: bool
    created: str


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        # WAL statt des Default-Journals: mehrere Teilnehmende schreiben im LAN
        # gleichzeitig (EIP-T-009), ohne WAL wuerde das schnell in "database is
        # locked" enden. busy_timeout laesst SQLite bei kurzer Ueberschneidung
        # warten statt sofort abzubrechen.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        # Alle Threads teilen sich diese eine Verbindung (check_same_thread=False).
        # Deshalb steht auch jeder *Lesezugriff* unter dem Lock, nicht nur die
        # Schreiber: zwei Anfragen gleichzeitig auf derselben Connection liefern
        # sonst vertauschte oder leere Zeilen zurueck - unter Last hiess das
        # "Umfrage gibt es nicht" mitten im Betrieb (EIP-T-019). RLock, damit die
        # zusammengesetzten Operationen in poll_service.py weiter schachteln
        # koennen. Bei der Groessenordnung dieser Umfrage (rund 100 Teilnehmende)
        # kostet die Serialisierung nichts Spuerbares; eine Verbindung pro Thread
        # waere der naechste Schritt, wenn das je knapp wird.
        self.lock = threading.RLock()

    # -- config ------------------------------------------------------------
    def get_config(self, key: str) -> str | None:
        with self.lock:
            row = self._conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_config(self, key: str, value: str) -> None:
        with self.lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
            )
            self._conn.commit()

    # -- polls -------------------------------------------------------------
    def create_poll(self, poll_id: str, question: str, options: list[str], created: str) -> None:
        with self.lock:
            self._conn.execute(
                "INSERT INTO polls (poll_id, question, options, closed, created) "
                "VALUES (?, ?, ?, 0, ?)",
                (poll_id, question, json.dumps(options, ensure_ascii=False), created),
            )
            self._conn.commit()

    def poll(self, poll_id: str) -> PollRow | None:
        with self.lock:
            row = self._conn.execute(
                "SELECT * FROM polls WHERE poll_id = ?", (poll_id,)
            ).fetchone()
        return self._poll_row(row) if row else None

    def polls(self) -> list[PollRow]:
        with self.lock:
            rows = self._conn.execute("SELECT * FROM polls ORDER BY created DESC").fetchall()
        return [self._poll_row(r) for r in rows]

    @staticmethod
    def _poll_row(row: sqlite3.Row) -> PollRow:
        return PollRow(
            poll_id=row["poll_id"],
            question=row["question"],
            options=json.loads(row["options"]),
            closed=bool(row["closed"]),
            created=row["created"],
        )

    def close_poll(self, poll_id: str) -> None:
        with self.lock:
            self._conn.execute("UPDATE polls SET closed = 1 WHERE poll_id = ?", (poll_id,))
            self._conn.commit()

    # -- Eligibility-Ledger ------------------------------------------------
    def has_eligibility(self, poll_id: str, voter_key: str) -> bool:
        with self.lock:
            row = self._conn.execute(
                "SELECT 1 FROM eligibility WHERE poll_id = ? AND voter_key = ?",
                (poll_id, voter_key),
            ).fetchone()
        return row is not None

    def add_eligibility(self, poll_id: str, voter_key: str) -> None:
        with self.lock:
            self._conn.execute(
                "INSERT INTO eligibility (poll_id, voter_key) VALUES (?, ?)", (poll_id, voter_key)
            )
            self._conn.commit()

    def count_eligibility(self, poll_id: str) -> int:
        with self.lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM eligibility WHERE poll_id = ?", (poll_id,)
            ).fetchone()
        return int(row["n"])

    def remove_eligibility(self, poll_id: str, voter_key: str) -> bool:
        """Nur fuer den Testbetrieb (EIP-Reset): Eligibility-Eintrag loeschen,
        damit derselbe Testcode erneut ein Token abholen kann. Im echten
        eID-Verfahren gibt es diesen Weg nicht - dort ist die Sperre nach dem
        ersten Token endgueltig gewollt (§6)."""
        with self.lock:
            cur = self._conn.execute(
                "DELETE FROM eligibility WHERE poll_id = ? AND voter_key = ?", (poll_id, voter_key)
            )
            self._conn.commit()
            return cur.rowcount > 0

    # -- Vote-Ledger (nur verbrauchte Tokens) ------------------------------
    def is_spent(self, poll_id: str, token_hex: str) -> bool:
        with self.lock:
            row = self._conn.execute(
                "SELECT 1 FROM spent WHERE poll_id = ? AND token_hex = ?", (poll_id, token_hex)
            ).fetchone()
        return row is not None

    def add_spent(self, poll_id: str, token_hex: str) -> None:
        with self.lock:
            self._conn.execute(
                "INSERT INTO spent (poll_id, token_hex) VALUES (?, ?)", (poll_id, token_hex)
            )
            self._conn.commit()

    def count_spent(self, poll_id: str) -> int:
        with self.lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM spent WHERE poll_id = ?", (poll_id,)
            ).fetchone()
        return int(row["n"])

    # -- Board -------------------------------------------------------------
    def board(self, poll_id: str) -> list[BoardEntry]:
        with self.lock:
            rows = self._conn.execute(
                "SELECT idx, prev_hash, payload, entry_hash FROM board "
                "WHERE poll_id = ? ORDER BY idx",
                (poll_id,),
            ).fetchall()
        return [BoardEntry(r["idx"], r["prev_hash"], r["payload"], r["entry_hash"]) for r in rows]

    def board_head(self, poll_id: str) -> tuple[int, str]:
        """(naechster_index, head_hash)."""
        with self.lock:
            row = self._conn.execute(
                "SELECT idx, entry_hash FROM board WHERE poll_id = ? ORDER BY idx DESC LIMIT 1",
                (poll_id,),
            ).fetchone()
        return (0, GENESIS) if row is None else (row["idx"] + 1, row["entry_hash"])

    def append_board(self, poll_id: str, payload: dict[str, Any]) -> BoardEntry:
        with self.lock:
            index, prev = self.board_head(poll_id)
            line = canonical(payload)
            digest = entry_hash(index, prev, line)
            self._conn.execute(
                "INSERT INTO board (poll_id, idx, prev_hash, payload, entry_hash) "
                "VALUES (?, ?, ?, ?, ?)",
                (poll_id, index, prev, line, digest),
            )
            self._conn.commit()
            return BoardEntry(index, prev, line, digest)

    def overwrite_board_payload(self, poll_id: str, index: int, payload: str) -> bool:
        """Nur fuer die Manipulationsdemo (§9): Payload aendern, Hashes stehen lassen."""
        with self.lock:
            cur = self._conn.execute(
                "UPDATE board SET payload = ? WHERE poll_id = ? AND idx = ?",
                (payload, poll_id, index),
            )
            self._conn.commit()
            return cur.rowcount > 0


def verify_chain(entries: list[BoardEntry]) -> tuple[bool, int | None]:
    """Prueft die Kette. Gibt (ok, erster_defekter_index) zurueck."""
    prev = GENESIS
    for entry in entries:
        expected = entry_hash(entry.index, prev, entry.payload)
        if entry.prev_hash != prev or entry.entry_hash != expected:
            return False, entry.index
        prev = entry.entry_hash
    return True, None
