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

Struktur seit EIP-ADR-20260728-001 (Merkle-Set mit Batch-Kette): Eintraege
haben **keine Eingangsreihenfolge** mehr. Ein Eintrag ist ein Blatt

    leaf(payload)     = SHA256(0x00 || canonical(payload))

und die Blaetter eines Batches bilden, aufsteigend nach Blatt-Hash sortiert,
einen Merkle-Baum

    node(left, right) = SHA256(0x01 || left || right)

(bei ungerader Knotenzahl wird der letzte Knoten durchgereicht, nicht
dupliziert - Duplizieren ist der CVE-2012-2459-Fehler von Bitcoin). Die Roots
der Batches bilden die einzige verbleibende Ordnung, eine Kette:

    batch_root(n) = SHA256(0x02 || merkle_root(n) || batch_root(n-1))
    batch_root(0) = SHA256(0x02 || merkle_root(0) || GENESIS)

Innerhalb eines Batches gibt es keine Reihenfolge (KODEX § 2), zwischen
Batches macht die Kette Loeschen erkennbar (§7, ADR Fund 3).

Verhalten bei unlesbaren Eintraegen - genau eines, fuer alle Aufrufstellen:

    Ein Eintrag, der sich nicht als eine der vier Varianten lesen laesst, wird
    zu ``Unlesbar`` und **verschwindet nicht still**. Er zaehlt nirgends mit
    (weder als Stimme noch als Token-Ausgabe), und er ist ein Befund: das Board
    liefert kein belastbares Ergebnis mehr, bis er geklaert ist.

Das Modul haengt an nichts: keine Datenbank, kein Schluessel, kein Netz. Ein
Dritter kann es zusammen mit verifikation.py allein aus dem Board-Export
benutzen.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Iterable, Sequence

GENESIS = "0" * 64

VOTE = "VOTE"
TOKEN_ISSUED = "TOKEN_ISSUED"
POLL_OPEN = "POLL_OPEN"
POLL_CLOSED = "POLL_CLOSED"
UNLESBAR = "UNLESBAR"

# Laenge des Nonce in TOKEN_ISSUED: 16 Bytes = 32 Hex-Zeichen. Der Nonce ersetzt
# die fruehere laufende Nummer ``n_eligible`` (ADR Fund 1): Er traegt keine
# Ordnung, macht die Blaetter aber eindeutig - ohne ihn waeren alle
# TOKEN_ISSUED-Eintraege einer Umfrage byte-identisch und der Baum verloere
# ihre Anzahl.
NONCE_HEX_LEN = 32


# ---------------------------------------------------------------------------
# Serialisierung, Blatt-Hash, Merkle-Baum, Batch-Kette
# ---------------------------------------------------------------------------


