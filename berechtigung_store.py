"""SQLite-Persistenz der Berechtigungsseite - alles, was das Pseudonym kennt.

Die andere Haelfte der Speicher-Trennung aus EIP-T-033, Baustein G (die
Board-Seite und die gemeinsame Basis stehen in store.py):

  eligibility  gehashte Pseudonyme - weiss "hat abgeholt", nicht "wie gestimmt"
  issue_retry  kurzlebiger Wiederhol-Puffer der Ausgabe (EIP-T-070): verblindete
               Anfrage und ihre Blindsignatur, damit ein Abbruch nach dem
               Signieren nicht die Berechtigung verbrennt. Wird nach Ablauf und
               beim Schliessen geloescht, faellt aus Sicherungskopien heraus
  config       die Schluessel dieser Seite: Umfrage-Schluessel der Pseudonym-
               Ableitung (poll_secret, Baustein D), privater Token-Signatur-
               schluessel (poll_key, EIP-T-069), Cookie-Schluessel der
               eID-Sitzung. Alles, was hier liegt, waere in der Board-Datei
               genau die Rueckrechenbarkeit, die die Trennung ausschliesst.

Warum eine eigene Datei und nicht eine Tabelle weiter links: In *einer* Datei
ist der Join Eligibility-Ledger gegen Board ein SELECT, der jedem Codepfad
versehentlich unterlaufen kann - und wer die Datei hat, hat beide Seiten. In
zwei Dateien ist er eine bewusste Handlung ueber zwei Verbindungen, und die
Trennlinie liegt schon dort, wo in Stufe 2 die Betreibergrenze verlaufen soll
(EIP-T-037/T-040): Dienst A haelt diese Datei, Dienst B die Board-Datei.

Keine Tabelle traegt eine Eingangsreihenfolge (Baustein E): eligibility ist
WITHOUT ROWID ueber (poll_id, voter_key). issue_retry ist die eine Ausnahme
und deshalb ausdruecklich benannt: Sie traegt eine Zeit, weil ein Ablauf sie
braucht. Auf die *Stunde gerundet* - eine Stunde ist zu grob, um daraus eine
Reihenfolge zu bauen, und die Zeile verschwindet ohnehin mit dem Ablauf. Was
sie verbindet (voter_key -> verblindete Anfrage), sieht der Issuer im
regulaeren Ablauf ohnehin; das entblindete Token kommt darin nicht vor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from store import SqliteStore

__all__ = ["BerechtigungsStore"]


class BerechtigungsStore(SqliteStore):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS config (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS eligibility (
        poll_id   TEXT NOT NULL,
        voter_key TEXT NOT NULL,
        PRIMARY KEY (poll_id, voter_key)
    ) WITHOUT ROWID;
    CREATE TABLE IF NOT EXISTS issue_retry (
        poll_id   TEXT NOT NULL,
        voter_key TEXT NOT NULL,
        blinded_h TEXT NOT NULL,
        blind_sig TEXT NOT NULL,
        stunde    TEXT NOT NULL,
        PRIMARY KEY (poll_id, voter_key)
    ) WITHOUT ROWID;
    """
    # In einer Kopie dieser Datei ueberlebt kein config-Eintrag: Alles hier
    # sind Schluessel, und der Wiederhol-Puffer ist Betriebszustand von heute.
    KOPIERBARE_CONFIG_PRAEFIXE = ()
    KOPIE_LEEREN = ("issue_retry",)

    def _weise_altformat_ab(self) -> None:
        if self._hat_tabelle("board"):
            raise RuntimeError(
                f"Die Datenbank {self.path} traegt eine board-Tabelle - das ist die alte "
                "kombinierte Datei vor der Speicher-Trennung (EIP-T-033, Baustein G), keine "
                "Berechtigungs-Datenbank. Datei loeschen oder EIDPOLL_DB auf einen neuen "
                "Pfad setzen, dann neu starten."
            )

    # -- Eligibility-Ledger: ein Ausweis, ein Token (§6) --------------------
    def beanspruche(
        self,
        poll_id: str,
        voter_key: str,
        blinded_h: str | None = None,
        blind_sig_hex: str | None = None,
    ) -> bool:
        """Erhebt den Anspruch auf genau ein Stimm-Token.

        Rueckgabe: ``False``, wenn fuer diesen Ausweis in dieser Umfrage schon
        eine Berechtigung ausgegeben wurde.

        ``blinded_h`` und ``blind_sig_hex`` gehen in denselben Schritt
        (EIP-T-070): Wer den Anspruch verbraucht, muss die Antwort nachher noch
        einmal bekommen koennen. Laege der Wiederhol-Puffer in einer zweiten
        Transaktion, waere genau der Fall wieder offen, den das Ticket schliesst
        - Anspruch weg, Antwort nirgends. Ohne die beiden (Puffer abgeschaltet)
        bleibt es beim alten Verhalten.

        Pruefen und Eintragen sind *ein* Schritt, durchgesetzt vom PRIMARY KEY
        der Tabelle: ``INSERT OR IGNORE`` traegt ein oder tut nichts, und
        ``rowcount`` sagt, was davon passiert ist. Ein zweiter Anspruch kann
        sich deshalb nicht zwischen Pruefung und Einfuegen schieben - die
        Datenbank entscheidet, nicht die Aufmerksamkeit des Aufrufers
        (EIP-T-047, §9).

        Der TOKEN_ISSUED-Eintrag fuers Board liegt seit Baustein G **nicht**
        mehr in dieser Transaktion - er gehoert der anderen Datei. Schlaegt er
        fehl, nimmt der Aufrufer den Anspruch mit ``gib_frei`` zurueck; das
        Fenster dazwischen macht die Konsistenzpruefung sichtbar
        (poll_service.check_consistency), statt dass eine Transaktion es
        verdeckt haette, die es ueber zwei Dateien nicht mehr gibt.
        """
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO eligibility (poll_id, voter_key) VALUES (?, ?)",
                (poll_id, voter_key),
            )
            if cur.rowcount == 0:
                return False
            try:
                if blinded_h is not None and blind_sig_hex is not None:
                    self._conn.execute(
                        "INSERT OR REPLACE INTO issue_retry "
                        "(poll_id, voter_key, blinded_h, blind_sig, stunde) VALUES (?, ?, ?, ?, ?)",
                        (poll_id, voter_key, blinded_h, blind_sig_hex, self._stunde()),
                    )
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()  # kein Puffer-Eintrag, kein Anspruch
                raise

    def gib_frei(self, poll_id: str, voter_key: str) -> None:
        """Nimmt einen gerade erhobenen Anspruch zurueck (Ausgleichsschritt).

        Nur fuer den Fall, dass der Board-Eintrag der Ausgabe in der anderen
        Datei fehlschlaegt: Ohne diesen Schritt waere die Berechtigung
        verbraucht, ohne dass jemand ein Token bekommen haette - der Fall, den
        beanspruche gerade ausschliessen soll.
        """
        with self._lock:
            self._conn.execute(
                "DELETE FROM eligibility WHERE poll_id = ? AND voter_key = ?",
                (poll_id, voter_key),
            )
            self._conn.execute(
                "DELETE FROM issue_retry WHERE poll_id = ? AND voter_key = ?",
                (poll_id, voter_key),
            )
            self._conn.commit()

    def anzahl_ansprueche(self, poll_id: str) -> int:
        """Ausgegebene Berechtigungen - die Eligibility-Haelfte der Abrechnung."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM eligibility WHERE poll_id = ?", (poll_id,)
            ).fetchone()
        return int(row["n"])

    # -- Wiederhol-Puffer der Ausgabe (EIP-T-070) ---------------------------
    def wiederhol_signatur(self, poll_id: str, voter_key: str, blinded_h: str) -> str | None:
        """Die zuvor ausgegebene Blindsignatur, wenn dieselbe verblindete
        Anfrage noch einmal kommt (EIP-T-070). Sonst ``None``.

        ``None`` heisst zweierlei und darf es auch: kein Puffer-Eintrag mehr
        (abgelaufen), oder ein *anderes* ``blinded_msg`` von einem bereits
        versorgten Ausweis. Beides endet in derselben Abweisung - der Aufrufer
        unterscheidet sie fuer das Debug-Modul, nicht fuer die Antwort.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT blind_sig FROM issue_retry "
                "WHERE poll_id = ? AND voter_key = ? AND blinded_h = ?",
                (poll_id, voter_key, blinded_h),
            ).fetchone()
        return row["blind_sig"] if row else None

    def verwirf_wiederhol_puffer(
        self, poll_id: str | None = None, aelter_als: datetime | None = None
    ) -> int:
        """Loescht Wiederhol-Eintraege und gibt zurueck, wie viele es waren.

        Ohne Argumente: alles. ``poll_id`` grenzt auf eine Umfrage ein (beim
        Schliessen - danach ist kein Token mehr etwas wert), ``aelter_als`` auf
        die abgelaufenen (Ablaufdurchlauf). Der Vergleich laeuft ueber den
        ISO-Text, der sortiert wie die Zeit.
        """
        bedingungen: list[str] = []
        werte: list[Any] = []
        if poll_id is not None:
            bedingungen.append("poll_id = ?")
            werte.append(poll_id)
        if aelter_als is not None:
            bedingungen.append("stunde < ?")
            werte.append(aelter_als.isoformat(timespec="seconds"))
        wo = (" WHERE " + " AND ".join(bedingungen)) if bedingungen else ""
        with self._lock:
            cur = self._conn.execute(f"DELETE FROM issue_retry{wo}", werte)
            self._conn.commit()
        return cur.rowcount

    def wiederhol_puffer_stand(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM issue_retry").fetchone()
        return int(row["n"])
