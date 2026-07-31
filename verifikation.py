"""Board-Pruefung - ohne Datenbank, ohne privaten Schluessel.

§7 sagt zu, dass jeder das veroeffentlichte Ergebnis nachrechnen kann. Solange
die Pruefung nur als Methodenbuendel auf PollService existiert, ist das eine
Behauptung: Sie haengt an SQLite und an dem Objekt, das den *privaten*
Signaturschluessel haelt. Dieses Modul loest sie heraus (EIP-T-045).

    pruefe(batches, options) -> Pruefbericht

Eine reine Funktion ueber die veroeffentlichten Batches. Ein Durchlauf
beantwortet alle Fragen, die das Board beantworten kann: Batch-Kette
(Merkle-Roots und ihre Verkettung, EIP-ADR-20260728-001), Token-Signaturen,
Ledger-Abrechnung, Auszaehlung, Token-Lookup.

Den oeffentlichen Schluessel bringt das Board seit EIP-T-069 selbst mit: Er
steht im POLL_OPEN-Eintrag und liegt damit im Merkle-Baum und in der
Batch-Kette. Das ist kein Selbstbezug, sondern eine Festlegung - der Eintrag
wird bei der Eroeffnung veroeffentlicht, also vor der ersten Teilnahme, und
ein spaeterer Tausch bricht die Kette. Weil der private Teil beim Schliessen
vernichtet wird (EIP-T-069), ist das Board zugleich der einzige Ort, an dem
der oeffentliche Teil die Umfrage sicher ueberlebt.

Auf der Kommandozeile ist das Modul das mitgelieferte Pruefwerkzeug:

    python3 verifikation.py board.json [--pubkey key.pem]

board.json liefert die App unter /api/board/{poll_id}. ``--pubkey`` ersetzt den
Schluessel nicht mehr, sondern **haelt dagegen**: Wer ihn aus einer
unabhaengigen Quelle hat, laesst pruefen, ob das Board denselben nennt. Eine
Abweichung ist ein Befund und macht das Ergebnis unbelastbar.

Das Board-*Format* selbst steht seit EIP-T-046 in board_eintrag.py: kanonisches
JSON, Blatt-Hash, Merkle-Baum, Batch-Kette, Konstruktoren und der Parser auf
typisierte Varianten. Dieses Modul deutet keinen Eintrag mehr selbst, es prueft
nur noch, was der Parser liefert.

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
    PollOpen,
    TokenIssued,
    Unlesbar,
    Vote,
    batch_root,
    canonical,
    leaf_hash,
    merkle_root,
    parse,
)

__all__ = [
    "GENESIS",
    "Accounting",
    "Batch",
    "BoardEntry",
    "ChainStatus",
    "Pruefbericht",
    "batches_from_export",
    "canonical",
    "pruefe",
    "pruefe_weiter",
    "schluessel_aus_board",
    "verify_batches",
]


@dataclass(frozen=True)
class Batch:
    """Ein veroeffentlichter Batch: Eintragsmenge plus die beiden Roots.

    ``n`` ist die Batch-Nummer (0-basiert, lueckenlos). ``merkle_root`` ist die
    Root ueber die Blatt-Hashes der Eintraege, ``batch_root`` das Kettenglied
    ueber den Vorgaenger (board_eintrag, ADR E1).
    """

    n: int
    merkle_root: str
    batch_root: str
    entries: tuple[BoardEntry, ...]


def verify_batches(batches: Sequence[Batch]) -> tuple[bool, int | None]:
    """Prueft Roots und Kette aller Batches. Gibt (ok, erster_defekter_batch) zurueck.

    Nachgerechnet wird alles aus den Payloads: Blatt-Hashes, Merkle-Root,
    Kettenglied. Die gespeicherten Roots sind Behauptungen, die hier gegen die
    Eintraege geprueft werden - nicht umgekehrt.
    """
    prev = GENESIS
    for erwartet_n, batch in enumerate(batches):
        if batch.n != erwartet_n or not batch.entries:
            return False, batch.n
        leaves = [leaf_hash(e.payload) for e in batch.entries]
        if merkle_root(leaves) != batch.merkle_root:
            return False, batch.n
        if batch_root(batch.merkle_root, prev) != batch.batch_root:
            return False, batch.n
        prev = batch.batch_root
    return True, None


def schluessel_aus_board(
    batches: Sequence[Batch],
) -> tuple[rsa.RSAPublicKey | None, str | None, str | None]:
    """Holt den Token-Schluessel der Umfrage aus ihrem POLL_OPEN-Eintrag.

    Rueckgabe: ``(Schluessel, PEM, Fehler)`` - bei einem Fehler sind die ersten
    beiden ``None``.

    Gesucht wird ueber alle Batches, nicht nur im ersten: Die Reihenfolge
    *innerhalb* eines Batches gibt es nicht (ADR E1), und ein Board, das mit
    einem anderen Batch beginnt, ist kaputt und nicht still zu deuten. Genau
    ein POLL_OPEN muss es geben - zwei hiessen zwei Schluessel fuer dieselbe
    Umfrage, und welcher gilt, waere Auslegung.
    """
    offen = [
        eintrag
        for batch in batches
        for entry in batch.entries
        if isinstance(eintrag := parse(entry), PollOpen)
    ]
    if not offen:
        return None, None, "Kein POLL_OPEN-Eintrag im Board - kein Token-Schluessel (EIP-T-069)"
    if len(offen) > 1:
        return None, None, f"{len(offen)} POLL_OPEN-Eintraege im Board - Schluessel nicht eindeutig"
    pem = offen[0].pubkey
    try:
        from cryptography.hazmat.primitives import serialization

        key = serialization.load_pem_public_key(pem.encode())
    except Exception as exc:
        return None, pem, f"Token-Schluessel im Board nicht lesbar: {exc}"
    if not isinstance(key, rsa.RSAPublicKey):
        return None, pem, "Token-Schluessel im Board ist kein RSA-Schluessel"
    return key, pem, None


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
    """Zustand der Batch-Kette und der Token-Signaturen.

    ``broken_at`` ist die Nummer des ersten Batches, dessen Root oder
    Kettenglied nicht zu seinen Eintraegen passt. ``bad_signature_at`` ist der
    Blatt-Hash der ersten Stimme ohne gueltige Signatur - Eintraege haben keine
    Nummern mehr (ADR E1), der Blatt-Hash ist ihr Name.
    """

    ok: bool
    broken_at: int | None
    signatures_ok: bool
    bad_signature_at: str | None

    @property
    def sound(self) -> bool:
        return self.ok and self.signatures_ok


@dataclass(frozen=True)
class Pruefbericht:
    """Alles, was sich aus den Batches plus oeffentlichem Schluessel sagen laesst.

    ``counts`` ist die Auszaehlung ueber alle VOTE-Eintraege. Sie ist nur dann
    ein Ergebnis, wenn ``chain.sound`` gilt und weder ``unknown_choice`` noch
    ``unlesbar`` etwas melden - ansonsten ist sie die Zaehlung eines kaputten
    Boards. Wer sie veroeffentlicht, muss alles pruefen; ``result_ok`` fasst das
    zusammen.

    ``unlesbar`` haelt den ersten Eintrag, den board_eintrag.parse nicht deuten
    konnte, mitsamt Grund. Er zaehlt nirgends mit und macht das Ergebnis
    unbrauchbar - er verschwindet nicht still (EIP-T-046).

    ``schluessel_fehler`` meldet, dass der Token-Schluessel dieser Umfrage im
    Board fehlt, doppelt ist, nicht lesbar ist oder einem unabhaengig
    mitgegebenen Schluessel widerspricht (EIP-T-069). Ohne pruefbaren Schluessel
    ist keine Signatur pruefbar, also ist auch kein Ergebnis belastbar.
    """

    batches: tuple[Batch, ...]
    chain: ChainStatus
    accounting: Accounting
    votes: tuple[tuple[str, tuple[str, ...]], ...]
    counts: dict[str, int]
    unknown_choice: str | None
    unlesbar: Unlesbar | None = None
    schluessel_pem: str | None = None
    schluessel_fehler: str | None = None

    @property
    def entries(self) -> tuple[BoardEntry, ...]:
        return tuple(e for b in self.batches for e in b.entries)

    @property
    def n_entries(self) -> int:
        return sum(len(b.entries) for b in self.batches)

    @property
    def n_batches(self) -> int:
        return len(self.batches)

    @property
    def result_ok(self) -> bool:
        return (
            self.chain.sound
            and self.unknown_choice is None
            and self.unlesbar is None
            and self.schluessel_fehler is None
        )

    def lookup(self, token_hex: str) -> list[str] | None:
        """Individuelle Verifizierbarkeit: eigenes Token im Board finden.

        Findet nur Veroeffentlichtes: Zwischen Abgabe und naechstem Batch traegt
        der signierte Beleg den Nachweis, nicht das Board (ADR E4).
        """
        token_hex = token_hex.strip().lower()
        return next((list(c) for t, c in self.votes if t == token_hex), None)


def pruefe(
    batches: Iterable[Batch],
    options: Sequence[str] | None = None,
    erwarteter_schluessel: rsa.RSAPublicKey | None = None,
) -> Pruefbericht:
    """Prueft die veroeffentlichten Batches in einem Durchlauf.

    ``options`` sind die Optionen der Umfrage. Sind sie bekannt, enthaelt
    ``counts`` jede Option (auch mit 0) und eine Stimme fuer etwas anderes
    landet in ``unknown_choice``. Ohne ``options`` zaehlt der Bericht nur, was
    tatsaechlich im Board steht - das ist die Sicht eines Dritten, der nur die
    Datei hat.

    ``erwarteter_schluessel`` ist der Token-Schluessel aus einer *unabhaengigen*
    Quelle. Er ersetzt den Schluessel im Board nicht, sondern wird dagegen
    gehalten: Weicht er ab, ist das ein Befund (EIP-T-069).

    Diese Funktion prueft immer alles ohne Vorbedingung. Sie ist die Pruefung,
    auf die sich §7 beruft; ``pruefe_weiter`` ist eine Abkuerzung fuer den
    laufenden Betrieb, kein Ersatz.
    """
    return _pruefe(list(batches), options, erwarteter_schluessel, vorher=None)


def pruefe_weiter(
    vorher: Pruefbericht,
    batches: Iterable[Batch],
    options: Sequence[str] | None = None,
    erwarteter_schluessel: rsa.RSAPublicKey | None = None,
) -> Pruefbericht:
    """Schreibt einen Bericht auf das gewachsene Board fort (EIP-T-051).

    ``batches`` ist das **ganze** veroeffentlichte Board, nicht nur der Zuwachs.
    Roots und Kette werden darueber vollstaendig neu geprueft - sie sind billig,
    und nur sie entlarven einen nachtraeglich umgeschriebenen Eintrag. Gespart
    werden die Signaturpruefungen der Batches, die in ``vorher`` schon geprueft
    wurden: RSASSA-PSS ueber jede Stimme bei jeder Stimme ist das quadratische
    Stueck.

    Passt ``vorher`` nicht zum Board - weniger Batches, letzte Root
    ausgetauscht - laeuft die Vollpruefung. Der Aufrufer muss das nicht wissen.
    """
    batches = list(batches)
    k = len(vorher.batches)
    passt = len(batches) >= k and (
        k == 0 or batches[k - 1].batch_root == vorher.batches[k - 1].batch_root
    )
    return _pruefe(
        batches, options, erwarteter_schluessel, vorher=vorher if passt else None
    )


def _pruefe(
    batches: list[Batch],
    options: Sequence[str] | None,
    erwarteter_schluessel: rsa.RSAPublicKey | None,
    vorher: Pruefbericht | None,
) -> Pruefbericht:
    """Gemeinsamer Durchlauf. Ohne ``vorher`` von vorn, sonst ab dessen Ende."""
    chain_ok, broken_at = verify_batches(batches)

    # Der Schluessel kommt aus dem Board selbst (EIP-T-069). Neu abgeleitet auch
    # beim Fortschreiben: Er ist die Grundlage jeder Signaturpruefung, und ein
    # Board, dessen POLL_OPEN sich unterwegs aendert, darf nicht deshalb
    # unbemerkt bleiben, weil der erste Durchlauf ihn schon gelesen hatte.
    public_key, schluessel_pem, schluessel_fehler = schluessel_aus_board(batches)
    if (
        schluessel_fehler is None
        and erwarteter_schluessel is not None
        and public_key is not None
        and erwarteter_schluessel.public_numbers() != public_key.public_numbers()
    ):
        schluessel_fehler = (
            "Der Token-Schluessel im Board ist nicht der erwartete - das Board gehoert zu "
            "einem anderen Schluessel als dem unabhaengig mitgegebenen"
        )
        public_key = None
    if vorher is None:
        ab = 0
        sig_ok: bool = True
        bad_sig_at: str | None = None
        n_eligible = 0
        votes: list[tuple[str, tuple[str, ...]]] = []
        counts: dict[str, int] = {opt: 0 for opt in (options or [])}
        unknown_choice: str | None = None
        unlesbar: Unlesbar | None = None
    else:
        ab = len(vorher.batches)
        sig_ok, bad_sig_at = vorher.chain.signatures_ok, vorher.chain.bad_signature_at
        n_eligible = vorher.accounting.n_eligible
        votes = list(vorher.votes)
        counts = dict(vorher.counts)
        unknown_choice = vorher.unknown_choice
        unlesbar = vorher.unlesbar

    for batch in batches[ab:]:
        for entry in batch.entries:
            eintrag = parse(entry)

            if isinstance(eintrag, Unlesbar):
                # Nicht ueberspringen: ein Eintrag, den niemand deuten kann,
                # waere sonst dasselbe wie ein Eintrag, den es nicht gibt - und
                # damit ein Weg, Stimmen durch Kaputtschreiben verschwinden zu
                # lassen.
                if unlesbar is None:
                    unlesbar = eintrag
                continue
            if isinstance(eintrag, TokenIssued):
                n_eligible += 1
                continue
            if not isinstance(eintrag, Vote):
                continue

            # Signaturpruefung: der erste Fehlschlag zaehlt, danach wird nicht
            # weiter geprueft - die Aussage "hier stimmt etwas nicht" reicht,
            # und bei einem manipulierten Board waere jede weitere PSS-Pruefung
            # nur Rechenzeit.
            if (
                sig_ok
                and public_key is not None
                and not blind.verify(public_key, eintrag.token, eintrag.sig)
            ):
                sig_ok, bad_sig_at = False, entry.leaf_hash

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

    # Ohne pruefbaren Schluessel ist keine Signatur geprueft. "alle gueltig" zu
    # melden, weil nichts geprueft werden konnte, waere die gefaehrlichste
    # Variante des Berichts - der Grund steht in schluessel_fehler.
    if public_key is None:
        sig_ok = False

    return Pruefbericht(
        batches=tuple(batches),
        chain=ChainStatus(
            ok=chain_ok, broken_at=broken_at, signatures_ok=sig_ok, bad_signature_at=bad_sig_at
        ),
        accounting=Accounting(n_eligible=n_eligible, n_votes=len(votes)),
        votes=tuple(votes),
        counts=counts,
        unknown_choice=unknown_choice,
        unlesbar=unlesbar,
        schluessel_pem=schluessel_pem,
        schluessel_fehler=schluessel_fehler,
    )


# ---------------------------------------------------------------------------
# Pruefwerkzeug fuer Dritte
# ---------------------------------------------------------------------------


def batches_from_export(export: dict[str, Any]) -> list[Batch]:
    """Batches aus dem JSON-Export von /api/board/{poll_id}.

    Eintraege stehen im Export nur als Payload-Zeilen; die Blatt-Hashes werden
    hier nachgerechnet statt gelesen - der Export behauptet, die Pruefung
    rechnet.
    """
    return [
        Batch(
            n=int(b["batch"]),
            merkle_root=str(b["merkle_root"]),
            batch_root=str(b["batch_root"]),
            entries=tuple(
                BoardEntry(payload=str(p), leaf_hash=leaf_hash(str(p)), batch=int(b["batch"]))
                for p in b.get("entries", [])
            ),
        )
        for b in export.get("batches", [])
    ]


def _report_lines(export: dict[str, Any], bericht: Pruefbericht, key_source: str) -> list[str]:
    chain = bericht.chain
    acc = bericht.accounting
    lines = [
        f"Umfrage:          {export.get('poll', '?')}",
        f"Frage:            {export.get('question', '?')}",
        f"Status:           {'geschlossen' if export.get('closed') else 'offen'}",
        f"Batches:          {bericht.n_batches} mit {bericht.n_entries} Eintraegen",
        f"Token-Schluessel: aus dem Board (POLL_OPEN), {key_source}",
        "",
        f"Batch-Kette:      {'intakt' if chain.ok else f'GEBROCHEN in Batch {chain.broken_at}'}",
        f"Token-Signaturen: "
        + (
            "alle gueltig"
            if chain.signatures_ok
            else f"UNGUELTIG in Blatt {str(chain.bad_signature_at)[:16]}..."
        ),
        f"Abrechnung:       {acc.n_votes} Stimmen bei {acc.n_eligible} ausgegebenen Token"
        + ("" if acc.ok else f"  -> UEBERSCHUSS +{acc.surplus}"),
        "",
    ]
    if bericht.schluessel_fehler is not None:
        lines.append(f"SCHLUESSEL: {bericht.schluessel_fehler}")
    if bericht.unlesbar is not None:
        lines.append(
            f"Unlesbarer Eintrag {bericht.unlesbar.leaf[:16]}...: {bericht.unlesbar.grund}"
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
        help="Token-Schluessel dieser Umfrage als PEM, aus einer unabhaengigen Quelle. Er "
        "ersetzt den Schluessel im Board nicht, sondern wird dagegen gehalten: Weicht er ab, "
        "ist das ein Befund. Ohne die Angabe gilt der Schluessel aus dem Board - der steht "
        "seit EIP-T-069 im POLL_OPEN-Eintrag und damit in der Batch-Kette.",
    )
    parser.add_argument("--token", default=None, help="eigenes Stimm-Token (hex) im Board suchen")
    args = parser.parse_args(argv)

    export = json.loads(args.board.read_text(encoding="utf-8"))
    erwartet: rsa.RSAPublicKey | None = None
    if args.pubkey is not None:
        key = serialization.load_pem_public_key(args.pubkey.read_bytes())
        if not isinstance(key, rsa.RSAPublicKey):
            print("Kein RSA-Schluessel.")
            return 2
        erwartet, key_source = key, f"gegen {args.pubkey} geprueft"
    else:
        key_source = "kein unabhaengiger Schluessel mitgegeben (--pubkey)"

    bericht = pruefe(batches_from_export(export), export.get("options"), erwartet)
    print("\n".join(_report_lines(export, bericht, key_source)))

    if args.token:
        found = bericht.lookup(args.token)
        print()
        print(
            f"Token {args.token[:16]}...: {found}"
            if found is not None
            else f"Token {args.token[:16]}...: NICHT im Board (oder noch nicht veroeffentlicht)"
        )

    return 0 if (bericht.result_ok and bericht.accounting.ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
