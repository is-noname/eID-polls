"""SQLite-Persistenz: Eligibility-Ledger, Vote-Ledger, Board mit Batch-Kette.

Datenmodell nach EIP-RFC-20260725-001 §6/§9, dem Prototyp-Fund aus
PROTOTYPE_two-ledger/NOTES.md und EIP-ADR-20260728-001:

  eligibility  gehashte Pseudonyme - weiss "hat abgeholt", nicht "wie gestimmt"
  spent        verbrauchte Tokens - reiner Doppelabstimmungs-Index, KEINE Stimmen
  board        die Eintraege; ohne Eingangsreihenfolge, jeder Eintrag gehoert zu
               einem veroeffentlichten Batch oder wartet im Puffer (batch NULL)
  batches      die veroeffentlichten Batches mit Merkle-Root und Batch-Kette -
               zusammen mit board die einzige Auszaehlungsquelle (§7)

Keine Tabelle traegt eine Eingangsreihenfolge (EIP-T-033, Baustein E):
eligibility und spent sind WITHOUT ROWID ueber ihre Primaerschluessel, board
haengt an (poll_id, leaf_hash) - der Blatt-Hash ist gleichverteilt und sagt
nichts ueber die Zeit. Die einzige Ordnung ist die Batch-Nummer, und deren
Granularitaet ist die Anonymitaetsmenge (ADR E3).

Der Puffer-Zeitpunkt (fuer den Zeitdeckel) wird **auf die Stunde gerundet** je
Umfrage gespeichert, nicht je Eintrag: Ein exakter Zeitstempel des ersten
Eintrags eines Batches waere genau der Korrelationsanker, den der Umbau
entfernt. Fuer einen 6-Stunden-Deckel reicht die Stunde.

Das Board-*Format* selbst steht nicht hier, damit ein Dritter es ohne diese
Datei - und damit ohne Datenbank - nachrechnen kann (§7): kanonisches JSON,
Blatt-Hash, Merkle-Baum und Batch-Kette in board_eintrag.py (EIP-T-046), die
Pruefung in verifikation.py (EIP-T-045). Hier bleibt die Persistenz.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import board_eintrag
from board_eintrag import GENESIS, BoardEntry, canonical
from verifikation import Batch

__all__ = [
    "GENESIS",
    "Batch",
    "BoardEntry",
    "PollRow",
    "Store",
    "canonical",
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
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS spent (
    poll_id   TEXT NOT NULL,
    token_hex TEXT NOT NULL,
    PRIMARY KEY (poll_id, token_hex)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS board (
    poll_id   TEXT NOT NULL,
    leaf_hash TEXT NOT NULL,
    payload   TEXT NOT NULL,
    batch     INTEGER,
    PRIMARY KEY (poll_id, leaf_hash)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS batches (
    poll_id     TEXT NOT NULL,
    batch       INTEGER NOT NULL,
    merkle_root TEXT NOT NULL,
    batch_root  TEXT NOT NULL,
    published   TEXT NOT NULL,
    PRIMARY KEY (poll_id, batch)
) WITHOUT ROWID;
"""

