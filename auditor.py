#!/usr/bin/env python3
"""Unabhaengiger Auditor fuer ein veroeffentlichtes eID-Umfrage-Board.

Diese Datei gehoert absichtlich zu *keinem* Modul dieser App. Sie importiert
nichts aus dem Projekt, sondern rechnet das Board aus seiner oeffentlichen
Beschreibung nach - Blatt-Hash, Merkle-Baum, Batch-Kette, Signaturen,
Abrechnung, Auszaehlung. Wer verifikation.py benutzt, prueft mit dem Code der
Stelle, der er misstraut; das ist keine unabhaengige Pruefung, sondern eine
zweite Ausfuehrung derselben Behauptung (EIP-T-071).

    python3 auditor.py https://<instanz>/api/board/<poll-id>
    python3 auditor.py board.json --pubkey key.pem --token <hex>
    python3 auditor.py board.json --beleg beleg.json --belegkey beleg.pem

Was geprueft wird:

  1. Struktur   Blatt-Hashes, Merkle-Roots und Batch-Kette werden aus den
                Payloads neu gerechnet. Die im Export genannten Roots sind
                Behauptungen und werden dagegen gehalten.
  2. Schluessel Der Token-Schluessel kommt aus dem POLL_OPEN-*Eintrag* und liegt
                damit unter der Root. Das Feld "public_key" neben den Batches
                wird ignoriert - es steht ausserhalb des Baums.
  3. Signaturen Jede Stimme traegt eine RSASSA-PSS-Signatur (SHA-384,
                Salt-Laenge 0) ueber ihr Token. Sie ist eine gewoehnliche
                PSS-Signatur; die Blindsignatur ist nur ihr Entstehungsweg.
  4. Tokens     Kein Token darf zweimal im Board stehen. Das ist die einzige
                oeffentliche Sperre gegen Doppelabstimmung - der Ledger, der sie
                im Betrieb verhindert, ist von aussen nicht einsehbar.
  5. Abrechnung Nicht mehr Stimmen als ausgegebene Token (RFC §9).
  6. Ergebnis   Auszaehlung ueber die Stimmen, verglichen mit dem, was die
                Instanz unter /api/status veroeffentlicht.

Grenzen, die kein Skript aufheben kann: Das Board zeigt, dass die
veroeffentlichten Eintraege zueinander passen. Ob *alle* abgegebenen Stimmen
darin stehen, zeigt es nicht - dafuer braucht es die Belege der Waehlenden
(--beleg). Und ob die ausgegebenen Token an Berechtigte gingen, ist im Board
grundsaetzlich nicht sichtbar; das ist Phase A und liegt beim Betreiber.

Abhaengigkeiten: Standardbibliothek plus `cryptography` (RSA-PSS, Ed25519) -
eine fremde, gepruefte Bibliothek, kein Code dieses Projekts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from typing import Any, Iterable, Sequence

GENESIS = "0" * 64
TIMEOUT_S = 20


# ---------------------------------------------------------------------------
# Die Formatdefinition, unabhaengig nachgebaut (EIP-ADR-20260728-001)
# ---------------------------------------------------------------------------


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def blatt(payload: str) -> str:
    """SHA256(0x00 || payload) - Domain-Trennung gegen Second-Preimage."""
    return hashlib.sha256(b"\x00" + payload.encode()).hexdigest()


def knoten(links: str, rechts: str) -> str:
    return hashlib.sha256(b"\x01" + bytes.fromhex(links) + bytes.fromhex(rechts)).hexdigest()


def wurzel(blaetter: Iterable[str]) -> str:
    """Merkle-Root ueber die aufsteigend sortierte Blattmenge.

    Ein einzelner ungerader Knoten wird durchgereicht, nicht dupliziert
    (CVE-2012-2459).
    """
    ebene = sorted(blaetter)
    if not ebene:
        raise ValueError("Merkle-Baum ueber leere Menge")
    while len(ebene) > 1:
        naechste = [knoten(ebene[i], ebene[i + 1]) for i in range(0, len(ebene) - 1, 2)]
        if len(ebene) % 2:
            naechste.append(ebene[-1])
        ebene = naechste
    return ebene[0]


def kettenglied(merkle: str, vorher: str) -> str:
    return hashlib.sha256(b"\x02" + bytes.fromhex(merkle) + bytes.fromhex(vorher)).hexdigest()


def pfad(blaetter: Sequence[str], ziel: str) -> list[tuple[str, str]] | None:
    """Inklusionspfad eines Blattes: Liste aus (Seite des Geschwisters, Hash).

    Der Pfad ist logarithmisch - er belegt die Zugehoerigkeit, ohne dass der
    Pruefende das ganze Board haben muss.
    """
    ebene = sorted(blaetter)
    if ziel not in ebene:
        return None
    i = ebene.index(ziel)
    schritte: list[tuple[str, str]] = []
    while len(ebene) > 1:
        naechste = [knoten(ebene[j], ebene[j + 1]) for j in range(0, len(ebene) - 1, 2)]
        if len(ebene) % 2:
            naechste.append(ebene[-1])
            if i == len(ebene) - 1:
                i = len(naechste) - 1  # durchgereicht: kein Geschwister
                ebene = naechste
                continue
        schritte.append(("L" if i % 2 else "R", ebene[i ^ 1]))
        i //= 2
        ebene = naechste
    return schritte


def pfad_prueft(blatt_hash: str, schritte: Sequence[tuple[str, str]], root: str) -> bool:
    h = blatt_hash
    for seite, geschwister in schritte:
        h = knoten(geschwister, h) if seite == "L" else knoten(h, geschwister)
    return h == root


# ---------------------------------------------------------------------------
# Quellen
# ---------------------------------------------------------------------------


def hole(quelle: str) -> dict[str, Any]:
    """JSON aus einer URL oder einer Datei."""
    if quelle.startswith(("http://", "https://")):
        with urllib.request.urlopen(quelle, timeout=TIMEOUT_S) as antwort:
            roh = antwort.read().decode()
    else:
        with open(quelle, encoding="utf-8") as datei:
            roh = datei.read()
    daten = json.loads(roh)
    if not isinstance(daten, dict):
        raise ValueError(f"{quelle}: kein JSON-Objekt")
    return daten


def status_url(board_quelle: str) -> str | None:
    """Die Statusroute derselben Instanz - dort steht das veroeffentlichte Ergebnis."""
    if "/api/board/" in board_quelle:
        return board_quelle.replace("/api/board/", "/api/status/", 1)
    return None


# ---------------------------------------------------------------------------
# Pruefung
# ---------------------------------------------------------------------------


class Auditor:
    def __init__(self, export: dict[str, Any]) -> None:
        self.export = export
        self.befunde: list[str] = []
        self.batches: list[dict[str, Any]] = list(export.get("batches") or [])
        self.blaetter: dict[int, list[str]] = {}
        self.stimmen: list[tuple[str, tuple[str, ...]]] = []
        self.n_token = 0
        self.counts: dict[str, int] = {}
        self.pubkey_pem: str | None = None
        self.kette_ok = False
        self.signaturen_ok = False

    def befund(self, text: str) -> None:
        self.befunde.append(text)

    # -- 1. Struktur ------------------------------------------------------
    def pruefe_struktur(self) -> None:
        vorher = GENESIS
        for n, batch in enumerate(self.batches):
            eintraege = [str(p) for p in batch.get("entries") or []]
            if int(batch.get("batch", -1)) != n:
                self.befund(f"Batch an Position {n} nennt sich {batch.get('batch')!r}")
                return
            if not eintraege:
                self.befund(f"Batch {n} ist leer - ein leerer Batch ist kein Batch")
                return
            blaetter = [blatt(p) for p in eintraege]
            self.blaetter[n] = blaetter
            if len(set(blaetter)) != len(blaetter):
                self.befund(f"Batch {n} enthaelt denselben Eintrag zweimal")
            gerechnet = wurzel(blaetter)
            if gerechnet != batch.get("merkle_root"):
                self.befund(f"Batch {n}: Merkle-Root passt nicht zu den Eintraegen")
                return
            if kettenglied(gerechnet, vorher) != batch.get("batch_root"):
                self.befund(f"Batch {n}: Kettenglied gebrochen - Vorgaenger ausgetauscht?")
                return
            vorher = str(batch["batch_root"])
        self.kette_ok = True

    # -- 2. Schluessel ----------------------------------------------------
    def token_schluessel(self, erwartet_pem: bytes | None):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        offen = [d for d in self._eintraege() if d.get("type") == "POLL_OPEN"]
        if len(offen) != 1:
            self.befund(f"{len(offen)} POLL_OPEN-Eintraege im Board - kein eindeutiger Schluessel")
            return None
        pem = offen[0].get("pubkey")
        if not isinstance(pem, str):
            self.befund("POLL_OPEN ohne Feld 'pubkey' - Schluessel nicht unter der Root")
            return None
        self.pubkey_pem = pem
        try:
            key = serialization.load_pem_public_key(pem.encode())
        except Exception as exc:  # noqa: BLE001 - jede Ursache ist derselbe Befund
            self.befund(f"Token-Schluessel im Board nicht lesbar: {exc}")
            return None
        if not isinstance(key, rsa.RSAPublicKey):
            self.befund("Token-Schluessel im Board ist kein RSA-Schluessel")
            return None
        if erwartet_pem is not None:
            erwartet = serialization.load_pem_public_key(erwartet_pem)
            if erwartet.public_numbers() != key.public_numbers():  # type: ignore[union-attr]
                self.befund("Board nennt einen anderen Schluessel als die unabhaengige Quelle")
                return None
        return key

    # -- 3.-6. Eintraege --------------------------------------------------
    def pruefe_eintraege(self, key) -> None:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        optionen = self.export.get("options")
        if isinstance(optionen, list):
            self.counts = {str(o): 0 for o in optionen}
        gesehen: set[str] = set()
        signaturen_ok = key is not None

        for daten in self._eintraege():
            typ = daten.get("type")
            if typ == "TOKEN_ISSUED":
                self.n_token += 1
                continue
            if typ != "VOTE":
                if typ not in ("POLL_OPEN", "POLL_CLOSED"):
                    self.befund(f"Unbekannter Eintragstyp {typ!r} - Board nicht deutbar")
                continue
            try:
                token = bytes.fromhex(str(daten["token"]))
                sig = bytes.fromhex(str(daten["sig"]))
                choices = tuple(str(c) for c in daten["choices"])
            except (KeyError, ValueError, TypeError):
                self.befund("Stimme mit fehlenden oder unlesbaren Feldern")
                continue
            if not choices:
                self.befund("Stimme ohne Auswahl")

            if token.hex() in gesehen:
                self.befund(f"Token {token.hex()[:16]}... steht zweimal im Board")
            gesehen.add(token.hex())

            if key is not None:
                try:
                    key.verify(
                        sig,
                        token,
                        padding.PSS(mgf=padding.MGF1(hashes.SHA384()), salt_length=0),
                        hashes.SHA384(),
                    )
                except (InvalidSignature, ValueError):
                    signaturen_ok = False
                    self.befund(f"Stimme {token.hex()[:16]}... ohne gueltige Token-Signatur")

            self.stimmen.append((token.hex(), choices))
            for c in choices:
                if isinstance(optionen, list) and c not in self.counts:
                    self.befund(f"Stimme fuer unbekannte Option {c!r}")
                self.counts[c] = self.counts.get(c, 0) + 1

        self.signaturen_ok = signaturen_ok
        if len(self.stimmen) > self.n_token:
            self.befund(
                f"Mehr Stimmen als ausgegebene Token: {len(self.stimmen)} zu {self.n_token} "
                f"(Ueberschuss {len(self.stimmen) - self.n_token}, RFC §9)"
            )

    def pruefe_ergebnis(self, status: dict[str, Any]) -> None:
        """Vergleicht die eigene Zaehlung mit dem, was die Instanz veroeffentlicht."""
        if status.get("participation") != len(self.stimmen):
            self.befund(
                f"Veroeffentlichte Teilnahme {status.get('participation')} != "
                f"{len(self.stimmen)} Stimmen im Board"
            )
        if status.get("n_eligible") != self.n_token:
            self.befund(
                f"Veroeffentlichte Token-Zahl {status.get('n_eligible')} != "
                f"{self.n_token} im Board"
            )
        result = status.get("result")
        if isinstance(result, dict):
            fremd = {str(k): int(v) for k, v in result.items()}
            eigen = {k: v for k, v in self.counts.items()}
            if fremd != eigen:
                self.befund(f"Veroeffentlichtes Ergebnis {fremd} != eigene Zaehlung {eigen}")

    def _eintraege(self):
        for batch in self.batches:
            for payload in batch.get("entries") or []:
                try:
                    daten = json.loads(str(payload))
                except json.JSONDecodeError:
                    self.befund("Eintrag ist kein JSON - zaehlt nirgends mit und bleibt ein Befund")
                    continue
                if isinstance(daten, dict):
                    yield daten
                else:
                    self.befund("Eintrag ist kein JSON-Objekt")

    @property
    def belastbar(self) -> bool:
        return self.kette_ok and self.signaturen_ok and not self.befunde


# ---------------------------------------------------------------------------
# Beleg (EIP-T-033 B): Inklusionsbeweis einer einzelnen Stimme
# ---------------------------------------------------------------------------


def pruefe_beleg(auditor: Auditor, beleg: dict[str, Any], belegkey_pem: bytes | None) -> list[str]:
    """Prueft einen Abgabebeleg gegen das Board. Gibt Meldungszeilen zurueck."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    zeilen: list[str] = []
    poll = str(beleg.get("poll") or auditor.export.get("poll"))
    leaf = str(beleg.get("leaf_hash") or beleg.get("leaf") or "")
    batch = int(beleg.get("batch", -1))

    if belegkey_pem is None:
        pem = auditor.export.get("beleg_public_key")
        zeilen.append(
            "Beleg-Schluessel aus dem Board-Export - der steht NICHT unter der Merkle-Root. "
            "Gegen einen unabhaengig bezogenen Schluessel pruefen (--belegkey)."
        )
    else:
        pem = belegkey_pem.decode()
    try:
        key = serialization.load_pem_public_key(str(pem).encode())
        assert isinstance(key, ed25519.Ed25519PublicKey)
        botschaft = canonical({"batch": batch, "leaf": leaf, "poll": poll, "typ": "BELEG"})
        key.verify(bytes.fromhex(str(beleg.get("beleg_sig", ""))), botschaft.encode())
        zeilen.append("Beleg-Signatur:   gueltig (Ed25519)")
    except (InvalidSignature, ValueError, AssertionError) as exc:
        zeilen.append(f"Beleg-Signatur:   UNGUELTIG ({exc or 'Signatur passt nicht'})")

    blaetter = auditor.blaetter.get(batch)
    if blaetter is None:
        zeilen.append(
            f"Inklusion:        Batch {batch} ist noch nicht veroeffentlicht - die Zusage "
            "steht aus (spaetestens bei Schliessung faellig)"
        )
        return zeilen
    schritte = pfad(blaetter, leaf)
    root = str(auditor.batches[batch].get("merkle_root"))
    if schritte is None:
        zeilen.append(
            f"Inklusion:        FEHLT - Blatt {leaf[:16]}... ist nicht in Batch {batch}. "
            "Der Beleg ist der Nachweis dafuer, nicht eine Behauptung."
        )
    elif pfad_prueft(leaf, schritte, root):
        zeilen.append(f"Inklusion:        belegt, Pfadlaenge {len(schritte)} in Batch {batch}")
    else:
        zeilen.append(f"Inklusion:        Pfad fuehrt nicht zur Root von Batch {batch}")
    return zeilen


