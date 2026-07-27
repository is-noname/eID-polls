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
from poll_service import PollService, Rejected

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


def _signaturschluessel(service: PollService) -> rsa.RSAPrivateKey:
    """Den Token-Schluessel aus der Store-Config holen.

    Kein Zugriff auf `PollService._d`: Die Demo nimmt denselben Weg wie ein
    Betreiber, der die Datenbank hat - das *ist* die Aussage von §9.
    """
    pem = service.store.get_config("token_key_pem")
    if not pem:
        raise Rejected("Kein Token-Signaturschluessel in der Datenbank.")
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
    d = _signaturschluessel(service).private_numbers().d
    token = secrets.token_bytes(32)
    blinded, inv = blind.blind(token, service.n, service.e)
    sig = blind.finalize(blind.blind_sign(blinded, service.n, d), inv, service.n)
    service.cast_vote(poll_id, token, sig, [choice])
    log.error("demo", "Betreiber-Stimme ohne Berechtigung eingeschleust (Demo).", poll=poll_id)


def tamper_board(service: PollService, poll_id: str, index: int, new_choice: str) -> None:
    """Schreibt eine Board-Stimme um und laesst die Hashes stehen.

    Zeigt Fund 2 aus dem Prototyp: die Kette entlarvt genau diesen faulen
    Angreifer. Ein Betreiber mit Schreibzugriff wuerde die Hashes dahinter
    neu rechnen - dagegen hilft nur ein extern verankerter Merkle-Root (§12).
    """
    entry = next((e for e in service.board(poll_id) if e.index == index), None)
    if entry is None:
        raise Rejected(f"Kein Board-Eintrag #{index}.")
    gestimmt = parse(entry)
    if not isinstance(gestimmt, Vote):
        raise Rejected(f"Eintrag #{index} ist keine Stimme.")
    umgeschrieben = board_eintrag.vote(gestimmt.poll, gestimmt.token, gestimmt.sig, [new_choice])

    with _direktzugriff(service.store.path) as conn:
        conn.execute(
            "UPDATE board SET payload = ? WHERE poll_id = ? AND idx = ?",
            (canonical(umgeschrieben), poll_id, index),
        )
    log.error("demo", f"Board-Eintrag #{index} manipuliert (Demo).", poll=poll_id)
    service.check_consistency(poll_id)


def reset_eligibility(service: PollService, poll_id: str, pseudonym: str) -> bool:
    """Testbetrieb: Eligibility-Eintrag loeschen, damit derselbe Testcode erneut
    ein Token abholen kann. Im echten eID-Verfahren gibt es diesen Weg nicht -
    dort ist die Sperre nach dem ersten Token endgueltig gewollt (§6).
    """
    service.poll(poll_id)
    key = service.voter_key(pseudonym, poll_id)
    with _direktzugriff(service.store.path) as conn:
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
        int(payload.get("index", -1)),
        str(payload.get("choice", "")),
    )
    return JSONResponse({"ok": True})


@router.post("/api/admin/demo/stuff/{poll_id}")
async def api_admin_stuff(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    web.require_admin(request)
    stuff_ballot(web.deps(request).service, poll_id, str(payload.get("choice", "")))
    return JSONResponse({"ok": True})