# Praefix des gerundeten Puffer-Beginns je Umfrage (Zeitdeckel, ADR E3).
PENDING_SINCE = "pending_since:"


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
        self._weise_altformat_ab()
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
        # durch. RLock bleibt, weil die zusammengesetzten Operationen hier drin
        # schachteln (momentaufnahme, publiziere).
        self._lock = threading.RLock()

    def _weise_altformat_ab(self) -> None:
        """Datenbanken im Ketten-Format (vor ADR-20260728-001) nicht stillschweigend
        weiterbenutzen.

        Der Formatwechsel ist ein bewusster Bruch (ADR, "Formatbruch"): Eintraege
        verlieren ihre Nummern, die Kette wird zur Batch-Kette. Ein Altbestand
        laesst sich nicht verlustfrei ueberfuehren, ohne seine Eingangsreihenfolge
        mitzunehmen - und genau die soll weg. Die Migrationsentscheidung der ADR:
        Vorfuehrdaten verwerfen. Sichtbar statt still - deshalb Abbruch mit
        Anleitung statt eines leeren Boards neben vollen Ledgern.
        """
        spalten = {
            r["name"]
            for r in self._conn.execute("PRAGMA table_info(board)").fetchall()
        }
        if "idx" in spalten:
            raise RuntimeError(
                f"Die Datenbank {self.path} stammt aus dem Ketten-Format vor "
                "EIP-ADR-20260728-001 (Merkle-Set mit Batch-Kette). Sie enthaelt nur "
                "Vorfuehrdaten und wird verworfen: Datei loeschen oder EIDPOLL_DB auf "
                "einen neuen Pfad setzen, dann neu starten."
            )
        # Boards ohne Token-Schluessel im POLL_OPEN-Eintrag (vor EIP-T-069)
        # liessen sich nicht mehr pruefen: Der globale Schluessel, gegen den
        # ihre Signaturen gelten, wird beim Start vernichtet. Auch das ist
        # Vorfuehrbestand und wird sichtbar verworfen, statt als Board mit
        # lauter unlesbaren Eroeffnungseintraegen weiterzulaufen.
        if spalten:
            alt = self._conn.execute(
                "SELECT COUNT(*) AS n FROM board "
                "WHERE payload LIKE '%\"POLL_OPEN\"%' AND payload NOT LIKE '%\"pubkey\"%'"
            ).fetchone()
            if alt and int(alt["n"]):
                raise RuntimeError(
                    f"Die Datenbank {self.path} stammt aus der Zeit vor EIP-T-069 (ein "
                    "globaler Token-Signaturschluessel statt einem je Umfrage). Ihre "
                    "Boards nennen keinen Schluessel und waeren nach dem Start nicht mehr "
                    "pruefbar. Sie enthaelt nur Vorfuehrdaten und wird verworfen: Datei "
                    "loeschen oder EIDPOLL_DB auf einen neuen Pfad setzen, dann neu starten."
                )

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
        D), waere das eine Behauptung statt einer Loeschung. Deshalb vier
        Schritte: Wert mit Zufallsbytes gleicher Laenge ueberschreiben, Zeile
        loeschen, Datei neu schreiben (VACUUM), WAL leeren.

        Der letzte Schritt ist nicht kosmetisch. Bis EIP-T-041 stand hier, VACUUM
        raeume das WAL gleich mit ab - das tut es nicht: Der vernichtete
        Schluessel lag danach vollstaendig in ``<datei>-wal``, und der Abzug in
        smoke_test.datenabzug_nach_schluss hat ihn dort gefunden. Baustein D war
        damit fuer jeden, der die Dateien neben der Datenbank mitnimmt, nicht
        erfuellt. ``wal_checkpoint(TRUNCATE)`` schreibt das WAL in die (frisch
        gevacuumte) Datei zurueck und setzt es auf Laenge 0.

        Die Grenze dieser Zusage, die nach KODEX § 4 mitzusagen ist: Sie gilt
        fuer *diese Datei und ihr WAL*. Sicherungskopien, Dateisystem-Snapshots
        und die Blockverwaltung einer SSD liegen ausserhalb dessen, was ein
        Programm ueberschreiben kann - ein truncate gibt Bloecke frei, es
        loescht sie nicht physisch. Wer die Zusage vollstaendig halten will,
        braucht eine Backup-Regel dazu - nicht nur diesen Aufruf.
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
            # TRUNCATE statt des Default-PASSIVE: PASSIVE laesst das WAL in
            # voller Laenge liegen, samt des Frames, der den alten Wert traegt.
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
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
        self, poll_id: str, voter_key: str, eintrag: dict[str, Any]
    ) -> BoardEntry | None:
        """Erhebt den Anspruch auf genau ein Stimm-Token und vermerkt die
        Ausgabe im Board-Puffer.

        Rueckgabe: der gepufferte Board-Eintrag der Ausgabe, oder ``None``,
        wenn fuer diesen Ausweis in dieser Umfrage schon eine Berechtigung
        ausgegeben wurde.

        Pruefen und Eintragen sind *ein* Schritt, durchgesetzt vom PRIMARY KEY
        der Tabelle: ``INSERT OR IGNORE`` traegt ein oder tut nichts, und
        ``rowcount`` sagt, was davon passiert ist. Ein zweiter Anspruch kann
        sich deshalb nicht zwischen Pruefung und Einfuegen schieben - die
        Datenbank entscheidet, nicht die Aufmerksamkeit des Aufrufers
        (EIP-T-047, §9).

        Der Board-Eintrag gehoert in denselben Schritt: sonst zeigt die
        Abrechnung fuer einen Moment einen Ledger-Eintrag ohne Board-Eintrag,
        und das Debug-Modul meldet eine Inkonsistenz, die es nicht gibt.
        """
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO eligibility (poll_id, voter_key) VALUES (?, ?)",
                (poll_id, voter_key),
            )
            if cur.rowcount == 0:
                return None
            try:
                # _puffer committet - und damit auch den Anspruch oben.
                entry, _ = self._puffer(poll_id, eintrag)
                return entry
            except Exception:
                self._conn.rollback()  # kein Board-Eintrag, kein Anspruch
                raise

    # -- Vote-Ledger: ein Token, eine Stimme (§9) --------------------------
    def verbrauche_token(
        self, poll_id: str, token_hex: str, eintrag: dict[str, Any]
    ) -> tuple[BoardEntry, int] | None:
        """Verbraucht ein Stimm-Token und puffert die Stimme fuers Board.

        Rueckgabe: ``(Board-Eintrag, zugesagte Batch-Nummer)``, oder ``None``,
        wenn dieses Token in dieser Umfrage schon verbraucht war. Die zugesagte
        Batch-Nummer ist Teil des signierten Belegs (ADR E4): Jede
        Veroeffentlichung nimmt den ganzen Puffer mit, also ist der naechste
        Batch nach dem Einfuegen genau der, in dem dieser Eintrag erscheint.

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
                return self._puffer(poll_id, eintrag)
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

    def momentaufnahme(
        self, poll_id: str
    ) -> tuple[list[Batch], list[BoardEntry], int, int]:
        """(Batches, Puffer, ausgegebene Berechtigungen, verbrauchte Tokens) in
        einem Zug - erst danach pruefen: die teuren Signaturpruefungen duerfen
        nicht zwischen den Lesezugriffen liegen (siehe ledger_stand).
        """
        with self._lock:
            batches = self.veroeffentlichte_batches(poll_id)
            pending = self.pending(poll_id)
            eligible, spent = self.ledger_stand(poll_id)
        return batches, pending, eligible, spent

    # -- Board: Puffer und Batches (EIP-ADR-20260728-001) -------------------
    def _puffer(self, poll_id: str, payload: dict[str, Any]) -> tuple[BoardEntry, int]:
        """Legt einen Eintrag in den Puffer. Rueckgabe: (Eintrag, naechste Batch-Nummer)."""
        entry = BoardEntry.from_payload(payload)
        self._conn.execute(
            "INSERT INTO board (poll_id, leaf_hash, payload, batch) VALUES (?, ?, ?, NULL)",
            (poll_id, entry.leaf_hash, entry.payload),
        )
        # Puffer-Beginn fuer den Zeitdeckel, auf die Stunde gerundet
        # (Modul-Docstring: keine feinen Zeitstempel neben den Eintraegen).
        key = PENDING_SINCE + poll_id
        row = self._conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        if row is None:
            stunde = datetime.now().replace(minute=0, second=0, microsecond=0)
            self._conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?)",
                (key, stunde.isoformat(timespec="seconds")),
            )
        zusage = int(
            self._conn.execute(
                "SELECT COUNT(*) AS n FROM batches WHERE poll_id = ?", (poll_id,)
            ).fetchone()["n"]
        )
        self._conn.commit()
        return entry, zusage

    def puffer_eintrag(self, poll_id: str, payload: dict[str, Any]) -> BoardEntry:
        """Eintrag ohne Ledger-Anspruch puffern (POLL_OPEN, POLL_CLOSED)."""
        with self._lock:
            entry, _ = self._puffer(poll_id, payload)
        return entry

    def pending(self, poll_id: str) -> list[BoardEntry]:
        """Der unveroeffentlichte Puffer - Betreibersicht, nicht Teil des
        oeffentlichen Boards. Sortiert nach Blatt-Hash, damit auch diese Sicht
        keine Eingangsreihenfolge zeigt."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT leaf_hash, payload FROM board "
                "WHERE poll_id = ? AND batch IS NULL ORDER BY leaf_hash",
                (poll_id,),
            ).fetchall()
        return [BoardEntry(r["payload"], r["leaf_hash"], None) for r in rows]

    def pending_stand(self, poll_id: str) -> tuple[int, datetime | None]:
        """(Anzahl im Puffer, gerundeter Puffer-Beginn oder None)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM board WHERE poll_id = ? AND batch IS NULL",
                (poll_id,),
            ).fetchone()
            since = self.get_config(PENDING_SINCE + poll_id)
        return int(row["n"]), datetime.fromisoformat(since) if since else None

    def veroeffentlichte_batches(self, poll_id: str) -> list[Batch]:
        with self._lock:
            batch_rows = self._conn.execute(
                "SELECT batch, merkle_root, batch_root FROM batches "
                "WHERE poll_id = ? ORDER BY batch",
                (poll_id,),
            ).fetchall()
            entry_rows = self._conn.execute(
                "SELECT leaf_hash, payload, batch FROM board "
                "WHERE poll_id = ? AND batch IS NOT NULL ORDER BY batch, leaf_hash",
                (poll_id,),
            ).fetchall()
        je_batch: dict[int, list[BoardEntry]] = {}
        for r in entry_rows:
            je_batch.setdefault(int(r["batch"]), []).append(
                BoardEntry(r["payload"], r["leaf_hash"], int(r["batch"]))
            )
        return [
            Batch(
                n=int(r["batch"]),
                merkle_root=r["merkle_root"],
                batch_root=r["batch_root"],
                entries=tuple(je_batch.get(int(r["batch"]), ())),
            )
            for r in batch_rows
        ]

    def publiziere(self, poll_id: str) -> Batch | None:
        """Veroeffentlicht den gesamten Puffer als naechsten Batch.

        Rueckgabe: der neue Batch, oder ``None`` bei leerem Puffer. Merkle-Root
        und Kettenglied werden hier berechnet und gespeichert; die Pruefung
        (verifikation.py) rechnet beides aus den Eintraegen nach und behandelt
        die gespeicherten Werte als Behauptung.
        """
        with self._lock:
            pending = self.pending(poll_id)
            if not pending:
                return None
            n = int(
                self._conn.execute(
                    "SELECT COUNT(*) AS n FROM batches WHERE poll_id = ?", (poll_id,)
                ).fetchone()["n"]
            )
            prev_row = self._conn.execute(
                "SELECT batch_root FROM batches WHERE poll_id = ? AND batch = ?",
                (poll_id, n - 1),
            ).fetchone()
            prev = prev_row["batch_root"] if prev_row else GENESIS
            root = board_eintrag.merkle_root(e.leaf_hash for e in pending)
            glied = board_eintrag.batch_root(root, prev)
            self._conn.execute(
                "UPDATE board SET batch = ? WHERE poll_id = ? AND batch IS NULL",
                (n, poll_id),
            )
            self._conn.execute(
                "INSERT INTO batches (poll_id, batch, merkle_root, batch_root, published) "
                "VALUES (?, ?, ?, ?, ?)",
                (poll_id, n, root, glied, datetime.now().isoformat(timespec="seconds")),
            )
            self._conn.execute(
                "DELETE FROM config WHERE key = ?", (PENDING_SINCE + poll_id,)
            )
            self._conn.commit()
            return Batch(
                n=n,
                merkle_root=root,
                batch_root=glied,
                entries=tuple(BoardEntry(e.payload, e.leaf_hash, n) for e in pending),
            )
