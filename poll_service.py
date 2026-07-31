"""Serverseitiger Kern: zwei Ledger, Blindsignatur, Board als einzige Auszaehlungsquelle.

Uebernommen aus PROTOTYPE_two-ledger/poll_logic.py, mit den drei Aenderungen,
die dort als offen notiert waren:

  1. textbook-Chaum  ->  RFC 9474 (blind.py, dokumentierte Abweichung von §4)
  2. String-Board    ->  kanonisches JSON (store.py)
  3. Speicher        ->  SQLite (store.py)

Unveraendert und bewusst so: Der Vote-Ledger (`spent`) haelt nur verbrauchte
Tokens, keine Stimmen. Die Stimmen liegen ausschliesslich im Board, und tally()
rechnet ueber die verifizierte Kette - sonst prueft die Oeffentlichkeit eine
Struktur, die fuer das veroeffentlichte Ergebnis nicht massgeblich ist
(§7, Prototyp-Fund 1).

Die Auszaehlung selbst steht seit EIP-T-045 nicht mehr hier, sondern in
verifikation.py: eine reine Funktion ueber Board-Eintraege und den
*oeffentlichen* Schluessel, die jeder Dritte ohne diese Datenbank ausfuehren
kann. Dieser Kern liest das Board und uebersetzt Befunde in Abweisungen - was
gilt, entscheidet das Pruefmodul.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

import blind
import board_eintrag
from board_eintrag import BoardEntry, TokenIssued, Vote, canonical, parse
from debug import log
from store import PollRow, Store
from verifikation import (
    Accounting,
    Batch,
    ChainStatus,
    Pruefbericht,
    pruefe,
    pruefe_weiter,
    schluessel_aus_board,
)


class Rejected(Exception):
    """Server weist eine Anfrage regelkonform ab.

    ``status_code`` gilt nur fuer Seiten-Routen; die JSON-API antwortet
    einheitlich mit 400. Fehlender Betreiber-Nachweis ist 403, alles andere
    eine regulaere fachliche Abweisung.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


__all__ = ["Accounting", "Beleg", "ChainStatus", "PollService", "Pruefbericht", "Rejected"]

# Praefix der Umfrage-Schluessel in der config-Tabelle. Beide je Umfrage, beide
# vernichtet beim Schliessen:
#   POLL_SECRET  HMAC-Schluessel der Pseudonym-Ableitung (EIP-T-033, Baustein D)
#   POLL_KEY     privater Token-Signaturschluessel (EIP-T-069)
# Der *oeffentliche* Teil des Token-Schluessels steht nicht hier, sondern im
# POLL_OPEN-Eintrag des Boards: Er muss die Vernichtung ueberleben, sonst waere
# die Auszaehlung nach dem Schliessen nicht mehr nachpruefbar.
POLL_SECRET = "poll_secret:"
POLL_KEY = "poll_key:"


@dataclass(frozen=True)
class Beleg:
    """Signierter Inklusionsbeleg der Stimmabgabe (EIP-ADR-20260728-001, E4).

    Die Zusage: Das Blatt ``leaf`` erscheint im Batch ``batch`` des
    oeffentlichen Boards - spaetestens nach dem Zeitdeckel, in jedem Fall beim
    Schliessen der Umfrage. ``sig`` ist Ed25519 ueber das kanonische JSON
    ``{"batch":…,"leaf":…,"poll":…,"typ":"BELEG"}`` und offline pruefbar gegen
    den veroeffentlichten Beleg-Schluessel. Fehlt das Blatt spaeter, ist der
    Beleg der mathematische Nachweis dafuer - nicht nur eine Behauptung.
    """

    poll_id: str
    entry: BoardEntry
    batch: int
    sig_hex: str


