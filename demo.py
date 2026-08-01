"""Angriffsdemos (§9) - ausserhalb des Kerns.

KODEX §9 braucht diese Vorfuehrungen: Eine Pruefung, die nie ausschlaegt, ist
Dekoration. Die Demos bleiben also - nur nicht mehr im Kern. Bis EIP-T-050
boten `PollService` und `Store` genau die Operationen an, gegen die das
Verfahren argumentiert: eine Methode, die einen Board-Eintrag umschreibt, stand
direkt neben der, die ihn anhaengt.

Dieses Modul benutzt Kern und Store deshalb **von aussen**, mit den Mitteln, die
ein Betreiber ohnehin hat:

  - Ballot-Stuffing laeuft durch das oeffentliche `cast_vote`. Der
    Signaturschluessel kommt aus der Store-Config - der Betreiber haelt ihn
    allein (DEPLOY.md, "Was fehlt"), und genau das ist der Punkt der Demo.
  - Board-Manipulation und Test-Reset schreiben mit einer eigenen Verbindung in
    dieselbe Datenbank. Auch das ist keine Bequemlichkeit, sondern das
    Angreifermodell: Wer die Platte hat, braucht keine API.

Damit gilt wieder: Es gibt keinen Weg *durch die Anwendung*, der das Board
umschreibt oder eine Berechtigung loescht.

Verdrahtet wird das Modul nur, wenn `Settings.demos` gesetzt ist (`create_app`).
Oeffentlich ist der Schalter aus, es sei denn, jemand setzt `EIDPOLL_DEMOS=1` -
die oeffentliche Vorfuehrinstanz tut das (DEPLOY.md).
"""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import blind
import board_eintrag
import web
from board_eintrag import Vote, canonical, parse
from debug import log
from poll_service import POLL_KEY, PollService, Rejected

router = APIRouter()


@contextmanager
def _direktzugriff(path: Path) -> Iterator[sqlite3.Connection]:
    """Eigene Verbindung zur Datenbank - der Weg am Kern vorbei.

    Bewusst nicht die Verbindung des Stores: Dieses Modul soll keinen Zugriff
    auf dessen Innenleben brauchen, und der Store soll keine Schreiboperation
    anbieten, die es hier braucht. WAL und busy_timeout (store.py) machen die
    zweite Verbindung unproblematisch.
    """
    conn = sqlite3.connect(path, timeout=30)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _signaturschluessel(service: PollService, poll_id: str) -> rsa.RSAPrivateKey:
    """Den Token-Schluessel dieser Umfrage aus der Store-Config holen.

    Kein Zugriff auf einen privaten Merker des Service: Die Demo nimmt denselben
    Weg wie ein Betreiber, der die Datenbank hat - das *ist* die Aussage von §9.

    Seit EIP-T-069 gibt es den Schluessel nur je Umfrage und nur, solange sie
    laeuft. Genau das ist die Grenze, die die Demo vorfuehrt: Nach dem
    Schliessen findet auch der Betreiber hier nichts mehr.
    """
    pem = service.berechtigung.get_config(POLL_KEY + poll_id)
    if not pem:
        raise Rejected(
            f"Kein Signaturschluessel fuer '{poll_id}' in der Datenbank - die Umfrage ist "
            "geschlossen und der Schluessel vernichtet (EIP-T-069). Auch der Betreiber kann "
            "hier keine Token mehr herstellen."
        )
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    assert isinstance(key, rsa.RSAPrivateKey)
    return key


# ---------------------------------------------------------------------------
# Die Eingriffe
# ---------------------------------------------------------------------------


def stuff_ballot(service: PollService, poll_id: str, choice: str) -> None:
    """Betreiber signiert sich selbst ein Token - ohne Eligibility-Eintrag.

    Laeuft absichtlich durch denselben cast_vote-Pfad: das Token ist
    kryptografisch ununterscheidbar von einem echten. Nur die
    Ledger-Abrechnung entlarvt es (§9).
    """
    key = _signaturschluessel(service, poll_id)
    n = key.public_key().public_numbers().n
    token = secrets.token_bytes(32)
    e = key.public_key().public_numbers().e
    blinded, inv = blind.blind(token, n, e)
    sig = blind.finalize(blind.blind_sign(blinded, n, key.private_numbers().d, e), inv, n)
    service.cast_vote(poll_id, token, sig, [choice])
    log.error("demo", "Betreiber-Stimme ohne Berechtigung eingeschleust (Demo).", poll=poll_id)