# ---------------------------------------------------------------------------
# Bericht
# ---------------------------------------------------------------------------


def _abgleich(status: dict[str, Any] | None) -> str:
    if status is None:
        return "kein Statusabruf (--status)"
    if isinstance(status.get("result"), dict):
        return "Zahlen und Ergebnis gegen die Instanz geprueft"
    return "Zahlen geprueft; Ergebnis noch nicht veroeffentlicht (Umfrage laeuft)"


def bericht(auditor: Auditor, status: dict[str, Any] | None) -> list[str]:
    e = auditor.export
    n_eintraege = sum(len(b.get("entries") or []) for b in auditor.batches)
    zeilen = [
        f"Umfrage:          {e.get('poll', '?')}",
        f"Frage:            {e.get('question', '?')}",
        f"Status:           {'geschlossen' if e.get('closed') else 'offen'}",
        f"Board:            {len(auditor.batches)} Batches mit {n_eintraege} Eintraegen",
        "",
        f"Struktur:         {'nachgerechnet' if auditor.kette_ok else 'FEHLERHAFT'}",
        f"Token-Signaturen: {'alle gueltig' if auditor.signaturen_ok else 'NICHT alle gueltig'}",
        f"Tokens:           {len(auditor.stimmen)} Stimmen, {auditor.n_token} ausgegeben",
        f"Ergebnisabgleich: {_abgleich(status)}",
        "",
        "Auszaehlung:" if auditor.belastbar else "Auszaehlung (NICHT belastbar):",
    ]
    for opt, n in sorted(auditor.counts.items(), key=lambda kv: (-kv[1], kv[0])):
        zeilen.append(f"  {n:>5}  {opt}")
    if auditor.befunde:
        zeilen += ["", "Befunde:"] + [f"  - {b}" for b in auditor.befunde]
    zeilen += [
        "",
        "Ergebnis belastbar: ja" if auditor.belastbar else "Ergebnis belastbar: NEIN",
    ]
    return zeilen


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Rechnet ein veroeffentlichtes Board unabhaengig nach (EIP-T-071).",
        epilog="Importiert nichts aus dieser App - das ist der Zweck.",
    )
    p.add_argument("board", help="URL von /api/board/{poll} oder Pfad zu board.json")
    p.add_argument("--status", default=None, help="URL von /api/status/{poll} (sonst abgeleitet)")
    p.add_argument("--pubkey", default=None, help="Token-Schluessel (PEM) aus unabhaengiger Quelle")
    p.add_argument("--beleg", default=None, help="Abgabebeleg als JSON-Datei")
    p.add_argument("--belegkey", default=None, help="Beleg-Schluessel (PEM) aus unabh. Quelle")
    p.add_argument("--token", default=None, help="eigenes Stimm-Token (hex) im Board suchen")
    args = p.parse_args(argv)

    export = hole(args.board)
    auditor = Auditor(export)
    auditor.pruefe_struktur()
    erwartet = open(args.pubkey, "rb").read() if args.pubkey else None
    auditor.pruefe_eintraege(auditor.token_schluessel(erwartet))

    quelle = args.status or status_url(args.board)
    status: dict[str, Any] | None = None
    if quelle:
        try:
            status = hole(quelle)
            auditor.pruefe_ergebnis(status)
        except Exception as exc:  # noqa: BLE001 - Netz, Datei, JSON: derselbe Hinweis
            print(f"Hinweis: Status nicht abrufbar ({exc}) - kein Ergebnisabgleich.\n")

    print("\n".join(bericht(auditor, status)))

    if args.beleg:
        belegkey = open(args.belegkey, "rb").read() if args.belegkey else None
        print()
        print("\n".join(pruefe_beleg(auditor, hole(args.beleg), belegkey)))

    if args.token:
        t = args.token.strip().lower()
        treffer = [c for tok, c in auditor.stimmen if tok == t]
        print()
        print(
            f"Token {t[:16]}...: {list(treffer[0])}"
            if treffer
            else f"Token {t[:16]}...: nicht im veroeffentlichten Board"
        )

    return 0 if auditor.belastbar else 1


if __name__ == "__main__":
    sys.exit(main())
