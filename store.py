"""SQLite-Persistenz der Board-Seite - und die gemeinsame Basis beider Speicher.

Seit EIP-T-033 (Baustein G) gibt es **zwei Datenbankdateien**, nicht eine:

  board.sqlite3         diese Datei hier: Umfragen, Board, Batches, Vote-Ledger
  *.berechtigung.*      berechtigung_store.py: Eligibility-Ledger, Wiederhol-
                        Puffer, Umfrage-Schluessel - alles, was das Pseudonym
                        kennt

Die Trennlinie verlaeuft dort, wo spaeter die Betreibergrenze liegen soll
(Stufe 2, EIP-T-037/T-040): Dienst A kennt das Pseudonym und gibt Blind-
signaturen aus, Dienst B kennt Token und Stimme. Ein Join ueber beide Seiten
ist damit eine bewusste Handlung ueber zwei Dateien - kein SELECT ueber zwei
Tabellen derselben Datei, das einem Codepfad versehentlich unterlaeuft.

Datenmodell nach EIP-RFC-20260725-001 §6/§9, dem Prototyp-Fund aus
PROTOTYPE_two-ledger/NOTES.md und EIP-ADR-20260728-001:

  spent        verbrauchte Tokens - reiner Doppelabstimmungs-Index, KEINE Stimmen
  board        die Eintraege; ohne Eingangsreihenfolge, jeder Eintrag gehoert zu
               einem veroeffentlichten Batch oder wartet im Puffer (batch NULL)
  batches      die veroeffentlichten Batches mit Merkle-Root und Batch-Kette -
               zusammen mit board die einzige Auszaehlungsquelle (§7)

Keine Tabelle traegt eine Eingangsreihenfolge (EIP-T-033, Baustein E): spent
ist WITHOUT ROWID ueber seinen Primaerschluessel, board haengt an (poll_id,
leaf_hash) - der Blatt-Hash ist gleichverteilt und sagt nichts ueber die Zeit.
Die einzige Ordnung ist die Batch-Nummer, und deren Granularitaet ist die
Anonymitaetsmenge (ADR E3).

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
from typing import Any, ClassVar

import board_eintrag
from board_eintrag import GENESIS, BoardEntry, canonical
from verifikation import Batch

__all__ = [
    "GENESIS",
    "Batch",
    "BoardEntry",
    "PollRow",
    "SqliteStore",
    "Store",
    "canonical",
]

# Praefix des gerundeten Puffer-Beginns je Umfrage (Zeitdeckel, ADR E3).
PENDING_SINCE = "pending_since:"


@dataclass(frozen=True)
class PollRow:
    poll_id: str
    question: str
    options: list[str]
    closed: bool
    created: str


class SqliteStore:
    """Gemeinsame Basis beider Speicher: Verbindung, Lock, config-Tabelle.

    Was hier steht, brauchen beide Seiten der Trennlinie identisch - vor allem
    ``vernichte_config`` und ``kopiere_ohne_geheimnisse``, deren Zusagen nicht
    in zwei Fassungen auseinanderlaufen duerfen. Was eine Seite alleine
    braucht, steht in ihrer Unterklasse.
    """

    SCHEMA: ClassVar[str] = ""
    # Was aus der config-Tabelle eine Sicherungskopie ueberleben darf
    # (EIP-T-067). Bewusst eine *Positiv*liste: Eine Liste der Geheimnisse waere
    # eine Liste von heute - der naechste Schluessel, den jemand hinzufuegt,
    # laege still in jeder Kopie, und genau dieser Fund (ein vernichtetes
    # server_secret, das in data.backup.<zeit>/ weiterlebte) hat das Ticket
    # ausgeloest. Ein neuer Eintrag muss hier bewusst freigegeben werden, sonst
    # faellt er heraus.
    KOPIERBARE_CONFIG_PRAEFIXE: ClassVar[tuple[str, ...]] = ()
    # Tabellen, die in einer Kopie geleert werden (Betriebszustand, kein Bestand).
    KOPIE_LEEREN: ClassVar[tuple[str, ...]] = ()

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
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()
        # Alle Threads teilen sich diese eine Verbindung (check_same_thread=False).
        # Deshalb steht auch jeder *Lesezugriff* unter dem Lock, nicht nur die
        # Schreiber: zwei Anfragen gleichzeitig auf derselben Connection liefern
        # sonst vertauschte oder leere Zeilen zurueck - unter Last hiess das
        # "Umfrage gibt es nicht" mitten im Betrieb (EIP-T-019).
        #
        # Das Lock ist privat (EIP-T-047): es sichert diese eine Verbindung, es
        # ist *nicht* der Grund, warum ein Ausweis nur ein Token bekommt. Diese
        # Regel setzen die Ledger-Methoden selbst durch. RLock bleibt, weil die
        # zusammengesetzten Operationen hier drin schachteln (momentaufnahme,
        # publiziere).
        self._lock = threading.RLock()

    def _weise_altformat_ab(self) -> None:
        """Hook der Unterklassen: bekannte Altformate sichtbar abweisen."""

    def _hat_tabelle(self, name: str) -> bool:
        return bool(
            self._conn.execute(f"PRAGMA table_info({name})").fetchall()
        )

    @staticmethod
    def _stunde() -> str:
        return datetime.now().replace(minute=0, second=0, microsecond=0).isoformat(
            timespec="seconds"
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

        Diese Regel gibt es seit EIP-T-067: EIP-RPT-20260731-002 §3.3 sagt,
        wann eine Kopie existieren darf (Regel 1: keine, die eine
        Schluesselvernichtung ueberdauert), und ``kopiere_ohne_geheimnisse``
        gibt den Weg vor, eine anzulegen, die keine Schluessel traegt. Der Satz
        oben bleibt trotzdem stehen: Dateisystem-Snapshots und die
        Blockverwaltung einer SSD erreicht auch diese Regel nicht - sie ist
        Disziplin plus ein Test ueber das Datenverzeichnis, kein Beweis ueber
        den Datentraeger.
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

    def kopiere_ohne_geheimnisse(self, ziel: Path) -> list[str]:
        """Legt eine Sicherungskopie an, die keine Schluessel traegt (EIP-T-067).

        Rueckgabe: die entfernten config-Schluessel, sortiert - damit der
        Aufrufer *sieht*, was herausgefallen ist, statt es zu glauben.

        Die Zusage von ``vernichte_config`` gilt fuer eine Datei. Eine Kopie
        daneben hebt sie auf, und zwar lautlos: Am 2026-07-31 lag in
        ``data.backup.<zeit>/`` ein ``server_secret``, das die Datenbank
        daneben laengst vernichtet hatte - damit waren die Eligibility-Zeilen
        aller Umfragen weiter auf ihr Pseudonym zurueckrechenbar (EIP-T-033,
        Baustein D). Eine Kopie mit Schluesseln ist kein Backup, sondern ein
        zweiter Angriffspunkt: nach KODEX §5 ist sie beschlagnahmefaehig wie
        das Original, ohne dessen Schutz.

        Deshalb kopiert diese Methode nicht die Datei, sondern die Datenbank
        *ohne* ihre config-Tabelle bis auf ``KOPIERBARE_CONFIG_PRAEFIXE`` und
        ohne die Tabellen aus ``KOPIE_LEEREN`` (Betriebszustand von heute,
        kein Bestand - EIP-T-070).

        Drei Feinheiten, die je einen Fehlschlag gekostet haben:

        - ``VACUUM INTO`` statt Dateikopie: schreibt die Zielseiten neu, also
          ohne Freispeicher, und braucht kein WAL daneben. Eine Kopie mit
          ``shutil`` waere ohne ihr WAL unvollstaendig - und *mit* ihm traege
          sie genau die Frames, die V-003 ausgemacht haben.
        - Nach dem Loeschen in der Kopie noch einmal VACUUM: ein DELETE gibt
          die Seite nur frei, der Wert steht weiter im Freispeicher.
        - ``journal_mode=DELETE`` am Ende: sonst bleibt neben der Kopie ein
          ``-wal`` liegen, und beim Aufraeumen zaehlt das Verzeichnis, nicht
          die Datei (V-003 eine Ebene hoeher).

        Was die Methode **nicht** leistet: Sie macht ein Backup einer offenen
        Umfrage nicht unbedenklich. Regel 1 der Backup-Regel
        (EIP-RPT-20260731-002 §3.3) bleibt der Massstab: Sie sagt, *wann* eine
        Kopie existieren darf, diese Methode nur, *wie* sie dann aussieht.
        """
        ziel = Path(ziel)
        if ziel.exists():
            raise FileExistsError(
                f"{ziel} gibt es schon. Eine Sicherungskopie wird nicht ueberschrieben - "
                "sonst bleibt der alte Inhalt im Freispeicher der Datei stehen."
            )
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._conn.execute("VACUUM INTO ?", (str(ziel),))

        kopie = sqlite3.connect(ziel)
        try:
            if self.KOPIERBARE_CONFIG_PRAEFIXE:
                behalten = " OR ".join(["key LIKE ?"] * len(self.KOPIERBARE_CONFIG_PRAEFIXE))
                wo = f"NOT ({behalten})"
                muster = [p + "%" for p in self.KOPIERBARE_CONFIG_PRAEFIXE]
            else:
                wo, muster = "1=1", []
            entfernt = [
                r[0] for r in kopie.execute(
                    f"SELECT key FROM config WHERE {wo} ORDER BY key", muster
                ).fetchall()
            ]
            kopie.execute(
                f"UPDATE config SET value = "
                f"substr(hex(randomblob(length(value))), 1, length(value)) "
                f"WHERE {wo}", muster
            )
            kopie.execute(f"DELETE FROM config WHERE {wo}", muster)
            for tabelle in self.KOPIE_LEEREN:
                kopie.execute(f"DELETE FROM {tabelle}")
            kopie.commit()
            kopie.execute("VACUUM")
            kopie.execute("PRAGMA journal_mode=DELETE")
        finally:
            kopie.close()
        return entfernt


class Store(SqliteStore):
    """Die Board-Seite: Umfragen, Board mit Batch-Kette, Vote-Ledger.

    Kennt Token und Stimme, aber kein Pseudonym und keinen Umfrage-Schluessel -
    die liegen in berechtigung_store.BerechtigungsStore (Baustein G).
    """

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
    KOPIERBARE_CONFIG_PRAEFIXE = (PENDING_SINCE,)
    KOPIE_LEEREN = ()

    def _weise_altformat_ab(self) -> None:
        """Bekannte Altbestaende nicht stillschweigend weiterbenutzen.

        Drei Faelle, alle nach demselben Muster (sichtbar abweisen mit
        Anleitung statt still weiterlaufen):

        1. Ketten-Format vor EIP-ADR-20260728-001 (board.idx).
        2. Boards ohne Token-Schluessel im POLL_OPEN-Eintrag (vor EIP-T-069).
        3. Kombinierte Datenbank vor Baustein G (eligibility-Tabelle in
           derselben Datei wie das Board): Die Trennung der Speicher laesst
           sich nicht dadurch herstellen, dass die alte Datei einfach zur
           Board-Datei erklaert wird - der Eligibility-Bestand laege dann
           weiter neben dem Board, und die Trennlinie waere Behauptung.
           Vorfuehrdaten verwerfen, wie bei den Formatbruechen zuvor.
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
        if self._hat_tabelle("eligibility"):
            raise RuntimeError(
                f"Die Datenbank {self.path} stammt aus der Zeit vor der Speicher-Trennung "
                "(EIP-T-033, Baustein G): Eligibility-Ledger und Board liegen in derselben "
                "Datei. Seitdem gehoeren sie in zwei Dateien mit getrennten Zugriffspfaden. "
                "Sie enthaelt nur Vorfuehrdaten und wird verworfen: Datei loeschen oder "
                "EIDPOLL_DB auf einen neuen Pfad setzen, dann neu starten."
            )

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

        Pruefen und Eintragen sind *ein* Schritt, durchgesetzt vom PRIMARY KEY
        der Tabelle: ``INSERT OR IGNORE`` traegt ein oder tut nichts, und
        ``rowcount`` sagt, was davon passiert ist (EIP-T-047, §9). Der
        Board-Eintrag gehoert in denselben Schritt - beides liegt in dieser
        einen Datei, die Transaktion bleibt also auch nach der Speicher-
        Trennung (Baustein G) ein Stueck. Der Ledger haelt nur den Token-Hash,
        keine Stimme: was gestimmt wurde, steht ausschliesslich im Board (§7).
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

    def anzahl_verbraucht(self, poll_id: str) -> int:
        """Verbrauchte Tokens dieser Umfrage - die Board-Haelfte der Abrechnung."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM spent WHERE poll_id = ?", (poll_id,)
            ).fetchone()
        return int(row["n"])

    def momentaufnahme(self, poll_id: str) -> tuple[list[Batch], list[BoardEntry], int]:
        """(Batches, Puffer, verbrauchte Tokens) in einem Zug - erst danach
        pruefen: die teuren Signaturpruefungen duerfen nicht zwischen den
        Lesezugriffen liegen. Die Eligibility-Haelfte der Abrechnung liegt seit
        Baustein G in der anderen Datei; wie die beiden Lesezeitpunkte
        zusammengehen, entscheidet der Aufrufer (poll_service.ledger_stand).
        """
        with self._lock:
            batches = self.veroeffentlichte_batches(poll_id)
            pending = self.pending(poll_id)
            spent = self.anzahl_verbraucht(poll_id)
        return batches, pending, spent

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
            self._conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?)", (key, self._stunde())
            )
        zusage = int(
            self._conn.execute(
                "SELECT COUNT(*) AS n FROM batches WHERE poll_id = ?", (poll_id,)
            ).fetchone()["n"]
        )
        self._conn.commit()
        return entry, zusage

    def puffer_eintrag(self, poll_id: str, payload: dict[str, Any]) -> BoardEntry:
        """Eintrag ohne Vote-Ledger-Anspruch puffern (POLL_OPEN, POLL_CLOSED,
        TOKEN_ISSUED - letzterer kommt seit Baustein G von der Berechtigungs-
        seite herueber: der Eintrag traegt nur einen Zufalls-Nonce, kein
        Pseudonym, und die oeffentliche Abrechnung aus §9 braucht ihn)."""
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