def tamper_board(service: PollService, poll_id: str, leaf_prefix: str, new_choice: str) -> None:
    """Schreibt eine veroeffentlichte Board-Stimme um und laesst die Roots stehen.

    Zeigt Fund 2 aus dem Prototyp: Merkle-Root und Batch-Kette entlarven genau
    diesen faulen Angreifer. Ein Betreiber mit Schreibzugriff wuerde Roots und
    Kette dahinter neu rechnen - dagegen hilft nur ein extern verankerter
    Merkle-Root (§12, EIP-T-006).

    Adressiert wird der Eintrag ueber seinen Blatt-Hash (oder ein eindeutiges
    Praefix davon) - Eintraege haben keine Nummern mehr (ADR E1).
    """
    leaf_prefix = leaf_prefix.strip().lower()
    if not leaf_prefix:
        raise Rejected("Blatt-Hash (oder Praefix) angeben.")
    treffer = [e for e in service.board(poll_id) if e.leaf_hash.startswith(leaf_prefix)]
    if not treffer:
        raise Rejected(f"Kein veroeffentlichter Board-Eintrag mit Blatt {leaf_prefix}...")
    if len(treffer) > 1:
        raise Rejected(f"Blatt-Praefix {leaf_prefix} ist nicht eindeutig.")
    entry = treffer[0]
    gestimmt = parse(entry)
    if not isinstance(gestimmt, Vote):
        raise Rejected(f"Eintrag {entry.leaf_hash[:16]}... ist keine Stimme.")
    umgeschrieben = board_eintrag.vote(gestimmt.poll, gestimmt.token, gestimmt.sig, [new_choice])

    with _direktzugriff(service.board_store.path) as conn:
        conn.execute(
            "UPDATE board SET payload = ? WHERE poll_id = ? AND leaf_hash = ?",
            (canonical(umgeschrieben), poll_id, entry.leaf_hash),
        )
    log.error(
        "demo", f"Board-Eintrag {entry.leaf_hash[:16]}... manipuliert (Demo).", poll=poll_id
    )
    service.check_consistency(poll_id, service.pruefbericht(poll_id))


def reset_eligibility(service: PollService, poll_id: str, pseudonym: str) -> bool:
    """Testbetrieb: Eligibility-Eintrag loeschen, damit derselbe Testcode erneut
    ein Token abholen kann. Im echten eID-Verfahren gibt es diesen Weg nicht -
    dort ist die Sperre nach dem ersten Token endgueltig gewollt (§6).
    """
    if service.poll(poll_id).closed:
        # Ohne diese Abweisung liefe der Reset in die Schluessel-Meldung aus
        # _poll_secret und wuerde wie ein Defekt aussehen. Er ist keiner: Nach
        # dem Schliessen ist der Umfrage-Schluessel vernichtet (EIP-T-033, D),
        # und damit ist gerade nicht mehr feststellbar, *wessen* Eintrag zu
        # loeschen waere. Das ist der Zweck der Vernichtung, nicht ihr Fehler.
        raise Rejected(
            "Die Umfrage ist geschlossen - ein Testzugang laesst sich nicht mehr "
            "zuruecksetzen. Mit dem Umfrage-Schluessel ist die Zuordnung von Ausweis zu "
            "Eligibility-Eintrag vernichtet."
        )
    key = service.voter_key(pseudonym, poll_id)
    with _direktzugriff(service.berechtigung.path) as conn:
        cur = conn.execute(
            "DELETE FROM eligibility WHERE poll_id = ? AND voter_key = ?", (poll_id, key)
        )
        removed = cur.rowcount > 0
    if removed:
        log.info("admin", f"Testzugang fuer '{poll_id}' zurueckgesetzt.", poll=poll_id)
    return removed


# ---------------------------------------------------------------------------
# Routen - nur eingehaengt, wenn der Schalter an ist
# ---------------------------------------------------------------------------


@router.post("/api/admin/reset/{poll_id}")
async def api_admin_reset(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    """Testbetrieb: eigene Sperre nach Token-Abholung aufheben (EIP-Reset).

    Nimmt denselben Zugangscode wie /api/auth, um das Pseudonym zu bilden -
    im echten eID-Verfahren gaebe es diesen Weg nicht (§6, dauerhafte Sperre).
    """
    web.require_admin(request)
    d = web.deps(request)
    pseudonym = d.authenticator.authenticate(str(payload.get("credential", "")))
    return JSONResponse({"ok": True, "removed": reset_eligibility(d.service, poll_id, pseudonym)})


@router.post("/api/admin/demo/tamper/{poll_id}")
async def api_admin_tamper(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    web.require_admin(request)
    tamper_board(
        web.deps(request).service,
        poll_id,
        str(payload.get("leaf", "")),
        str(payload.get("choice", "")),
    )
    return JSONResponse({"ok": True})


@router.post("/api/admin/demo/stuff/{poll_id}")
async def api_admin_stuff(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    web.require_admin(request)
    stuff_ballot(web.deps(request).service, poll_id, str(payload.get("choice", "")))
    return JSONResponse({"ok": True})
