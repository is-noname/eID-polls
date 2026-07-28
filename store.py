"""SQLite-Persistenz: Eligibility-Ledger, Vote-Ledger, Board-Hash-Kette.

Datenmodell nach EIP-RFC-20260725-001 §6/§9 und dem Prototyp-Fund aus
PROTOTYPE_two-ledger/NOTES.md:

  eligibility  gehashte Pseudonyme - weiss "hat abgeholt", nicht "wie gestimmt"
  spent        verbrauchte Tokens - reiner Doppelabstimmungs-Index, KEINE Stimmen
  board        die Hash-Kette; traegt die Stimmen und ist die einzige
               Auszaehlungsquelle (§7)

Board-Payloads sind kanonisches JSON (sortierte Schluessel, keine Leerzeichen)
statt der String-Zeile des Prototyps. Damit faellt dessen Grenze weg, dass
Optionen kein Leerzeichen, '+' oder '=' enthalten duerfen.

Das Board-*Format* selbst steht nicht hier, damit ein Dritter es ohne diese
Datei - und damit ohne Datenbank - nachrechnen kann (§7): kanonisches JSON,
Eintrags-Hash und BoardEntry in board_eintrag.py (EIP-T-046), die Kettenpruefung
in verifikation.py (EIP-T-045). Hier bleibt die Persistenz. Die Namen werden
weiter re-exportiert, weil sie zum Board gehoeren und Aufrufer sie neben board()
erwarten.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from board_eintrag import GENESIS, BoardEntry, canonical, entry_hash
from verifikation import verify_chain

__all__ = [
    "GENESIS",
    "BoardEntry",
    "PollRow",
    "Store",
    "canonical",
    "entry_hash",
    "verify_chain",
]

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
        # "Umfrage gibt es nicht" mitten im Betrieb (EIP-T-019).
        #
        # Das Lock ist privat (EIP-T-047): es sichert diese eine Verbindung, es
        # ist *nicht* der Grund, warum ein Ausweis nur ein Token bekommt. Diese
        # Regel setzen beanspruche_berechtigung und verbrauche_token selbst
        # durch. Frueher klammerte poll_service.py "pruefen + einfuegen" von
        # aussen in dieses Lock - ein Vertrag, dessen Verlust keine Pruefung
        # ueber die Schnittstelle bemerkt haette. RLock bleibt, weil die
        # zusammengesetzten Operationen hier drin schachteln (momentaufnahme).
        # Bei der Groessenordnung dieser Umfrage (rund 100 Teilnehmende) kostet
        # die Serialisierung nichts Spuerbares; eine Verbindung pro Thread waere
        # der naechste Schritt, wenn das je knapp wird.
        self._lock = threading.RLock()

    # -- config ------------------------------------------------------------
    def get_config(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_config(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
            )
            self._conn.commit()

    def vernichte_config(self, key: str) -> bool:
        """Loescht einen Konfigurationswert so gruendlich, wie SQLite es zulaesst.

        Rueckgabe: ob es den Schluessel ueberhaupt gab.

        Ein blosses DELETE gibt die Seite nur frei - der alte Wert steht danach
        weiter im Freispeicher der Datei und im WAL. Fuer einen Schluessel, mit
        dessen Loeschung wir *nach aussen* argumentieren (EIP-T-033, Baustein
        D), waere das eine Behauptung statt einer Loeschung. Deshalb drei
        Schritte: Wert mit Zufallsbytes gleicher Laenge ueberschreiben, Zeile
        loeschen, Datei neu schreiben (VACUUM raeumt zugleich das WAL ab).

        Die Grenze dieser Zusage, die nach KODEX § 4 mitzusagen ist: Sie gilt
        fuer *diese Datei*. Sicherungskopien, Dateisystem-Snapshots und die
        Blockverwaltung einer SSD liegen ausserhalb dessen, was ein Programm
        ueberschreiben kann. Wer die Zusage vollstaendig halten will, braucht
        eine Backup-Regel dazu - nicht nur diesen Aufruf.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT length(value) AS n FROM config WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return False
            fuellwert = secrets.token_hex(max(int(row["n"]), 1))[: int(row["n"])]
            self._conn.execute("UPDATE config SET value = ? WHERE key = ?", (fuellwert, key))
            self._conn.execute("DELETE FROM config WHERE key = ?", (key,))
            self._conn.commit()
            # VACUUM kann nicht in einer Transaktion laufen - nach dem commit
            # oben ist keine offen.
            self._conn.execute("VACUUM")
        return True

    # -- polls -------------------------------------------------------------
    def create_poll(self, poll_id: str, question: str, options: list[str], created: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO polls (poll_id, question, options, closed, created) "
                "VALUES (?, ?, ?, 0, ?)",
                (poll_id, question, json.dumps(options, ensure_ascii=False), created),
            )
            self._conn.commit()

    def poll(self, poll_id: str) -> PollRow | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM polls WHERE poll_id = ?", (poll_id,)
            ).fetchone()
        return self._poll_row(row) if row else None

    def polls(self) -> list[PollRow]:
        with self._lock:
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
        with self._lock:
            self._conn.execute("UPDATE polls SET closed = 1 WHERE poll_id = ?", (poll_id,))
            self._conn.commit()

    # -- Eligibility-Ledger: ein Ausweis, ein Token (§6) --------------------
    def beanspruche_berechtigung(
        self, poll_id: str, voter_key: str, eintrag: Callable[[int], dict[str, Any]]
    ) -> BoardEntry | None:
        """Erhebt den Anspruch auf genau ein Stimm-Token und vermerkt die
        Ausgabe auf dem Board.

        Rueckgabe: der Board-Eintrag der Ausgabe, oder ``None``, wenn fuer
        diesen Ausweis in dieser Umfrage schon eine Berechtigung ausgegeben
        wurde.

        Pruefen und Eintragen sind *ein* Schritt, durchgesetzt vom PRIMARY KEY
        der Tabelle: ``INSERT OR IGNORE`` traegt ein oder tut nichts, und
        ``rowcount`` sagt, was davon passiert ist. Ein zweiter Anspruch kann
        sich deshalb nicht zwischen Pruefung und Einfuegen schieben - die
        Datenbank entscheidet, nicht die Aufmerksamkeit des Aufrufers
        (EIP-T-047, §9).

        Der Board-Eintrag gehoert in denselben Schritt: sonst zeigt die
        Abrechnung fuer einen Moment einen Ledger-Eintrag ohne Board-Eintrag,
        und das Debug-Modul meldet eine Inkonsistenz, die es nicht gibt.

        ``eintrag`` baut den Board-Payload aus der laufenden Nummer der
        Ausgabe - die steht erst hier fest. Als Rueckruf, damit das
        Board-*Format* ausserhalb dieser Datei bleibt (Modul-Docstring).
        """
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO eligibility (poll_id, voter_key) VALUES (?, ?)",
                (poll_id, voter_key),
            )
            if cur.rowcount == 0:
                return None
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM eligibility WHERE poll_id = ?", (poll_id,)
            ).fetchone()
            try:
                # append_board committet - und damit auch den Anspruch oben.
                return self.append_board(poll_id, eintrag(int(row["n"])))
            except Exception:
                self._conn.rollback()  # kein Board-Eintrag, kein Anspruch
                raise

    # -- Vote-Ledger: ein Token, eine Stimme (§9) --------------------------
    def verbrauche_token(
        self, poll_id: str, token_hex: str, eintrag: dict[str, Any]
    ) -> BoardEntry | None:
        """Verbraucht ein Stimm-Token und schreibt die Stimme aufs Board.

        Rueckgabe: der Board-Eintrag der Stimme, oder ``None``, wenn dieses
        Token in dieser Umfrage schon verbraucht war.

        Wie beanspruche_berechtigung ein einziger Schritt ueber den PRIMARY
        KEY - und aus demselben Grund zusammen mit dem Board-Eintrag. Der
        Ledger haelt nur den Token-Hash, keine Stimme: was gestimmt wurde,
        steht ausschliesslich im Board (§7).
        """
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO spent (poll_id, token_hex) VALUES (?, ?)",
                (poll_id, token_hex),
            )
            if cur.rowcount == 0:
                return None
            try:
                return self.append_board(poll_id, eintrag)
            except Exception:
                self._conn.rollback()  # keine Stimme, kein verbrauchtes Token
                raise

    # -- Ledger-Stand fuer die Abrechnung (§9) -----------------------------
    def ledger_stand(self, poll_id: str) -> tuple[int, int]:
        """(ausgegebene Berechtigungen, verbrauchte Tokens) in einem Zug.

        Beide Zahlen zusammen, damit die Abrechnung nicht zwei Zeitpunkte
        vergleicht: dazwischen abgegebene Stimmen saehen sonst wie eine
        Inkonsistenz aus - eine Falschmeldung ausgerechnet an der Stelle, die
        echte Manipulation anzeigen soll.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT (SELECT COUNT(*) FROM eligibility WHERE poll_id = ?) AS eligible, "
                "       (SELECT COUNT(*) FROM spent WHERE poll_id = ?) AS spent",
                (poll_id, poll_id),
            ).fetchone()
        return int(row["eligible"]), int(row["spent"])

    def momentaufnahme(self, poll_id: str) -> tuple[list[BoardEntry], int, int]:
        """(Board, ausgegebene Berechtigungen, verbrauchte Tokens) in einem Zug.

        Board und Ledger unter einem Schritt gelesen und erst danach geprueft:
        die teuren Signaturpruefungen duerfen nicht zwischen den Lesezugriffen
        liegen (siehe ledger_stand).
        """
        with self._lock:
            entries = self.board(poll_id)
            eligible, spent = self.ledger_stand(poll_id)
        return entries, eligible, spent

    # -- Board -------------------------------------------------------------
    def board(self, poll_id: str) -> list[BoardEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT idx, prev_hash, payload, entry_hash FROM board "
                "WHERE poll_id = ? ORDER BY idx",
                (poll_id,),
            ).fetchall()
        return [BoardEntry(r["idx"], r["prev_hash"], r["payload"], r["entry_hash"]) for r in rows]

    def board_head(self, poll_id: str) -> tuple[int, str]:
        """(naechster_index, head_hash)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT idx, entry_hash FROM board WHERE poll_id = ? ORDER BY idx DESC LIMIT 1",
                (poll_id,),
            ).fetchone()
        return (0, GENESIS) if row is None else (row["idx"] + 1, row["entry_hash"])

    def append_board(self, poll_id: str, payload: dict[str, Any]) -> BoardEntry:
        with self._lock:
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