class PollService:
    def __init__(
        self, db_path: Path, batch_k: int = 10, batch_deckel_s: int = 6 * 3600
    ) -> None:
        """``batch_k`` und ``batch_deckel_s`` sind die Parameter aus ADR E3:
        Mindest-Anonymitaetsmenge je Batch und Zeitdeckel, beide nach aussen zu
        nennen (Board-Seite, Beleg-Erklaertext)."""
        self.store = Store(db_path)
        self.batch_k = max(1, int(batch_k))
        self.batch_deckel_s = max(60, int(batch_deckel_s))
        # Letzter Bericht je Umfrage, damit der Abstimmpfad nicht bei jeder
        # Stimme jede fruehere Signatur neu prueft (EIP-T-051). Nur eine
        # Abkuerzung fuer den laufenden Betrieb: pruefbericht() prueft ohne
        # Vorbedingung und setzt den Stand hier neu.
        self._letzte_pruefung: dict[str, Pruefbericht] = {}
        self._verwirf_altschluessel()
        self.cookie_key = self._load_cookie_key()
        self._beleg_key = self._load_beleg_key()

    # -- Schluessel und Secret ueberleben den Neustart ----------------------
    def _verwirf_altschluessel(self) -> None:
        """Vernichtet die alten *globalen* Schluessel beim Start.

        Zwei Stueck, aus zwei Tickets, mit derselben Begruendung:

        ``server_secret`` (EIP-T-033, D) und ``token_key_pem`` (EIP-T-069).

        Bis Baustein D war ``voter_key = H(pseudonym | poll_id | server_secret)``
        mit einem *global und dauerhaft* gespeicherten Secret. Es war zwar pro
        Umfrage gesalzen, aber jederzeit nachrechenbar - auch Jahre spaeter,
        auch fuer alle Umfragen gleichzeitig. Wer die Datenbank hatte, hatte die
        Teilnahmehistorie je Ausweis.

        Das Secret hat seit der Umstellung keinen Zweck mehr, also darf es nicht
        liegenbleiben: Solange es da ist, bleiben die Eligibility-Zeilen alter
        Umfragen auf ihr Pseudonym zurueckrechenbar. Die Vernichtung *ist* der
        Migrationspfad - sie stellt fuer Altbestaende genau die Eigenschaft her,
        die D fuer neue Umfragen zusagt.

        Was das fuer eine bereits laufende Umfrage bedeutet, steht bei
        ``_poll_secret``: Sie kann keine Token mehr ausgeben. Das ist gewollt
        und faellt sofort auf, statt still eine Doppelabstimmung zu erlauben.

        Fuer ``token_key_pem`` gilt dasselbe eine Ebene hoeher (EIP-T-069): Ein
        globaler Signaturschluessel, der nie vernichtet wird, laesst sich nach
        dem Ende jeder Umfrage weiterbenutzen - der Betreiber koennte auch Jahre
        spaeter gueltige Token nachproduzieren, und ein Token aus Umfrage A
        gaelte in Umfrage B. Beides faellt mit Schluesseln je Umfrage weg, aber
        nur, wenn der alte nicht liegenbleibt.
        """
        if self.store.vernichte_config("server_secret"):
            log.info(
                "keys",
                "Altes globales server_secret vernichtet - Voter-Keys laufen jetzt ueber "
                "Umfrage-Schluessel (EIP-T-033, D).",
            )
        if self.store.vernichte_config("token_key_pem"):
            log.info(
                "keys",
                "Alter globaler Token-Signaturschluessel vernichtet - Tokens werden jetzt je "
                "Umfrage signiert und der Schluessel beim Schliessen vernichtet (EIP-T-069).",
            )

    def _load_cookie_key(self) -> bytes:
        """Eigener Schluessel fuer die Signatur der Sitzungscookies (EIP-T-048).

        Bis hierher signierte die HTTP-Schicht ihre Cookies mit
        ``voter_key("cookie", "session")`` - die Pseudonym-Ableitung aus §6 war
        damit nebenbei KDF fuer Sitzungen. Zwei Zwecke an einem Schluessel
        heisst: wer den einen austauschen will (etwa um alle Sitzungen zu
        entwerten), trifft den anderen mit. ``voter_key`` dient deshalb nur noch
        der Pseudonym-Ableitung.
        """
        stored = self.store.get_config("cookie_secret")
        if stored:
            return bytes.fromhex(stored)
        secret = secrets.token_bytes(32)
        self.store.set_config("cookie_secret", secret.hex())
        return secret

    # -- Token-Signaturschluessel je Umfrage (EIP-T-069) --------------------
    def _erzeuge_poll_key(self, poll_id: str) -> str:
        """Erzeugt das Schluesselpaar dieser Umfrage. Rueckgabe: das oeffentliche PEM.

        Der private Teil geht in die config-Tabelle und wird beim Schliessen
        vernichtet; der oeffentliche wandert vom Aufrufer in den
        POLL_OPEN-Eintrag des Boards und ueberlebt dort.
        """
        key = blind.generate_key()
        self.store.set_config(
            POLL_KEY + poll_id,
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ).decode(),
        )
        log.info(
            "keys",
            f"Token-Signaturschluessel fuer '{poll_id}' erzeugt (2048 Bit, RFC 9474) - gilt "
            "nur fuer diese Umfrage und wird beim Schliessen vernichtet.",
            poll=poll_id,
        )
        return (
            key.public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            .decode()
        )

    def _poll_key(self, poll_id: str) -> rsa.RSAPrivateKey:
        """Der private Signaturschluessel dieser Umfrage - nur zum Signieren.

        Bewusst **ohne Zwischenspeicher**: Ein Cache im Prozess wuerde den
        Schluessel ueber seine Vernichtung hinaus am Leben halten, und damit
        genau die Zusage aushebeln, um derentwillen er vernichtet wird. Die
        Kosten sind ein PEM-Parse je Token-Ausgabe, also einmal pro Person.
        """
        pem = self.store.get_config(POLL_KEY + poll_id)
        if pem is None:
            raise Rejected(
                "Fuer diese Umfrage gibt es keinen Signaturschluessel mehr. Entweder ist sie "
                "geschlossen - dann ist das so gewollt und der Schluessel wurde vernichtet, "
                "damit auch der Betreiber keine gueltigen Token mehr herstellen kann - oder "
                "sie stammt aus einem Datenbestand vor der Umstellung auf Schluessel je "
                "Umfrage. In beiden Faellen werden keine Stimm-Token mehr ausgegeben. Das "
                "oeffentliche Board bleibt unveraendert pruefbar."
            )
        # Ein unlesbarer Schluessel ist ein Zustand, den es geben kann
        # (beschaedigte Datei, halb eingespielte Sicherung) - und er darf die
        # Konsistenzpruefung nicht mitreissen, denn genau die schaut man in dem
        # Fall an. Deshalb eine Abweisung statt einer durchschlagenden Ausnahme.
        try:
            key = serialization.load_pem_private_key(pem.encode(), password=None)
        except (ValueError, TypeError) as exc:
            raise Rejected(
                f"Der Signaturschluessel der Umfrage '{poll_id}' ist nicht lesbar ({exc}). "
                "Es werden keine Stimm-Token ausgegeben, solange das nicht geklaert ist."
            ) from exc
        if not isinstance(key, rsa.RSAPrivateKey):
            raise Rejected(
                f"Der Signaturschluessel der Umfrage '{poll_id}' ist kein RSA-Schluessel."
            )
        return key

    def poll_pubkey(self, poll_id: str) -> rsa.RSAPublicKey:
        """Der oeffentliche Token-Schluessel dieser Umfrage - aus dem Board.

        Nicht aus der config-Tabelle: Dort stuende er neben dem privaten Teil
        und verschwaende mit ihm. Im Board liegt er im Merkle-Baum und in der
        Batch-Kette, ist also weder austauschbar noch verlierbar - und ein
        Dritter liest ihn aus derselben Quelle (verifikation.schluessel_aus_board).
        """
        key, _, fehler = schluessel_aus_board(self.store.veroeffentlichte_batches(poll_id))
        if key is None:
            raise Rejected(
                f"Der Token-Schluessel der Umfrage '{poll_id}' ist im Board nicht auffindbar "
                f"({fehler}). Ohne ihn ist keine Stimme pruefbar."
            )
        return key

    def poll_pubkey_pem(self, poll_id: str) -> str:
        _, pem, _ = schluessel_aus_board(self.store.veroeffentlichte_batches(poll_id))
        return pem or ""

    def poll_params(self, poll_id: str) -> tuple[int, int]:
        """(n, e) fuer das Blinding im Browser - die oeffentlichen Parameter
        genau dieser Umfrage."""
        zahlen = self.poll_pubkey(poll_id).public_numbers()
        return zahlen.n, zahlen.e

    def _load_beleg_key(self) -> ed25519.Ed25519PrivateKey:
        """Eigener Schluessel fuer die Beleg-Signatur (ADR-20260728-001, offener
        Punkt 4): ein Schluessel, ein Zweck (Muster EIP-T-048). Der Token-
        Schluessel signiert Berechtigungen, dieser hier die Zusage, dass ein
        Blatt veroeffentlicht wird - wer den einen tauscht, darf den anderen
        nicht mit entwerten."""
        pem = self.store.get_config("beleg_key_pem")
        if pem:
            key = serialization.load_pem_private_key(pem.encode(), password=None)
            assert isinstance(key, ed25519.Ed25519PrivateKey)
            return key
        key = ed25519.Ed25519PrivateKey.generate()
        self.store.set_config(
            "beleg_key_pem",
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ).decode(),
        )
        log.info("keys", "Neuer Beleg-Signaturschluessel erzeugt (Ed25519).")
        return key

    @property
    def beleg_public_key_pem(self) -> str:
        return (
            self._beleg_key.public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            .decode()
        )

    def _signiere_beleg(self, poll_id: str, entry: BoardEntry, batch: int) -> Beleg:
        botschaft = canonical(
            {"batch": batch, "leaf": entry.leaf_hash, "poll": poll_id, "typ": "BELEG"}
        )
        sig = self._beleg_key.sign(botschaft.encode())
        return Beleg(poll_id=poll_id, entry=entry, batch=batch, sig_hex=sig.hex())

    # -- Pseudonym-Ableitung (§6: keine umfrageuebergreifende Verkettung) ---
    def _erzeuge_poll_secret(self, poll_id: str) -> None:
        """Legt den Umfrage-Schluessel an. Genau einmal, beim Anlegen der Umfrage."""
        self.store.set_config(POLL_SECRET + poll_id, secrets.token_bytes(32).hex())

    def _poll_secret(self, poll_id: str) -> bytes:
        stored = self.store.get_config(POLL_SECRET + poll_id)
        if stored is None:
            # Bewusst *nicht* stillschweigend einen neuen Schluessel erzeugen.
            # Ein neuer Schluessel hiesse: alle bisherigen Eligibility-Zeilen
            # dieser Umfrage sind nicht mehr reproduzierbar, und jeder Ausweis
            # bekaeme ein zweites Token - die Doppelabstimmungssperre aus §6
            # waere lautlos weg. Lieber keine Token mehr als zwei pro Ausweis.
            raise Rejected(
                "Fuer diese Umfrage gibt es keinen Umfrage-Schluessel mehr. Entweder ist sie "
                "geschlossen - dann ist das so gewollt und der Schluessel wurde vernichtet - "
                "oder sie stammt aus einem Datenbestand vor der Umstellung auf "
                "Umfrage-Schluessel. In beiden Faellen werden keine Stimm-Token mehr "
                "ausgegeben. Das oeffentliche Board bleibt unveraendert pruefbar."
            )
        return bytes.fromhex(stored)

    def vernichte_poll_secret(self, poll_id: str) -> bool:
        """Vernichtet den Umfrage-Schluessel. Ab hier ist die Umfrage anonym.

        Der Kern von Baustein D: Danach sind die ``eligibility``-Zeilen dieser
        Umfrage auf kein Pseudonym mehr zurueckzurechnen - nicht durch uns,
        nicht durch eine Beschlagnahme, nicht durch ein Datenleck. Ueber
        Umfragen hinweg ist ein Meinungsprofil damit strukturell unmoeglich und
        nicht nur unerwuenscht.

        Die Grenze der Zusage steht bei ``Store.vernichte_config``: sie gilt fuer
        die Datenbankdatei. Fuer Sicherungskopien gilt seit EIP-T-067 die Regel
        aus EIP-RPT-20260731-002 §3.3 - keine Kopie, die diese Vernichtung
        ueberdauert, und wenn eine angelegt wird, dann ueber
        ``Store.kopiere_ohne_geheimnisse``. Die Zusage ist damit eine ueber
        einen Bestand und nicht mehr nur ueber eine Datei.
        """
        vernichtet = self.store.vernichte_config(POLL_SECRET + poll_id)
        if vernichtet:
            log.info(
                "keys",
                f"Umfrage-Schluessel fuer '{poll_id}' vernichtet - die Eligibility-Eintraege "
                "dieser Umfrage sind ab jetzt auf kein Pseudonym mehr zurueckrechenbar.",
                poll=poll_id,
            )
        return vernichtet

    def vernichte_poll_key(self, poll_id: str) -> bool:
        """Vernichtet den privaten Signaturschluessel. Ab hier ist die Auszaehlung eingefroren.

        Der Kern von EIP-T-069: Danach kann niemand mehr gueltige Stimm-Token
        fuer diese Umfrage herstellen - auch kein kompromittierter oder
        boeswilliger Betreiber, auch nicht mit der Datenbank in der Hand. Das
        Ballot-Stuffing-Restrisiko aus RFC §9 ist damit *zeitlich* begrenzt: Es
        besteht nur noch, solange die Umfrage laeuft. Waehrenddessen bleibt es
        bestehen und braucht verteilte Dritte (§12, EIP-T-039) - dieser Schritt
        ersetzt sie nicht.

        Der oeffentliche Teil bleibt im Board und damit pruefbar; die Grenze der
        Loeschzusage steht bei ``Store.vernichte_config``, die Regel fuer
        Sicherungskopien bei ``vernichte_poll_secret`` (EIP-T-067).
        """
        vernichtet = self.store.vernichte_config(POLL_KEY + poll_id)
        if vernichtet:
            log.info(
                "keys",
                f"Signaturschluessel fuer '{poll_id}' vernichtet - es koennen keine gueltigen "
                "Stimm-Token fuer diese Umfrage mehr hergestellt werden, auch nicht von uns. "
                "Der oeffentliche Teil bleibt im Board.",
                poll=poll_id,
            )
        return vernichtet

    def voter_key(self, pseudonym: str, poll_id: str) -> str:
        """Wahlberechtigungs-Schluessel aus dem Pseudonym.

        HMAC unter dem *Umfrage*-Schluessel, nicht mehr ein Hash unter einem
        globalen Secret (EIP-T-033, Befund 2). Die Umfrage-ID muss nicht mehr in
        die Eingabe: Der Schluessel selbst gehoert bereits genau einer Umfrage,
        und er ueberlebt sie nicht.
        """
        return hmac.new(self._poll_secret(poll_id), pseudonym.encode(), hashlib.sha256).hexdigest()

    # -- Umfragen ----------------------------------------------------------
    def poll(self, poll_id: str) -> PollRow:
        poll = self.store.poll(poll_id)
        if poll is None:
            raise Rejected(
                f"Die Umfrage '{poll_id}' gibt es nicht. Bitte den Link oder die Umfrage-ID "
                "pruefen."
            )
        return poll

    def polls(self) -> list[PollRow]:
        return self.store.polls()

    def create_poll(self, poll_id: str, question: str, options: list[str]) -> PollRow:
        poll_id = poll_id.strip()
        question = question.strip()
        options = [o.strip() for o in options if o.strip()]
        if not poll_id or not poll_id.replace("-", "").replace("_", "").isalnum():
            raise Rejected("Umfrage-ID: nur Buchstaben, Ziffern, '-' und '_'.")
        if not question:
            raise Rejected("Frage darf nicht leer sein.")
        if len(options) < 2:
            raise Rejected("Mindestens zwei Optionen noetig.")
        if len(set(options)) != len(options):
            raise Rejected("Optionen muessen verschieden sein.")
        if self.store.poll(poll_id) is not None:
            raise Rejected(f"Umfrage '{poll_id}' existiert bereits.")

        # Beide Schluessel vor der Umfrage: eine Umfrage, die es gibt, aber fuer
        # die noch keine Berechtigung ableitbar oder signierbar waere, gibt es
        # nicht.
        self._erzeuge_poll_secret(poll_id)
        pubkey_pem = self._erzeuge_poll_key(poll_id)
        self.store.create_poll(poll_id, question, options, datetime.now().isoformat(timespec="seconds"))
        self.store.puffer_eintrag(
            poll_id, board_eintrag.poll_open(poll_id, question, options, pubkey_pem)
        )
        # POLL_OPEN wird sofort veroeffentlicht: das Anlegen ist eine
        # Betreiberhandlung, ihr Zeitpunkt ist ohnehin oeffentlich (die Umfrage
        # erscheint auf der Startseite). Die Mindestmenge k schuetzt
        # Teilnahme-Eintraege, nicht Verwaltungsakte.
        self.store.publiziere(poll_id)
        log.info("poll", f"Umfrage '{poll_id}' angelegt.", options=options)
        return self.poll(poll_id)

    def close_poll(self, poll_id: str) -> None:
        poll = self.poll(poll_id)
        if poll.closed:
            raise Rejected("Umfrage ist bereits geschlossen.")
        self.store.close_poll(poll_id)
        self.store.puffer_eintrag(poll_id, board_eintrag.poll_closed(poll_id))
        # Beim Schliessen wird der gesamte Puffer sofort veroeffentlicht
        # (ADR E3): kein Beleg wartet ueber das Ende hinaus. Der letzte Batch
        # darf dabei k unterschreiten - das ist die dokumentierte Grenze des
        # Mechanismus, keine Luecke.
        batch = self.store.publiziere(poll_id)
        if batch is not None and len(batch.entries) < self.batch_k + 1:
            log.info(
                "batch",
                f"Letzter Batch {batch.n} von '{poll_id}' mit {len(batch.entries)} "
                f"Eintraegen veroeffentlicht (unter k={self.batch_k}, bei Schliessung "
                "zulaessig).",
                poll=poll_id,
            )
        # Erst schliessen, dann vernichten: Waere die Reihenfolge umgekehrt und
        # das Schliessen schluege fehl, liefe eine offene Umfrage ohne
        # Ableitungsschluessel weiter - sie koennte keine Token mehr ausgeben,
        # ohne dass jemand es angeordnet haette.
        #
        # Und erst *veroeffentlichen*, dann vernichten: Der Puffer oben enthaelt
        # Eintraege, deren Signaturen gegen den oeffentlichen Teil geprueft
        # werden - der liegt im Board und bleibt, aber die Reihenfolge haelt
        # auch dann, wenn spaeter jemand den Ablauf umbaut.
        self.vernichte_poll_secret(poll_id)
        self.vernichte_poll_key(poll_id)
        log.info("poll", f"Umfrage '{poll_id}' geschlossen.")

    # -- Batch-Veroeffentlichung (EIP-ADR-20260728-001, E3) -----------------
    def publiziere_wenn_faellig(self, poll_id: str) -> Batch | None:
        """Veroeffentlicht den Puffer, wenn k erreicht oder der Zeitdeckel
        abgelaufen ist. Wird nach jedem Puffer-Eintrag und periodisch (web.py,
        Hintergrundaufgabe) aufgerufen - der Deckel darf nicht davon abhaengen,
        dass zufaellig noch jemand vorbeikommt."""
        anzahl, seit = self.store.pending_stand(poll_id)
        if anzahl == 0:
            return None
        faellig_menge = anzahl >= self.batch_k
        faellig_zeit = seit is not None and (
            datetime.now() - seit >= timedelta(seconds=self.batch_deckel_s)
        )
        if not (faellig_menge or faellig_zeit):
            return None
        batch = self.store.publiziere(poll_id)
        if batch is not None:
            log.info(
                "batch",
                f"Batch {batch.n} von '{poll_id}' veroeffentlicht: "
                f"{len(batch.entries)} Eintraege "
                f"({'Mindestmenge k erreicht' if faellig_menge else 'Zeitdeckel'}).",
                poll=poll_id,
            )
        return batch

    def publiziere_faellige(self) -> None:
        """Zeitdeckel-Durchlauf ueber alle Umfragen (Hintergrundaufgabe)."""
        for p in self.polls():
            try:
                self.publiziere_wenn_faellig(p.poll_id)
            except Exception as exc:  # ein haengender Puffer ist genau der stille Fehler
                log.exception("batch", exc)

    # -- Phase A: Wahlberechtigung (mit Pseudonym) -------------------------
    def issue_blind_signature(self, poll_id: str, pseudonym: str, blinded_msg: bytes) -> bytes:
        poll = self.poll(poll_id)
        if poll.closed:
            raise Rejected(
                "Diese Umfrage ist bereits geschlossen - es werden keine Stimm-Token mehr "
                "ausgegeben. Das Ergebnis steht auf dem oeffentlichen Board."
            )

        key = self.voter_key(pseudonym, poll_id)
        # Signiert wird mit dem Schluessel *dieser* Umfrage (EIP-T-069): Ein
        # Token aus einer anderen Umfrage ist hier strukturell wertlos, und nach
        # dem Schliessen gibt es diesen Schluessel nicht mehr.
        signaturschluessel = self._poll_key(poll_id)
        zahlen = signaturschluessel.public_key().public_numbers()
        # Signieren steht vor dem Anspruch: es aendert nichts und darf deshalb
        # folgenlos scheitern. Umgekehrt waere bei einer ungueltigen Anfrage die
        # Berechtigung verbraucht, ohne dass jemand ein Token bekommen haette.
        try:
            blind_sig = blind.blind_sign(
                blinded_msg, zahlen.n, signaturschluessel.private_numbers().d
            )
        except ValueError as exc:
            raise Rejected(f"Verblindete Anfrage ungueltig: {exc}") from exc

        # Ein Ausweis, ein Token: pruefen, eintragen und im Board-Puffer
        # vermerken sind ein Schritt (store.beanspruche_berechtigung, EIP-T-047).
        vermerkt = self.store.beanspruche_berechtigung(
            poll_id, key, board_eintrag.token_issued(poll_id)
        )
        if vermerkt is None:
            raise Rejected(
                "Fuer diesen Ausweis wurde bereits eine Stimmberechtigung ausgegeben - eine "
                "zweite ist bewusst nicht vorgesehen: Der Server sieht das Stimm-Token nie in "
                "Klarschrift und kann einen ehrlichen Verlust nicht von einem nur versteckten "
                "Token unterscheiden. Wurde damit abgestimmt, steht die Stimme im "
                "oeffentlichen Board und laesst sich mit dem Beleg unter /verify pruefen."
            )
        # Bewusst ohne voter_key: fuer die Fehlersuche reicht "ein Token wurde
        # ausgegeben". Wer es war, zusammen mit dem Zeitstempel, waere die halbe
        # Zuordnung Person -> Stimme (EIP-T-018). Die Doppelabholung faellt
        # ohnehin ueber den Eligibility-Ledger auf, nicht ueber dieses Log.
        log.info("phase-a", f"Token blind signiert fuer '{poll_id}'.")
        self.publiziere_wenn_faellig(poll_id)
        return blind_sig

    # -- Phase B: Stimmabgabe (anonym) -------------------------------------
    def cast_vote(
        self, poll_id: str, token: bytes, sig: bytes, choices: list[str]
    ) -> Beleg:
        poll = self.poll(poll_id)
        if poll.closed:
            raise Rejected(
                "Diese Umfrage ist geschlossen - es werden keine Stimmen mehr angenommen. Das "
                "Ergebnis steht auf dem oeffentlichen Board."
            )
        if not choices:
            raise Rejected("Keine Option gewaehlt.")
        if len(set(choices)) != len(choices):
            raise Rejected("Doppelte Option im Stimmzettel.")
        if any(c not in poll.options for c in choices):
            raise Rejected("Ungueltiger Stimmzettel (unbekannte Option).")
        # Geprueft wird gegen den Schluessel aus dem Board - dieselbe Quelle, aus
        # der auch ein Dritter prueft, und die einzige, die das Schliessen
        # ueberlebt (EIP-T-069).
        if not blind.verify(self.poll_pubkey(poll_id), token, sig):
            raise Rejected("Token-Signatur ungueltig.")

        # Ein Token, eine Stimme: verbrauchen und in den Board-Puffer schreiben
        # sind ein Schritt (store.verbrauche_token, EIP-T-047).
        vermerkt = self.store.verbrauche_token(
            poll_id, token.hex(), board_eintrag.vote(poll_id, token, sig, choices)
        )
        if vermerkt is None:
            raise Rejected(
                "Dieses Stimm-Token ist bereits verbraucht - es wurde damit schon "
                "abgestimmt. Die erste Abgabe steht im oeffentlichen Board; eine zweite "
                "Stimme mit demselben Token ist nicht moeglich."
            )
        entry, zugesagter_batch = vermerkt
        # Der Beleg entsteht vor der Veroeffentlichungspruefung: Die Zusage
        # bindet den Betreiber ab der Annahme, nicht ab der Sichtbarkeit
        # (ADR E4). Jede Veroeffentlichung nimmt den ganzen Puffer mit, also
        # ist die zugesagte Batch-Nummer exakt, nicht nur eine Untergrenze.
        beleg = self._signiere_beleg(poll_id, entry, zugesagter_batch)
        log.info(
            "phase-b",
            f"Stimme fuer '{poll_id}' gepuffert (Batch {zugesagter_batch} zugesagt).",
            poll=poll_id,
        )
        self.publiziere_wenn_faellig(poll_id)
        self.check_consistency(poll_id)
        return beleg

    # -- Auszaehlung: ausschliesslich aus dem Board (§7) --------------------
    def board(self, poll_id: str) -> list[BoardEntry]:
        """Die veroeffentlichten Eintraege. Der Puffer gehoert nicht dazu -
        oeffentlich ist nur, was in einem Batch steht."""
        self.poll(poll_id)
        return [e for b in self.store.veroeffentlichte_batches(poll_id) for e in b.entries]

    def pruefbericht(self, poll_id: str) -> Pruefbericht:
        """Vollpruefung: ein Durchlauf ueber das ganze Board, alle Aussagen darin (§7).

        Den oeffentlichen Schluessel holt sich die Pruefung seit EIP-T-069 aus
        dem Board selbst - was hier gerechnet wird, rechnet ein Dritter mit
        verifikation.py und board.json aus derselben Quelle nach. Der private
        Schluessel kommt in der Pruefung nicht vor; sie laeuft deshalb auch
        nach seiner Vernichtung unveraendert.

        Ohne Vorbedingung und ohne Abkuerzung: jede Signatur wird geprueft,
        auch wenn dieselbe Stimme vor einer Sekunde schon geprueft wurde. Was
        veroeffentlicht wird - Ergebnis, Board-Seite, Export - haengt an dieser
        Methode, nicht an der fortgeschriebenen (EIP-T-051).
        """
        poll = self.poll(poll_id)
        bericht = pruefe(self.store.veroeffentlichte_batches(poll_id), poll.options)
        self._letzte_pruefung[poll_id] = bericht
        return bericht

    def laufender_bericht(self, poll_id: str) -> Pruefbericht:
        """Bericht fuer den laufenden Betrieb - Kette ganz, Signaturen nur die neuen.

        Fuer Anzeigen und die Aufsicht waehrend des Abstimmens. Die Grenzen
        stehen bei verifikation.pruefe_weiter; wer eine Aussage
        veroeffentlicht, nimmt pruefbericht().
        """
        return self._laufende_momentaufnahme(poll_id)[0]

    def _laufende_momentaufnahme(
        self, poll_id: str
    ) -> tuple[Pruefbericht, list[BoardEntry], int, int]:
        """(fortgeschriebener Bericht, Puffer, Eligibility-Ledger, Vote-Ledger)
        in einem Zug."""
        options = self.poll(poll_id).options
        batches, pending, db_eligible, spent = self.store.momentaufnahme(poll_id)
        vorher = self._letzte_pruefung.get(poll_id)
        bericht = (
            pruefe(batches, options)
            if vorher is None
            else pruefe_weiter(vorher, batches, options)
        )
        self._letzte_pruefung[poll_id] = bericht
        return bericht, pending, db_eligible, spent

    def board_votes(self, poll_id: str) -> list[tuple[str, list[str]]]:
        """Stimmen so, wie sie oeffentlich im Board stehen. Jeder kann das nachrechnen."""
        return [(token, list(choices)) for token, choices in self.pruefbericht(poll_id).votes]

    def participation(self, poll_id: str) -> int:
        return self.laufender_bericht(poll_id).accounting.n_votes

    def chain_status(self, poll_id: str) -> ChainStatus:
        return self.pruefbericht(poll_id).chain

    def tally(self, poll_id: str, bericht: Pruefbericht | None = None) -> dict[str, int]:
        poll = self.poll(poll_id)
        if not poll.closed:
            raise Rejected("Die Verteilung wird erst nach dem Ende der Umfrage angezeigt.")
        return self.tally_von(bericht if bericht is not None else self.pruefbericht(poll_id))

    @staticmethod
    def tally_von(bericht: Pruefbericht) -> dict[str, int]:
        """Uebersetzt Befunde in Abweisungen - die Zahlen kommen aus dem Bericht."""
        status = bericht.chain
        # Vor der Signaturpruefung: Fehlt der Schluessel, *konnte* keine
        # Signatur geprueft werden. "Signatur ungueltig" waere hier die falsche
        # Auskunft (EIP-T-069).
        if bericht.schluessel_fehler is not None:
            raise Rejected(
                f"{bericht.schluessel_fehler} - kein Ergebnis, solange das nicht geklaert ist."
            )
        if not status.ok:
            raise Rejected(
                f"Batch-Kette gebrochen in Batch {status.broken_at} - kein Ergebnis, solange "
                "das nicht geklaert ist."
            )
        if not status.signatures_ok:
            raise Rejected(
                f"Board-Eintrag {str(status.bad_signature_at)[:16]}... traegt keine gueltige "
                "Token-Signatur - kein Ergebnis, solange das nicht geklaert ist."
            )
        if bericht.unlesbar is not None:
            raise Rejected(
                f"Board-Eintrag {bericht.unlesbar.leaf[:16]}... ist nicht lesbar "
                f"({bericht.unlesbar.grund}) - kein Ergebnis, solange das nicht geklaert ist."
            )
        if bericht.unknown_choice is not None:
            raise Rejected(
                f"Board enthaelt unbekannte Option '{bericht.unknown_choice}' - kein Ergebnis."
            )
        return dict(bericht.counts)

    # -- Oeffentliche Abrechnung (§9) --------------------------------------
    def accounting(self, poll_id: str) -> Accounting:
        """Beide Zahlen aus dem Board - also aus dem, was jeder Dritte sieht.

        Gezaehlt wird ueber das ganze Board; nur die Signaturpruefung nutzt den
        laufenden Bericht. Die beiden Zahlen sind damit immer aktuell.
        """
        return self.laufender_bericht(poll_id).accounting

    def lookup(self, poll_id: str, token_hex: str) -> list[str] | None:
        """Individuelle Verifizierbarkeit: eigenes Token im Board finden."""
        return self.pruefbericht(poll_id).lookup(token_hex)

    def board_export(self, poll_id: str) -> dict[str, object]:
        """Das Board als Datei zum Selbernachrechnen (verifikation.py als CLI).

        ``public_key`` ist eine Bequemlichkeit und keine zweite Quelle: Der
        massgebliche Token-Schluessel steht seit EIP-T-069 im
        POLL_OPEN-*Eintrag* und damit unter der Merkle-Root, die diese Datei
        mitliefert. Das Pruefwerkzeug liest ihn von dort; wer einen Schluessel
        aus unabhaengiger Quelle hat, laesst ihn mit --pubkey dagegenhalten.
        """
        poll = self.poll(poll_id)
        return {
            "poll": poll.poll_id,
            "question": poll.question,
            "options": poll.options,
            "closed": poll.closed,
            "created": poll.created,
            "public_key": self.poll_pubkey_pem(poll_id),
            "beleg_public_key": self.beleg_public_key_pem,
            "batch_k": self.batch_k,
            "batch_deckel_s": self.batch_deckel_s,
            "batches": [
                {
                    "batch": b.n,
                    "merkle_root": b.merkle_root,
                    "batch_root": b.batch_root,
                    # Nur die Payload-Zeilen: Blatt-Hashes rechnet der Pruefer
                    # nach, statt sie zu glauben (verifikation.batches_from_export).
                    "entries": [e.payload for e in b.entries],
                }
                for b in self.store.veroeffentlichte_batches(poll_id)
            ],
        }

    # -- Inkonsistenzpruefung fuers Debug-Modul ----------------------------
    def check_consistency(self, poll_id: str, bericht: Pruefbericht | None = None) -> list[str]:
        """Vergleicht Board gegen internen Zustand. Findings gehen ins Debug-Modul.

        Der Bericht darf uebergeben werden, wenn der Aufrufer das Board ohnehin
        schon geprueft hat - sonst laeuft dieselbe Pruefung ein zweites Mal.
        Wer die Vollpruefung will, uebergibt ``pruefbericht(poll_id)``.

        Ohne uebergebenen Bericht laeuft die laufende Pruefung: Board und beide
        Ledger in einem Zug gelesen (store.momentaufnahme) und erst danach
        geprueft. Sonst liegen die teuren Signaturpruefungen zwischen den
        Lesezugriffen, und eine Stimme, die in genau diesem Moment dazukommt,
        sieht wie eine Inkonsistenz aus - eine Falschmeldung im Debug-Modul,
        ausgerechnet an der Stelle, die echte Manipulation anzeigen soll.
        """
        findings: list[str] = []
        if bericht is None:
            bericht, pending, db_eligible, spent = self._laufende_momentaufnahme(poll_id)
        else:
            db_eligible, spent = self.store.ledger_stand(poll_id)
            pending = self.store.pending(poll_id)

        status = bericht.chain
        if not status.ok:
            findings.append(f"Batch-Kette gebrochen in Batch {status.broken_at}")
        if not status.signatures_ok:
            findings.append(
                f"Ungueltige Token-Signatur in Eintrag {str(status.bad_signature_at)[:16]}..."
            )

        acc = bericht.accounting
        if not acc.ok:
            findings.append(
                f"Ledger-Abrechnung schief: {acc.n_votes} Stimmen bei {acc.n_eligible} "
                f"Berechtigten (+{acc.surplus})"
            )
        if bericht.unlesbar is not None:
            findings.append(
                f"Board-Eintrag {bericht.unlesbar.leaf[:16]}... nicht lesbar: "
                f"{bericht.unlesbar.grund}"
            )
        if bericht.unknown_choice is not None:
            findings.append(f"Board enthaelt unbekannte Option '{bericht.unknown_choice}'")

        # Puffer-Zustand (ADR E3/E4): Ein Beleg, dessen Batch nie erscheint,
        # ist genau der stille Fehler, den das Debug-Modul sichtbar machen muss.
        pending_tokens = sum(1 for e in pending if isinstance(parse(e), TokenIssued))
        pending_votes = sum(1 for e in pending if isinstance(parse(e), Vote))

        # Abrechnung inklusive Puffer: Eine eingeschleuste Stimme (§9) muss dem
        # Betreiber sofort auffallen, nicht erst mit dem naechsten Batch. Die
        # oeffentliche Abrechnung oben rechnet nur ueber Veroeffentlichtes -
        # diese hier ist die interne Fruehwarnung.
        if acc.n_votes + pending_votes > acc.n_eligible + pending_tokens:
            findings.append(
                f"Mehr Stimmen als Berechtigungen (inkl. Puffer): "
                f"{acc.n_votes + pending_votes} Stimmen bei "
                f"{acc.n_eligible + pending_tokens} Token-Ausgaben"
            )
        anzahl, seit = self.store.pending_stand(poll_id)
        if self.poll(poll_id).closed and anzahl:
            findings.append(
                f"Umfrage ist geschlossen, aber {anzahl} Eintraege warten noch im "
                "Puffer - beim Schliessen muss der Puffer vollstaendig veroeffentlicht werden"
            )
        if seit is not None and datetime.now() - seit > timedelta(
            seconds=self.batch_deckel_s + 15 * 60
        ):
            findings.append(
                f"Zeitdeckel ueberschritten: Puffer von '{poll_id}' wartet seit {seit} "
                f"({anzahl} Eintraege) - Veroeffentlichung haengt"
            )

        # Lebenszyklus des Umfrage-Schluessels (EIP-T-033, D). Beide Richtungen
        # sind Befunde: Ein Schluessel, der eine geschlossene Umfrage ueberlebt,
        # haelt die Rueckrechenbarkeit auf Pseudonyme am Leben, die wir nach
        # aussen ausschliessen. Ein fehlender Schluessel bei offener Umfrage
        # heisst, dass niemand mehr teilnehmen kann - was ohne diese Zeile eine
        # stille Abweisung pro Versuch waere statt eines sichtbaren Zustands.
        geschlossen = self.poll(poll_id).closed
        hat_schluessel = self.store.get_config(POLL_SECRET + poll_id) is not None
        if geschlossen and hat_schluessel:
            findings.append(
                "Umfrage ist geschlossen, aber ihr Umfrage-Schluessel existiert noch - "
                "Eligibility-Eintraege bleiben auf Pseudonyme zurueckrechenbar"
            )
        if not geschlossen and not hat_schluessel:
            findings.append(
                "Umfrage ist offen, aber ihr Umfrage-Schluessel fehlt - es koennen keine "
                "Stimm-Token mehr ausgegeben werden"
            )

        # Lebenszyklus des Signaturschluessels (EIP-T-069), dieselben zwei
        # Richtungen: Ueberlebt der private Teil das Schliessen, kann der
        # Betreiber weiter gueltige Token herstellen - die Auszaehlung waere
        # nicht eingefroren, obwohl wir nach aussen genau das sagen. Fehlt er
        # bei offener Umfrage, kann niemand mehr teilnehmen.
        hat_sig_key = self.store.get_config(POLL_KEY + poll_id) is not None
        if geschlossen and hat_sig_key:
            findings.append(
                "Umfrage ist geschlossen, aber ihr Signaturschluessel existiert noch - es "
                "koennen weiter gueltige Stimm-Token hergestellt werden, die Auszaehlung ist "
                "nicht eingefroren"
            )
        if not geschlossen and not hat_sig_key:
            findings.append(
                "Umfrage ist offen, aber ihr Signaturschluessel fehlt - es koennen keine "
                "Stimm-Token mehr ausgegeben werden"
            )

        # Der oeffentliche Teil muss im Board stehen und zum privaten passen.
        # Faellt das auseinander, sind entweder alle bisherigen Signaturen nicht
        # mehr pruefbar oder die naechsten waeren es nicht - beides still, wenn
        # es hier nicht auffiele.
        if bericht.schluessel_fehler is not None:
            findings.append(bericht.schluessel_fehler)
        elif hat_sig_key and bericht.batches:
            try:
                privat = self._poll_key(poll_id).public_key().public_numbers()
                if privat != self.poll_pubkey(poll_id).public_numbers():
                    findings.append(
                        "Der Signaturschluessel dieser Umfrage passt nicht zum oeffentlichen "
                        "Schluessel in ihrem POLL_OPEN-Eintrag - ausgegebene Token waeren "
                        "gegen das Board nicht pruefbar"
                    )
            except Rejected as exc:
                findings.append(str(exc))

        # Veroeffentlichtes plus Puffer muss den Ledgern entsprechen: der Puffer
        # ist Teil des Boards, nur noch nicht sichtbar.
        if acc.n_votes + pending_votes != spent:
            findings.append(
                f"Board zeigt {acc.n_votes} Stimmen (+{pending_votes} im Puffer), "
                f"Vote-Ledger {spent} verbrauchte Tokens"
            )
        if acc.n_eligible + pending_tokens != db_eligible:
            findings.append(
                f"Board zeigt {acc.n_eligible} Token-Ausgaben (+{pending_tokens} im Puffer), "
                f"Eligibility-Ledger {db_eligible}"
            )

        for finding in findings:
            log.inconsistency("konsistenz", finding, poll=poll_id)
        return findings

    def check_all(self) -> dict[str, list[str]]:
        """Alle Umfragen, jede voll geprueft.

        Das Debug-Modul ist die Stelle, an der ein Betreiber hinsieht, wenn er
        etwas vermutet - hier waere die Abkuerzung aus dem Abstimmpfad
        (EIP-T-051) an der falschen Stelle gespart.
        """
        return {
            p.poll_id: self.check_consistency(p.poll_id, self.pruefbericht(p.poll_id))
            for p in self.polls()
        }
