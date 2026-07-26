"""Das Board-Eintragsformat: bauen und lesen, an genau einer Stelle.

Das Board ist die einzige Auszaehlungsquelle (§7). Trotzdem hatte sein Format
lange kein Modul: ``BoardEntry.data`` gab ein rohes ``dict`` zurueck, und jede
Aufrufstelle entschied neu, was ein gueltiger Eintrag ist - der Auszaehler
anders als die Kettenpruefung, die Kettenpruefung anders als der Test. Ein
manipulierter Eintrag wurde damit dreifach verschieden behandelt (EIP-T-046).

Hier steht beides zusammen:

    poll_open/poll_closed/token_issued/vote(...) -> dict   (schreiben)
    parse(entry) -> Vote | TokenIssued | PollOpen | PollClosed | Unlesbar  (lesen)

Kanonisches JSON, Typ-Diskriminierung, Hex-Dekodierung und Feld-Validierung
liegen ausschliesslich in dieser Datei. Wer einen Eintrag deuten will, ruft
``parse``; wer einen schreiben will, ruft einen Konstruktor. Rohe Dicts baut
niemand mehr selbst.

Verhalten bei unlesbaren Eintraegen - genau eines, fuer alle Aufrufstellen:

    Ein Eintrag, der sich nicht als eine der vier Varianten lesen laesst, wird
    zu ``Unlesbar`` und **verschwindet nicht still**. Er zaehlt nirgends mit
    (weder als Stimme noch als Token-Ausgabe), und er ist ein Befund: das Board
    liefert kein belastbares Ergebnis mehr, bis er geklaert ist.

Das ist die strengere der beiden bisherigen Deutungen, und die einzige, die zu
§7 passt: Eine Zeile, die niemand lesen kann, darf nicht wie eine Zeile
aussehen, die es nicht gibt - sonst kann ein Betreiber Stimmen unsichtbar
machen, indem er sie kaputt schreibt.

Das Modul haengt an nichts: keine Datenbank, kein Schluessel, kein Netz. Ein
Dritter kann es zusammen mit verifikation.py allein aus dem Board-Export
benutzen.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, ClassVar, Sequence

GENESIS = "0" * 64

VOTE = "VOTE"
TOKEN_ISSUED = "TOKEN_ISSUED"
POLL_OPEN = "POLL_OPEN"
POLL_CLOSED = "POLL_CLOSED"
UNLESBAR = "UNLESBAR"


# ---------------------------------------------------------------------------
# Serialisierung und Kettenglied
# ---------------------------------------------------------------------------


def canonical(payload: dict[str, Any]) -> str:
    """Kanonische Serialisierung einer Board-Zeile - Teil des oeffentlichen Boards."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(index: int, prev_hash: str, payload: str) -> str:
    return hashlib.sha256(f"{index}|{prev_hash}|{payload}".encode()).hexdigest()


@dataclass(frozen=True)
class BoardEntry:
    """Eine Zeile des Boards, so wie sie gespeichert und exportiert wird."""

    index: int
    prev_hash: str
    payload: str
    entry_hash: str

    @property
    def kind(self) -> str:
        """Eintragstyp fuer die Anzeige. Unlesbares heisst 'UNLESBAR'."""
        return parse(self).kind


# ---------------------------------------------------------------------------
# Konstruktoren - die einzigen Stellen, an denen Payloads entstehen
# ---------------------------------------------------------------------------


def poll_open(poll_id: str, question: str, options: Sequence[str]) -> dict[str, Any]:
    return {
        "type": POLL_OPEN,
        "poll": poll_id,
        "question": question,
        "options": [str(o) for o in options],
    }


def poll_closed(poll_id: str) -> dict[str, Any]:
    return {"type": POLL_CLOSED, "poll": poll_id}


def token_issued(poll_id: str, n_eligible: int) -> dict[str, Any]:
    return {"type": TOKEN_ISSUED, "poll": poll_id, "n_eligible": int(n_eligible)}


