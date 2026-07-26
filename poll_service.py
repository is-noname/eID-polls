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
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import blind
from debug import log
from store import BoardEntry, PollRow, Store, canonical, verify_chain


class Rejected(Exception):
    """Server weist eine Anfrage regelkonform ab.

    ``status_code`` gilt nur fuer Seiten-Routen; die JSON-API antwortet
    einheitlich mit 400. Fehlender Betreiber-Nachweis ist 403, alles andere
    eine regulaere fachliche Abweisung.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Accounting:
    """Oeffentliche Ledger-Abrechnung gegen Ballot-Stuffing (§9)."""

    n_eligible: int
    n_votes: int

    @property
    def ok(self) -> bool:
        return self.n_votes <= self.n_eligible

    @property
    def surplus(self) -> int:
        return max(0, self.n_votes - self.n_eligible)


@dataclass(frozen=True)
class ChainStatus:
    ok: bool
    broken_at: int | None
    signatures_ok: bool
    bad_signature_at: int | None

    @property
    def sound(self) -> bool:
        return self.ok and self.signatures_ok


class PollService:
    def __init__(self, db_path: Path) -> None:
        self.store = Store(db_path)
        self._secret = self._load_secret()
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
        self.store.append_board(
            poll_id, {"type": "POLL_OPEN", "poll": poll_id, "question": question, "options": options}
        )
        log.info("poll", f"Umfrage '{poll_id}' angelegt.", options=options)
        return self.poll(poll_id)

    def close_poll(self, poll_id: str) -> None:
        poll = self.poll(poll_id)
        if poll.closed:
            raise Rejected("Umfrage ist bereits geschlossen.")
        self.store.close_poll(poll_id)
        self.store.append_board(poll_id, {"type": "POLL_CLOSED", "poll": poll_id})
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
        with self.store.lock:
            if self.store.has_eligibility(poll_id, key):
                raise Rejected(
                    "Fuer diesen Ausweis wurde bereits ein Stimm-Token abgeholt - ein zweites ist "
                    "bewusst nicht vorgesehen: Der Server sieht das Token nie in Klarschrift und "
                    "kann einen ehrlichen Verlust nicht von einem nur versteckten Token "
                    "unterscheiden. Geraet gewechselt oder Browserdaten geloescht? Die beim "
                    "Abholen gesicherte Stimm-Token-Datei auf dieser Seite wieder einlesen."
                )
            try:
                blind_sig = blind.blind_sign(blinded_msg, self.n, self._d)
            except ValueError as exc:
                raise Rejected(f"Verblindete Anfrage ungueltig: {exc}") from exc
            self.store.add_eligibility(poll_id, key)
            self.store.append_board(
                poll_id,
                {
                    "type": "TOKEN_ISSUED",
                    "poll": poll_id,
                    "n_eligible": self.store.count_eligibility(poll_id),
                },
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

        with self.store.lock:
            if self.store.is_spent(poll_id, token.hex()):
                raise Rejected(
                    "Dieses Stimm-Token ist bereits verbraucht - es wurde damit schon "
                    "abgestimmt. Die erste Abgabe steht im oeffentlichen Board; eine zweite "
                    "Stimme mit demselben Token ist nicht moeglich."
                )
            self.store.add_spent(poll_id, token.hex())
            entry = self.store.append_board(
                poll_id,
                {
                    "type": "VOTE",
                    "poll": poll_id,
                    "token": token.hex(),
                    "sig": sig.hex(),
                    "choices": sorted(choices),
                },
            )
        log.info("phase-b", f"Stimme im Board vermerkt (#{entry.index}).", poll=poll_id)
        self.check_consistency(poll_id)
        return entry

    # -- Auszaehlung: ausschliesslich aus dem Board (§7) --------------------
    def board(self, poll_id: str) -> list[BoardEntry]:
        self.poll(poll_id)
        return self.store.board(poll_id)

    def board_votes(self, poll_id: str) -> list[tuple[str, list[str]]]:
        """Stimmen so, wie sie oeffentlich im Board stehen. Jeder kann das nachrechnen."""
        votes = []
        for entry in self.board(poll_id):
            data = entry.data
            if data.get("type") == "VOTE" and "token" in data and "choices" in data:
                votes.append((str(data["token"]), list(data["choices"])))
        return votes

    def participation(self, poll_id: str) -> int:
        return len(self.board_votes(poll_id))

    def chain_status(self, poll_id: str) -> ChainStatus:
        entries = self.board(poll_id)
        ok, broken_at = verify_chain(entries)

        sig_ok, bad_at = True, None
        pub = self._key.public_key()
        for entry in entries:
            data = entry.data
            if data.get("type") != "VOTE":
                continue
            try:
                token = bytes.fromhex(str(data["token"]))
                sig = bytes.fromhex(str(data["sig"]))
            except (KeyError, ValueError):
                sig_ok, bad_at = False, entry.index
                break
            if not blind.verify(pub, token, sig):
                sig_ok, bad_at = False, entry.index
                break

        return ChainStatus(ok=ok, broken_at=broken_at, signatures_ok=sig_ok, bad_signature_at=bad_at)

    def tally(self, poll_id: str) -> dict[str, int]:
        poll = self.poll(poll_id)
        if not poll.closed:
            raise Rejected("Die Verteilung wird erst nach dem Ende der Umfrage angezeigt.")
        status = self.chain_status(poll_id)
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

        counts = {opt: 0 for opt in poll.options}
        for _token_hex, choices in self.board_votes(poll_id):
            for choice in choices:
                if choice not in counts:
                    raise Rejected(f"Board enthaelt unbekannte Option '{choice}' - kein Ergebnis.")
                counts[choice] += 1
        return counts

    # -- Oeffentliche Abrechnung (§9) --------------------------------------
    def accounting(self, poll_id: str) -> Accounting:
        """Beide Zahlen aus dem Board - also aus dem, was jeder Dritte sieht."""
        n_eligible = 0
        for entry in self.board(poll_id):
            if entry.data.get("type") == "TOKEN_ISSUED":
                n_eligible += 1
        return Accounting(n_eligible=n_eligible, n_votes=self.participation(poll_id))

    def lookup(self, poll_id: str, token_hex: str) -> list[str] | None:
        """Individuelle Verifizierbarkeit: eigenes Token im Board finden."""
        token_hex = token_hex.strip().lower()
        return next((c for t, c in self.board_votes(poll_id) if t == token_hex), None)

    # -- Test-Reset (nur Testbetrieb, siehe store.remove_eligibility) ------
    def reset_eligibility(self, poll_id: str, pseudonym: str) -> bool:
        self.poll(poll_id)
        key = self.voter_key(pseudonym, poll_id)
        removed = self.store.remove_eligibility(poll_id, key)
        if removed:
            log.info("admin", f"Testzugang fuer '{poll_id}' zurueckgesetzt.", poll=poll_id)
        return removed

    # -- Inkonsistenzpruefung fuers Debug-Modul ----------------------------
    def check_consistency(self, poll_id: str) -> list[str]:
        """Vergleicht Board gegen internen Zustand. Findings gehen ins Debug-Modul."""
        findings: list[str] = []
        status = self.chain_status(poll_id)
        if not status.ok:
            findings.append(f"Board-Kette gebrochen ab Eintrag #{status.broken_at}")
        if not status.signatures_ok:
            findings.append(f"Ungueltige Token-Signatur in Eintrag #{status.bad_signature_at}")

        acc = self.accounting(poll_id)
        if not acc.ok:
            findings.append(
                f"Ledger-Abrechnung schief: {acc.n_votes} Stimmen bei {acc.n_eligible} "
                f"Berechtigten (+{acc.surplus})"
            )

        board_votes = self.participation(poll_id)
        spent = self.store.count_spent(poll_id)
        if board_votes != spent:
            findings.append(
                f"Board zeigt {board_votes} Stimmen, Vote-Ledger {spent} verbrauchte Tokens"
            )
        db_eligible = self.store.count_eligibility(poll_id)
        if acc.n_eligible != db_eligible:
            findings.append(
                f"Board zeigt {acc.n_eligible} Token-Ausgaben, Eligibility-Ledger {db_eligible}"
            )

        for finding in findings:
            log.inconsistency("konsistenz", finding, poll=poll_id)
        return findings

    def check_all(self) -> dict[str, list[str]]:
        return {p.poll_id: self.check_consistency(p.poll_id) for p in self.polls()}

    # -- Manipulationsdemo, absichtlich exponiert (§9) ----------------------
    def demo_tamper_board(self, poll_id: str, index: int, new_choice: str) -> None:
        """Schreibt eine Board-Stimme um und laesst die Hashes stehen.

        Zeigt Fund 2 aus dem Prototyp: die Kette entlarvt genau diesen faulen
        Angreifer. Ein Betreiber mit Schreibzugriff wuerde die Hashes dahinter
        neu rechnen - dagegen hilft nur ein extern verankerter Merkle-Root (§12).
        """
        entries = self.board(poll_id)
        entry = next((e for e in entries if e.index == index), None)
        if entry is None:
            raise Rejected(f"Kein Board-Eintrag #{index}.")
        data = entry.data
        if data.get("type") != "VOTE":
            raise Rejected(f"Eintrag #{index} ist keine Stimme.")
        data["choices"] = [new_choice]
        self.store.overwrite_board_payload(poll_id, index, canonical(data))
        log.error("demo", f"Board-Eintrag #{index} manipuliert (Demo).", poll=poll_id)
        self.check_consistency(poll_id)

    def demo_stuff_ballot(self, poll_id: str, choice: str) -> None:
        """Betreiber signiert sich selbst ein Token - ohne Eligibility-Eintrag.

        Laeuft absichtlich durch denselben cast_vote-Pfad: das Token ist
        kryptografisch ununterscheidbar von einem echten. Nur die
        Ledger-Abrechnung entlarvt es (§9).
        """
        token = secrets.token_bytes(32)
        blinded, inv = blind.blind(token, self.n, self.e)
        sig = blind.finalize(blind.blind_sign(blinded, self.n, self._d), inv, self.n)
        self.cast_vote(poll_id, token, sig, [choice])
        log.error("demo", "Betreiber-Stimme ohne Berechtigung eingeschleust (Demo).", poll=poll_id)
