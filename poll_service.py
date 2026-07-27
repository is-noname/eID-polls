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
import secrets
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import blind
import board_eintrag
from board_eintrag import BoardEntry
from debug import log
from store import PollRow, Store
from verifikation import Accounting, ChainStatus, Pruefbericht, pruefe, pruefe_weiter


class Rejected(Exception):
    """Server weist eine Anfrage regelkonform ab.

    ``status_code`` gilt nur fuer Seiten-Routen; die JSON-API antwortet
    einheitlich mit 400. Fehlender Betreiber-Nachweis ist 403, alles andere
    eine regulaere fachliche Abweisung.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


__all__ = ["Accounting", "ChainStatus", "PollService", "Pruefbericht", "Rejected"]


class PollService:
    def __init__(self, db_path: Path) -> None:
        self.store = Store(db_path)
        # Letzter Bericht je Umfrage, damit der Abstimmpfad nicht bei jeder
        # Stimme jede fruehere Signatur neu prueft (EIP-T-051). Nur eine
        # Abkuerzung fuer den laufenden Betrieb: pruefbericht() prueft ohne
        # Vorbedingung und setzt den Stand hier neu.
        self._letzte_pruefung: dict[str, Pruefbericht] = {}
        self._secret = self._load_secret()
        self.cookie_key = self._load_cookie_key()
        self._key = self._load_key()
        pub = self._key.public_key().public_numbers()
        self.n, self.e = pub.n, pub.e
        self._d = self._key.private_numbers().d

    # -- Schluessel und Secret ueberleben den Neustart ----------------------
    def _load_secret(self) -> bytes:
        stored = self.store.get_config("server_secret")
        if stored:
            return bytes.fromhex(stored)
        secret = secrets.token_bytes(32)
        self.store.set_config("server_secret", secret.hex())
        return secret

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

    def _load_key(self) -> rsa.RSAPrivateKey:
        pem = self.store.get_config("token_key_pem")
        if pem:
            key = serialization.load_pem_private_key(pem.encode(), password=None)
            assert isinstance(key, rsa.RSAPrivateKey)
            return key
        key = blind.generate_key()
        self.store.set_config(
            "token_key_pem",
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ).decode(),
        )
        log.info("keys", "Neuer Token-Signaturschluessel erzeugt (2048 Bit, RFC 9474).")
        return key

    @property
    def public_key_pem(self) -> str:
        return (
            self._key.public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            .decode()
        )

    # -- Pseudonym-Ableitung (§6: keine umfrageuebergreifende Verkettung) ---
    def voter_key(self, pseudonym: str, poll_id: str) -> str:
        return hashlib.sha256(
            pseudonym.encode() + b"|" + poll_id.encode() + b"|" + self._secret
        ).hexdigest()

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

        self.store.create_poll(poll_id, question, options, datetime.now().isoformat(timespec="seconds"))
        self.store.append_board(poll_id, board_eintrag.poll_open(poll_id, question, options))
        log.info("poll", f"Umfrage '{poll_id}' angelegt.", options=options)
        return self.poll(poll_id)

    def close_poll(self, poll_id: str) -> None:
        poll = self.poll(poll_id)
        if poll.closed:
            raise Rejected("Umfrage ist bereits geschlossen.")
        self.store.close_poll(poll_id)
        self.store.append_board(poll_id, board_eintrag.poll_closed(poll_id))
        log.info("poll", f"Umfrage '{poll_id}' geschlossen.")

    # -- Phase A: Wahlberechtigung (mit Pseudonym) -------------------------
    def issue_blind_signature(self, poll_id: str, pseudonym: str, blinded_msg: bytes) -> bytes:
        poll = self.poll(poll_id)
        if poll.closed:
            raise Rejected(
                "Diese Umfrage ist bereits geschlossen - es werden keine Stimm-Token mehr "
                "ausgegeben. Das Ergebnis steht auf dem oeffentlichen Board."
            )

        key = self.voter_key(pseudonym, poll_id)
        # Signieren steht vor dem Anspruch: es aendert nichts und darf deshalb
        # folgenlos scheitern. Umgekehrt waere bei einer ungueltigen Anfrage die
        # Berechtigung verbraucht, ohne dass jemand ein Token bekommen haette.
        try:
            blind_sig = blind.blind_sign(blinded_msg, self.n, self._d)
        except ValueError as exc:
            raise Rejected(f"Verblindete Anfrage ungueltig: {exc}") from exc

        # Ein Ausweis, ein Token: pruefen, eintragen und aufs Board vermerken
        # sind ein Schritt (store.beanspruche_berechtigung, EIP-T-047).
        vermerkt = self.store.beanspruche_berechtigung(
            poll_id, key, lambda nummer: board_eintrag.token_issued(poll_id, nummer)
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
        return blind_sig

    # -- Phase B: Stimmabgabe (anonym) -------------------------------------
    def cast_vote(
        self, poll_id: str, token: bytes, sig: bytes, choices: list[str]
    ) -> BoardEntry:
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
        if not blind.verify(self._key.public_key(), token, sig):
            raise Rejected("Token-Signatur ungueltig.")

        # Ein Token, eine Stimme: verbrauchen und aufs Board schreiben sind ein
        # Schritt (store.verbrauche_token, EIP-T-047).
        entry = self.store.verbrauche_token(
            poll_id, token.hex(), board_eintrag.vote(poll_id, token, sig, choices)
        )
        if entry is None:
            raise Rejected(
                "Dieses Stimm-Token ist bereits verbraucht - es wurde damit schon "
                "abgestimmt. Die erste Abgabe steht im oeffentlichen Board; eine zweite "
                "Stimme mit demselben Token ist nicht moeglich."
            )
        log.info("phase-b", f"Stimme im Board vermerkt (#{entry.index}).", poll=poll_id)
        self.check_consistency(poll_id)
        return entry

    # -- Auszaehlung: ausschliesslich aus dem Board (§7) --------------------
    def board(self, poll_id: str) -> list[BoardEntry]:
        self.poll(poll_id)
        return self.store.board(poll_id)

    def pruefbericht(self, poll_id: str) -> Pruefbericht:
        """Vollpruefung: ein Durchlauf ueber das ganze Board, alle Aussagen darin (§7).

        Bewusst mit dem *oeffentlichen* Schluessel: was hier gerechnet wird,
        rechnet ein Dritter mit verifikation.py und board.json genauso nach -
        der private Schluessel kommt in der Pruefung nicht mehr vor.

        Ohne Vorbedingung und ohne Abkuerzung: jede Signatur wird geprueft,
        auch wenn dieselbe Stimme vor einer Sekunde schon geprueft wurde. Was
        veroeffentlicht wird - Ergebnis, Board-Seite, Export - haengt an dieser
        Methode, nicht an der fortgeschriebenen (EIP-T-051).
        """
        poll = self.poll(poll_id)
        bericht = pruefe(self.store.board(poll_id), self._key.public_key(), poll.options)
        self._letzte_pruefung[poll_id] = bericht
        return bericht

    def laufender_bericht(self, poll_id: str) -> Pruefbericht:
        """Bericht fuer den laufenden Betrieb - Kette ganz, Signaturen nur die neuen.

        Fuer Anzeigen und die Aufsicht waehrend des Abstimmens. Die Grenzen
        stehen bei verifikation.pruefe_weiter; wer eine Aussage
        veroeffentlicht, nimmt pruefbericht().
        """
        return self._laufende_momentaufnahme(poll_id)[0]

    def _laufende_momentaufnahme(self, poll_id: str) -> tuple[Pruefbericht, int, int]:
        """(fortgeschriebener Bericht, Eligibility-Ledger, Vote-Ledger) in einem Zug."""
        options = self.poll(poll_id).options
        entries, db_eligible, spent = self.store.momentaufnahme(poll_id)
        vorher = self._letzte_pruefung.get(poll_id)
        bericht = (
            pruefe(entries, self._key.public_key(), options)
            if vorher is None
            else pruefe_weiter(vorher, entries, self._key.public_key(), options)
        )
        self._letzte_pruefung[poll_id] = bericht
        return bericht, db_eligible, spent

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
        if not status.ok:
            raise Rejected(
                f"Board-Kette gebrochen ab Eintrag #{status.broken_at} - kein Ergebnis, solange "
                "das nicht geklaert ist."
            )
        if not status.signatures_ok:
            raise Rejected(
                f"Board-Eintrag #{status.bad_signature_at} traegt keine gueltige "
                "Token-Signatur - kein Ergebnis, solange das nicht geklaert ist."
            )
        if bericht.unlesbar is not None:
            raise Rejected(
                f"Board-Eintrag #{bericht.unlesbar.index} ist nicht lesbar "
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

        Enthaelt den oeffentlichen Schluessel der Bequemlichkeit halber mit.
        Wer dem Betreiber nicht glaubt, nimmt ihn woanders her - genau darum
        kennt das Pruefwerkzeug die Option --pubkey.
        """
        poll = self.poll(poll_id)
        return {
            "poll": poll.poll_id,
            "question": poll.question,
            "options": poll.options,
            "closed": poll.closed,
            "created": poll.created,
            "public_key": self.public_key_pem,
            "entries": [
                {
                    "index": e.index,
                    "prev_hash": e.prev_hash,
                    "payload": e.payload,
                    "entry_hash": e.entry_hash,
                }
                for e in self.store.board(poll_id)
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
            bericht, db_eligible, spent = self._laufende_momentaufnahme(poll_id)
        else:
            db_eligible, spent = self.store.ledger_stand(poll_id)

        status = bericht.chain
        if not status.ok:
            findings.append(f"Board-Kette gebrochen ab Eintrag #{status.broken_at}")
        if not status.signatures_ok:
            findings.append(f"Ungueltige Token-Signatur in Eintrag #{status.bad_signature_at}")

        acc = bericht.accounting
        if not acc.ok:
            findings.append(
                f"Ledger-Abrechnung schief: {acc.n_votes} Stimmen bei {acc.n_eligible} "
                f"Berechtigten (+{acc.surplus})"
            )
        if bericht.unlesbar is not None:
            findings.append(
                f"Board-Eintrag #{bericht.unlesbar.index} nicht lesbar: {bericht.unlesbar.grund}"
            )
        if bericht.unknown_choice is not None:
            findings.append(f"Board enthaelt unbekannte Option '{bericht.unknown_choice}'")

        board_votes = acc.n_votes
        if board_votes != spent:
            findings.append(
                f"Board zeigt {board_votes} Stimmen, Vote-Ledger {spent} verbrauchte Tokens"
            )
        if acc.n_eligible != db_eligible:
            findings.append(
                f"Board zeigt {acc.n_eligible} Token-Ausgaben, Eligibility-Ledger {db_eligible}"
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
