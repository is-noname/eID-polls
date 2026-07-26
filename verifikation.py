"""Board-Format und seine Pruefung - ohne Datenbank, ohne privaten Schluessel.

§7 sagt zu, dass jeder das veroeffentlichte Ergebnis nachrechnen kann. Solange
die Pruefung nur als Methodenbuendel auf PollService existiert, ist das eine
Behauptung: Sie haengt an SQLite und an dem Objekt, das den *privaten*
Signaturschluessel haelt. Dieses Modul loest sie heraus (EIP-T-045).

    pruefe(entries, public_key, options) -> Pruefbericht

Eine reine Funktion ueber Board-Eintraege und den *oeffentlichen* Schluessel.
Ein Durchlauf beantwortet alle Fragen, die das Board beantworten kann:
Hash-Kette, Token-Signaturen, Ledger-Abrechnung, Auszaehlung, Token-Lookup.

Auf der Kommandozeile ist das Modul das mitgelieferte Pruefwerkzeug:

    python3 verifikation.py board.json [--pubkey key.pem]

board.json liefert die App unter /api/board/{poll_id}. Wer misstrauisch ist,
nimmt den oeffentlichen Schluessel nicht aus dieser Datei, sondern aus einer
unabhaengigen Quelle - dafuer ist --pubkey da.

Das Board-*Format* selbst steht seit EIP-T-046 in board_eintrag.py: kanonisches
JSON, Konstruktoren und der Parser auf typisierte Varianten. Dieses Modul deutet
keinen Eintrag mehr selbst, es prueft nur noch, was der Parser liefert. Die
Namen des Formats werden weiter re-exportiert, weil store.py und Aufrufer sie
neben der Pruefung erwarten.

Was dieses Modul absichtlich NICHT tut: abweisen. Es meldet Befunde, es wirft
keine Rejected. Ob ein Befund eine Anfrage abweist oder nur ins Debug-Modul
geht, entscheidet der Aufrufer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from cryptography.hazmat.primitives.asymmetric import rsa

import blind
from board_eintrag import (
    GENESIS,
    BoardEntry,
    TokenIssued,
    Unlesbar,
    Vote,
    canonical,
    entry_hash,
    parse,
)

__all__ = [
    "GENESIS",
    "Accounting",
    "BoardEntry",
    "ChainStatus",
    "Pruefbericht",
    "canonical",
    "entries_from_export",
    "entry_hash",
    "pruefe",
    "verify_chain",
]


def verify_chain(entries: Sequence[BoardEntry]) -> tuple[bool, int | None]:
    """Prueft die Kette. Gibt (ok, erster_defekter_index) zurueck."""
    prev = GENESIS
    for entry in entries:
        expected = entry_hash(entry.index, prev, entry.payload)
        if entry.prev_hash != prev or entry.entry_hash != expected:
            return False, entry.index
        prev = entry.entry_hash
    return True, None


# ---------------------------------------------------------------------------
# Befunde
# ---------------------------------------------------------------------------


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


@dataclass(frozen=True)
class Pruefbericht:
    """Alles, was sich aus Board plus oeffentlichem Schluessel sagen laesst.

    ``counts`` ist die Auszaehlung ueber alle VOTE-Eintraege. Sie ist nur dann
    ein Ergebnis, wenn ``chain.sound`` gilt und weder ``unknown_choice`` noch
    ``unlesbar`` etwas melden - ansonsten ist sie die Zaehlung eines kaputten
    Boards. Wer sie veroeffentlicht, muss alles pruefen; ``result_ok`` fasst das
    zusammen.

    ``unlesbar`` haelt den ersten Eintrag, den board_eintrag.parse nicht deuten
    konnte, mitsamt Grund. Er zaehlt nirgends mit und macht das Ergebnis
    unbrauchbar - er verschwindet nicht still (EIP-T-046).
    """

    entries: tuple[BoardEntry, ...]
    chain: ChainStatus
    accounting: Accounting
    votes: tuple[tuple[str, tuple[str, ...]], ...]
    counts: dict[str, int]
    unknown_choice: str | None
    unlesbar: Unlesbar | None = None

    @property
    def n_entries(self) -> int:
        return len(self.entries)

    @property
    def result_ok(self) -> bool:
        return self.chain.sound and self.unknown_choice is None and self.unlesbar is None

    def lookup(self, token_hex: str) -> list[str] | None:
        """Individuelle Verifizierbarkeit: eigenes Token im Board finden."""
        token_hex = token_hex.strip().lower()
        return next((list(c) for t, c in self.votes if t == token_hex), None)


def pruefe(
    entries: Iterable[BoardEntry],
    public_key: rsa.RSAPublicKey,
    options: Sequence[str] | None = None,
) -> Pruefbericht:
    """Prueft ein Board in einem Durchlauf.

    ``options`` sind die Optionen der Umfrage. Sind sie bekannt, enthaelt
    ``counts`` jede Option (auch mit 0) und eine Stimme fuer etwas anderes
    landet in ``unknown_choice``. Ohne ``options`` zaehlt der Bericht nur, was
    tatsaechlich im Board steht - das ist die Sicht eines Dritten, der nur die
    Datei hat.
    """
    entries = list(entries)

    chain_ok, broken_at = verify_chain(entries)
    sig_ok: bool = True
    bad_sig_at: int | None = None
    n_eligible = 0
    votes: list[tuple[str, tuple[str, ...]]] = []
    counts: dict[str, int] = {opt: 0 for opt in (options or [])}
    unknown_choice: str | None = None
    unlesbar: Unlesbar | None = None

    for entry in entries:
        eintrag = parse(entry)

        if isinstance(eintrag, Unlesbar):
            # Nicht ueberspringen: ein Eintrag, den niemand deuten kann, waere
            # sonst dasselbe wie ein Eintrag, den es nicht gibt - und damit ein
            # Weg, Stimmen durch Kaputtschreiben verschwinden zu lassen.
            if unlesbar is None:
                unlesbar = eintrag
            continue
        if isinstance(eintrag, TokenIssued):
            n_eligible += 1
            continue
        if not isinstance(eintrag, Vote):
            continue

        # Signaturpruefung: der erste Fehlschlag zaehlt, danach wird nicht
        # weiter geprueft - die Aussage "ab hier stimmt etwas nicht" reicht,
        # und bei einem manipulierten Board waere jede weitere PSS-Pruefung
        # nur Rechenzeit.
        if sig_ok and not blind.verify(public_key, eintrag.token, eintrag.sig):
            sig_ok, bad_sig_at = False, entry.index

        # Zaehlung unabhaengig davon: eine Stimme mit ungueltiger Signatur
        # zaehlt mit und macht das Board unbrauchbar, statt still zu
        # verschwinden.
        votes.append((eintrag.token_hex, eintrag.choices))
        for choice in eintrag.choices:
            if choice in counts:
                counts[choice] += 1
            elif options is None:
                counts[choice] = 1
            elif unknown_choice is None:
                unknown_choice = choice

    return Pruefbericht(
        entries=tuple(entries),
        chain=ChainStatus(
            ok=chain_ok, broken_at=broken_at, signatures_ok=sig_ok, bad_signature_at=bad_sig_at
        ),
        accounting=Accounting(n_eligible=n_eligible, n_votes=len(votes)),
        votes=tuple(votes),
        counts=counts,
        unknown_choice=unknown_choice,
        unlesbar=unlesbar,
    )


# ---------------------------------------------------------------------------
# Pruefwerkzeug fuer Dritte
# ---------------------------------------------------------------------------


def entries_from_export(export: dict[str, Any]) -> list[BoardEntry]:
    """Board-Eintraege aus dem JSON-Export von /api/board/{poll_id}."""
    return [
        BoardEntry(
            index=int(e["index"]),
            prev_hash=str(e["prev_hash"]),
            payload=str(e["payload"]),
            entry_hash=str(e["entry_hash"]),
        )
        for e in export.get("entries", [])
    ]


def _report_lines(export: dict[str, Any], bericht: Pruefbericht, key_source: str) -> list[str]:
    chain = bericht.chain
    acc = bericht.accounting
    lines = [
        f"Umfrage:          {export.get('poll', '?')}",
        f"Frage:            {export.get('question', '?')}",
        f"Status:           {'geschlossen' if export.get('closed') else 'offen'}",
        f"Board-Eintraege:  {bericht.n_entries}",
        f"Oeffentl. Schluessel aus: {key_source}",
        "",
        f"Hash-Kette:       {'intakt' if chain.ok else f'GEBROCHEN ab #{chain.broken_at}'}",
        f"Token-Signaturen: "
        + ("alle gueltig" if chain.signatures_ok else f"UNGUELTIG in #{chain.bad_signature_at}"),
        f"Abrechnung:       {acc.n_votes} Stimmen bei {acc.n_eligible} ausgegebenen Token"
        + ("" if acc.ok else f"  -> UEBERSCHUSS +{acc.surplus}"),
        "",
    ]
    if bericht.unlesbar is not None:
        lines.append(
            f"Unlesbarer Eintrag #{bericht.unlesbar.index}: {bericht.unlesbar.grund}"
        )
    if bericht.unknown_choice is not None:
        lines.append(f"Unbekannte Option im Board: '{bericht.unknown_choice}'")
    lines.append("Auszaehlung:" if bericht.result_ok else "Auszaehlung (NICHT belastbar):")
    for opt, n in sorted(bericht.counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"  {n:>5}  {opt}")
    lines.append("")
    lines.append(
        "Ergebnis belastbar: ja"
        if bericht.result_ok and acc.ok
        else "Ergebnis belastbar: NEIN - siehe Befunde oben"
    )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    from pathlib import Path

    from cryptography.hazmat.primitives import serialization

    parser = argparse.ArgumentParser(
        description="Prueft ein exportiertes Board (/api/board/{poll_id}) eigenstaendig nach."
    )
    parser.add_argument("board", type=Path, help="board.json")
    parser.add_argument(
        "--pubkey",
        type=Path,
        default=None,
        help="oeffentlicher Schluessel als PEM. Ohne diese Angabe wird der Schluessel aus "
        "board.json genommen - dann prueft man das Board nur gegen sich selbst.",
    )
    parser.add_argument("--token", default=None, help="eigenes Stimm-Token (hex) im Board suchen")
    args = parser.parse_args(argv)

    export = json.loads(args.board.read_text(encoding="utf-8"))
    if args.pubkey is not None:
        pem, key_source = args.pubkey.read_bytes(), str(args.pubkey)
    else:
        pem, key_source = str(export.get("public_key", "")).encode(), f"{args.board} (selbstbezueglich)"

    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, rsa.RSAPublicKey):
        print("Kein RSA-Schluessel.")
        return 2

    bericht = pruefe(entries_from_export(export), key, export.get("options"))
    print("\n".join(_report_lines(export, bericht, key_source)))

    if args.token:
        found = bericht.lookup(args.token)
        print()
        print(
            f"Token {args.token[:16]}...: {found}"
            if found is not None
            else f"Token {args.token[:16]}...: NICHT im Board"
        )

    return 0 if (bericht.result_ok and bericht.accounting.ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