def vote(poll_id: str, token: bytes, sig: bytes, choices: Sequence[str]) -> dict[str, Any]:
    """Stimme fuers Board. Die Optionen werden sortiert - die Reihenfolge des
    Anklickens darf im Board nicht sichtbar sein, sie waere ein Merkmal, an dem
    sich zwei Stimmen derselben Person aehneln koennten (§9)."""
    return {
        "type": VOTE,
        "poll": poll_id,
        "token": token.hex(),
        "sig": sig.hex(),
        "choices": sorted(str(c) for c in choices),
    }


# ---------------------------------------------------------------------------
# Varianten
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PollOpen:
    kind: ClassVar[str] = POLL_OPEN
    index: int
    poll: str
    question: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class PollClosed:
    kind: ClassVar[str] = POLL_CLOSED
    index: int
    poll: str


@dataclass(frozen=True)
class TokenIssued:
    kind: ClassVar[str] = TOKEN_ISSUED
    index: int
    poll: str
    n_eligible: int


@dataclass(frozen=True)
class Vote:
    kind: ClassVar[str] = VOTE
    index: int
    poll: str
    token: bytes
    sig: bytes
    choices: tuple[str, ...]

    @property
    def token_hex(self) -> str:
        return self.token.hex()


@dataclass(frozen=True)
class Unlesbar:
    """Eintrag, der sich nicht deuten laesst - siehe Modul-Docstring."""

    kind: ClassVar[str] = UNLESBAR
    index: int
    grund: str


Eintrag = PollOpen | PollClosed | TokenIssued | Vote | Unlesbar


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse(entry: BoardEntry) -> Eintrag:
    """Deutet eine Board-Zeile. Wirft nie - Fehler werden zu ``Unlesbar``."""
    try:
        data = json.loads(entry.payload)
    except (json.JSONDecodeError, TypeError):
        return Unlesbar(entry.index, "Payload ist kein JSON")
    if not isinstance(data, dict):
        return Unlesbar(entry.index, "Payload ist kein JSON-Objekt")

    kind = data.get("type")
    poll = data.get("poll")
    if not isinstance(poll, str):
        return Unlesbar(entry.index, "Feld 'poll' fehlt oder ist kein Text")

    if kind == VOTE:
        return _vote(entry.index, poll, data)
    if kind == TOKEN_ISSUED:
        n = data.get("n_eligible")
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            return Unlesbar(entry.index, "Feld 'n_eligible' fehlt oder ist keine Anzahl")
        return TokenIssued(entry.index, poll, n)
    if kind == POLL_OPEN:
        question = data.get("question")
        options = data.get("options")
        if not isinstance(question, str):
            return Unlesbar(entry.index, "Feld 'question' fehlt oder ist kein Text")
        if not isinstance(options, list) or not all(isinstance(o, str) for o in options):
            return Unlesbar(entry.index, "Feld 'options' fehlt oder ist keine Liste von Texten")
        return PollOpen(entry.index, poll, question, tuple(options))
    if kind == POLL_CLOSED:
        return PollClosed(entry.index, poll)

    return Unlesbar(entry.index, f"unbekannter Eintragstyp {kind!r}")


def _vote(index: int, poll: str, data: dict[str, Any]) -> Vote | Unlesbar:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return Unlesbar(index, "Feld 'choices' fehlt oder ist leer")
    if not all(isinstance(c, str) for c in choices):
        return Unlesbar(index, "Feld 'choices' enthaelt etwas, das kein Text ist")
    try:
        token = bytes.fromhex(str(data["token"]))
        sig = bytes.fromhex(str(data["sig"]))
    except KeyError as exc:
        return Unlesbar(index, f"Feld {exc.args[0]!r} fehlt")
    except ValueError:
        return Unlesbar(index, "Felder 'token'/'sig' sind kein Hex")
    if not token or not sig:
        return Unlesbar(index, "Felder 'token'/'sig' sind leer")
    return Vote(index, poll, token, sig, tuple(choices))