def canonical(payload: dict[str, Any]) -> str:
    """Kanonische Serialisierung einer Board-Zeile - Teil des oeffentlichen Boards."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def leaf_hash(payload: str) -> str:
    """Blatt-Hash eines Eintrags. 0x00-Praefix: Domain-Trennung gegen Second-Preimage."""
    return hashlib.sha256(b"\x00" + payload.encode()).hexdigest()


def _node(left: str, right: str) -> str:
    return hashlib.sha256(b"\x01" + bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


def merkle_root(leaves: Iterable[str]) -> str:
    """Merkle-Root ueber die Menge der Blatt-Hashes, aufsteigend sortiert.

    Der Blatt-Hash ist der Sortierschluessel (ADR E1): er existiert fuer jeden
    Eintragstyp und traegt keinen Bezug zur Eingangszeit. Ein leerer Batch ist
    kein Batch - veroeffentlicht wird nur, wenn etwas da ist.
    """
    ebene = sorted(leaves)
    if not ebene:
        raise ValueError("Merkle-Baum ueber leere Menge - ein Batch ist nie leer.")
    while len(ebene) > 1:
        naechste = [_node(ebene[i], ebene[i + 1]) for i in range(0, len(ebene) - 1, 2)]
        if len(ebene) % 2:
            naechste.append(ebene[-1])  # durchreichen, nicht duplizieren
        ebene = naechste
    return ebene[0]


def batch_root(merkle: str, prev_batch_root: str) -> str:
    """Kettenglied der Batch-Kette. 0x02-Praefix: eigene Domain."""
    return hashlib.sha256(
        b"\x02" + bytes.fromhex(merkle) + bytes.fromhex(prev_batch_root)
    ).hexdigest()


@dataclass(frozen=True)
class BoardEntry:
    """Eine Zeile des Boards, so wie sie gespeichert und exportiert wird.

    ``batch`` ist die Nummer des Batches, in dem der Eintrag veroeffentlicht
    ist - ``None``, solange er im Puffer auf die naechste Veroeffentlichung
    wartet. Eine Eingangsreihenfolge gibt es nicht (ADR E1).
    """

    payload: str
    leaf_hash: str
    batch: int | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any], batch: int | None = None) -> "BoardEntry":
        line = canonical(payload)
        return cls(payload=line, leaf_hash=leaf_hash(line), batch=batch)

    @property
    def kind(self) -> str:
        """Eintragstyp fuer die Anzeige. Unlesbares heisst 'UNLESBAR'."""
        return parse(self).kind


# ---------------------------------------------------------------------------
# Konstruktoren - die einzigen Stellen, an denen Payloads entstehen
# ---------------------------------------------------------------------------


def poll_open(
    poll_id: str,
    question: str,
    options: Sequence[str],
    pubkey_pem: str,
    min_anonymity_threshold: int,
    laufzeit_start: str,
    laufzeit_ende: str,
    auswertungsplan: str,
) -> dict[str, Any]:
    """Eroeffnung fuers Board - mit dem oeffentlichen Token-Schluessel dieser Umfrage.

    ``pubkey_pem`` gehoert hier hinein und nicht in die config-Tabelle
    (EIP-T-069): Der Eintrag liegt im Merkle-Baum und in der Batch-Kette, der
    Schluessel ist damit nach der Veroeffentlichung nicht mehr austauschbar,
    ohne dass die Kette bricht. Ein Schluessel in der Datenbank waere dagegen
    lautlos zu tauschen - und er muss die Vernichtung des privaten Teils beim
    Schliessen ueberleben, sonst ist die Auszaehlung danach nicht mehr
    nachpruefbar. Weil POLL_OPEN sofort veroeffentlicht wird, steht die
    Festlegung vor der ersten Teilnahme.

    ``min_anonymity_threshold`` steht aus demselben Grund hier (EIP-T-090,
    Basisidee §3.1): Eine Schwelle, die erst beim Auszaehlen gewaehlt wird, ist
    keine - sie waere nachtraeglich so zu setzen, dass das Warnlabel gerade
    ausbleibt. Im POLL_OPEN-Eintrag liegt sie unter der Merkle-Root und steht
    damit vor der ersten Stimme fest, nachrechenbar aus dem Export.

    ``laufzeit_start``/``laufzeit_ende`` und ``auswertungsplan`` sind die
    letzten beiden der fuenf Groessen aus KODEX § 7, die vor dem Start
    feststehen muessen (EIP-T-091, Verstoss V-006). Sie stehen hier aus einem
    Grund, der ueber "auch praktisch" hinausgeht: § 7 verbietet die
    "Verlaengerung einer laufenden Umfrage wegen des Zwischenstands" und
    "nachtraeglich hinzugefuegte Untergruppen-Auswertungen". Beides ist nur
    feststellbar, wenn die urspruengliche Zusage irgendwo liegt, wo sie nicht
    mehr zu bewegen ist. In einer Datenbankspalte waere sie es nicht - dort
    liesse sich ein Ende lautlos verschieben und ein Plan nachtraeglich
    erweitern, und der Verstoss haette keine Spur. Unter der Merkle-Root und in
    der Batch-Kette hat er eine: Wer sie aendert, bricht die Kette.

    Beide Zeitpunkte sind ISO 8601 mit Sekunden. Die Zeitzone bleibt die des
    Betreibersystems - eine Genauigkeit, die dieses Verfahren nicht herstellen
    kann, sollte es auch nicht behaupten.
    """
    return {
        "type": POLL_OPEN,
        "poll": poll_id,
        "question": question,
        "options": [str(o) for o in options],
        "pubkey": pubkey_pem,
        "min_anonymity_threshold": int(min_anonymity_threshold),
        "laufzeit_start": str(laufzeit_start),
        "laufzeit_ende": str(laufzeit_ende),
        "auswertungsplan": str(auswertungsplan),
    }


def poll_closed(poll_id: str) -> dict[str, Any]:
    return {"type": POLL_CLOSED, "poll": poll_id}


def token_issued(poll_id: str) -> dict[str, Any]:
    """Token-Ausgabe fuers Board. Der Nonce ersetzt die laufende Nummer (ADR E2):
    keine Ordnung im Payload, aber eindeutige Blaetter. Die Abrechnung zaehlt
    Eintraege, sie liest keinen Zaehler."""
    return {"type": TOKEN_ISSUED, "poll": poll_id, "nonce": secrets.token_hex(NONCE_HEX_LEN // 2)}


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
    leaf: str
    poll: str
    question: str
    options: tuple[str, ...]
    pubkey: str
    min_anonymity_threshold: int
    laufzeit_start: datetime
    laufzeit_ende: datetime
    auswertungsplan: str


@dataclass(frozen=True)
class PollClosed:
    kind: ClassVar[str] = POLL_CLOSED
    leaf: str
    poll: str


@dataclass(frozen=True)
class TokenIssued:
    kind: ClassVar[str] = TOKEN_ISSUED
    leaf: str
    poll: str
    nonce: str


@dataclass(frozen=True)
class Vote:
    kind: ClassVar[str] = VOTE
    leaf: str
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
    leaf: str
    grund: str


Eintrag = PollOpen | PollClosed | TokenIssued | Vote | Unlesbar


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse(entry: BoardEntry) -> Eintrag:
    """Deutet eine Board-Zeile. Wirft nie - Fehler werden zu ``Unlesbar``."""
    leaf = entry.leaf_hash
    try:
        data = json.loads(entry.payload)
    except (json.JSONDecodeError, TypeError):
        return Unlesbar(leaf, "Payload ist kein JSON")
    if not isinstance(data, dict):
        return Unlesbar(leaf, "Payload ist kein JSON-Objekt")

    kind = data.get("type")
    poll = data.get("poll")
    if not isinstance(poll, str):
        return Unlesbar(leaf, "Feld 'poll' fehlt oder ist kein Text")

    if kind == VOTE:
        return _vote(leaf, poll, data)
    if kind == TOKEN_ISSUED:
        nonce = data.get("nonce")
        if (
            not isinstance(nonce, str)
            or len(nonce) != NONCE_HEX_LEN
            or not _ist_hex(nonce)
        ):
            return Unlesbar(leaf, "Feld 'nonce' fehlt oder ist kein Hex fester Laenge")
        return TokenIssued(leaf, poll, nonce)
    if kind == POLL_OPEN:
        question = data.get("question")
        options = data.get("options")
        if not isinstance(question, str):
            return Unlesbar(leaf, "Feld 'question' fehlt oder ist kein Text")
        if not isinstance(options, list) or not all(isinstance(o, str) for o in options):
            return Unlesbar(leaf, "Feld 'options' fehlt oder ist keine Liste von Texten")
        pubkey = data.get("pubkey")
        if not isinstance(pubkey, str) or "PUBLIC KEY" not in pubkey:
            return Unlesbar(leaf, "Feld 'pubkey' fehlt oder ist kein PEM (EIP-T-069)")
        # Pflichtangabe wie 'pubkey': Fehlt sie, ist unbekannt, ab wann das
        # Warnlabel faellig waere - und ein stillschweigender Vorgabewert waere
        # genau die nachtraeglich gesetzte Schwelle, die der Eintrag verhindern
        # soll (EIP-T-090).
        schwelle = data.get("min_anonymity_threshold")
        if not isinstance(schwelle, int) or isinstance(schwelle, bool) or schwelle < 0:
            return Unlesbar(
                leaf,
                "Feld 'min_anonymity_threshold' fehlt oder ist keine nicht-negative "
                "Ganzzahl (EIP-T-090)",
            )
        # Laufzeit und Auswertungsplan sind Pflichtangaben wie die Schwelle
        # (EIP-T-091, KODEX § 7). Ein fehlendes Feld hier als "unbegrenzt" oder
        # "kein Plan" zu lesen, waere genau die Zusage, die nie gemacht wurde -
        # und gegen die sich dann auch kein Verstoss messen liesse.
        start = _zeitpunkt(data.get("laufzeit_start"))
        ende = _zeitpunkt(data.get("laufzeit_ende"))
        if start is None or ende is None:
            return Unlesbar(
                leaf,
                "Feld 'laufzeit_start'/'laufzeit_ende' fehlt oder ist kein ISO-8601-"
                "Zeitpunkt (EIP-T-091)",
            )
        if ende <= start:
            return Unlesbar(
                leaf, "Laufzeit endet nicht nach ihrem Beginn (EIP-T-091)"
            )
        plan = data.get("auswertungsplan")
        if not isinstance(plan, str) or not plan.strip():
            return Unlesbar(
                leaf, "Feld 'auswertungsplan' fehlt oder ist leer (EIP-T-091)"
            )
        return PollOpen(
            leaf, poll, question, tuple(options), pubkey, schwelle, start, ende, plan
        )
    if kind == POLL_CLOSED:
        return PollClosed(leaf, poll)

    return Unlesbar(leaf, f"unbekannter Eintragstyp {kind!r}")


def _zeitpunkt(wert: Any) -> datetime | None:
    """Ein ISO-8601-Zeitpunkt aus dem Payload, sonst ``None`` (EIP-T-091)."""
    if not isinstance(wert, str):
        return None
    try:
        return datetime.fromisoformat(wert)
    except ValueError:
        return None


def _ist_hex(s: str) -> bool:
    try:
        bytes.fromhex(s)
    except ValueError:
        return False
    return True


def _vote(leaf: str, poll: str, data: dict[str, Any]) -> Vote | Unlesbar:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return Unlesbar(leaf, "Feld 'choices' fehlt oder ist leer")
    if not all(isinstance(c, str) for c in choices):
        return Unlesbar(leaf, "Feld 'choices' enthaelt etwas, das kein Text ist")
    try:
        token = bytes.fromhex(str(data["token"]))
        sig = bytes.fromhex(str(data["sig"]))
    except KeyError as exc:
        return Unlesbar(leaf, f"Feld {exc.args[0]!r} fehlt")
    except ValueError:
        return Unlesbar(leaf, "Felder 'token'/'sig' sind kein Hex")
    if not token or not sig:
        return Unlesbar(leaf, "Felder 'token'/'sig' sind leer")
    return Vote(leaf, poll, token, sig, tuple(choices))
