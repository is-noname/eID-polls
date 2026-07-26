"""HTTP-Schicht: Seiten und JSON-API.

Wichtig fuer §6/§10: Der unverblindete Stimm-Token entsteht im Browser und
verlaesst ihn nur zweimal - verblindet in Phase A und zusammen mit der Stimme in
Phase B. Der Server sieht ihn dazwischen nie. Das Blinding liegt deshalb in
static/blind.js und nicht hier; serverseitiges "Blinding" waere kein
Wahlgeheimnis gegen den Betreiber, sondern nur eine Behauptung.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import markdown
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
from auth import AuthError, CodeAuthenticator
from debug import log
from poll_service import PollService, Rejected

BASE_DIR = Path(__file__).parent
DB_PATH = Path(os.environ.get("EIDPOLL_DB", BASE_DIR / "data" / "eidpoll.sqlite3"))
ADMIN_TOKEN = config.ADMIN_TOKEN

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
service = PollService(DB_PATH)
authenticator = CodeAuthenticator()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

class RevalidatingStatics(StaticFiles):
    """Statische Dateien immer revalidieren lassen.

    Ohne Cache-Control cacht der Browser CSS und JS heuristisch, ohne
    nachzufragen. Nach einer Aenderung sieht man dann neues Markup mit altem
    Stylesheet und muss hart neu laden. "no-cache" heisst nicht "nicht cachen",
    sondern "vor Benutzung nachfragen" - bei unveraendertem ETag antwortet der
    Server mit 304, es geht also kein Traffic verloren.
    """

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    for line in config.startup_banner():
        log.info("system", line)
        print(f"[eidpoll] {line}", flush=True)
    # Ohne persistente Platte (Gratis-Hosting) ist die Datenbank nach jedem
    # Neustart leer. Eine leere Startseite waere fuer einen Besucher nicht von
    # einer kaputten Instanz zu unterscheiden.
    if config.SEED_DEMO and not service.polls():
        try:
            service.create_poll(config.SEED_POLL_ID, config.SEED_QUESTION, config.SEED_OPTIONS)
        except Rejected as exc:
            log.reject("system", f"Demo-Umfrage nicht angelegt: {exc}")
    yield


app = FastAPI(title="eID-Umfrage", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", RevalidatingStatics(directory=str(BASE_DIR / "static")), name="static")

SESSION_COOKIE = "eidpoll_session"
ADMIN_COOKIE = "eidpoll_admin"


# ---------------------------------------------------------------------------
# Signierte Cookies (Pseudonym verlaesst den Server nur signiert)
# ---------------------------------------------------------------------------


def _sign(value: str) -> str:
    mac = hmac.new(service.voter_key("cookie", "session").encode(), value.encode(), hashlib.sha256)
    return f"{value}.{mac.hexdigest()[:32]}"


def _unsign(signed: str | None) -> str | None:
    if not signed or "." not in signed:
        return None
    value, _, mac = signed.rpartition(".")
    return value if hmac.compare_digest(_sign(value), f"{value}.{mac}") else None


def current_pseudonym(request: Request) -> str | None:
    return _unsign(request.cookies.get(SESSION_COOKIE))


def is_admin(request: Request) -> bool:
    return _unsign(request.cookies.get(ADMIN_COOKIE)) == "admin"


LOCAL_HOSTS = {"127.0.0.1", "::1"}


def is_local(request: Request) -> bool:
    """Nur der Rechner, auf dem der Server laeuft - nicht jedes LAN-Geraet (EIP-T-009).

    Oeffentlich ist niemand "lokal": Hinter einem Reverse Proxy ist die
    Absender-IP nicht mehr die des Besuchers, und die daran haengenden Rechte
    (Beenden, Admin-Link) waeren dann an eine Angabe geknuepft, die der Proxy
    setzt statt der Bediener.
    """
    if config.PUBLIC:
        return False
    return request.client is not None and request.client.host in LOCAL_HOSTS


def _require_admin(request: Request) -> None:
    if not is_admin(request):
        raise Rejected(
            "Dieser Bereich ist dem Betreiber der Umfrage vorbehalten. "
            "Anmeldung mit dem Admin-Token unter /admin.",
            status_code=403,
        )


# ---------------------------------------------------------------------------
# Fehlerbehandlung - jede Abweisung und jeder Fehler geht ins Debug-Modul
# ---------------------------------------------------------------------------


@app.exception_handler(Rejected)
async def _rejected_handler(request: Request, exc: Rejected) -> HTMLResponse | JSONResponse:
    log.reject("abgewiesen", str(exc), pfad=request.url.path)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": str(exc)}, status_code=400)
    return page(request, "error.html", status_code=exc.status_code, message=str(exc))


@app.exception_handler(AuthError)
async def _auth_handler(request: Request, exc: AuthError) -> JSONResponse:
    log.reject("auth", str(exc), pfad=request.url.path)
    return JSONResponse({"error": str(exc)}, status_code=400)


@app.exception_handler(Exception)
async def _error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Der Wortlaut einer Ausnahme traegt Pfade, SQL und Feldnamen nach aussen.
    # Lokal ist das die schnellste Diagnose, oeffentlich eine Auskunft ueber den
    # Server an Unbeteiligte - der Text bleibt dann im Debug-Modul.
    log.exception(f"unerwartet {request.url.path}", exc)
    detail = "Interner Fehler." if config.PUBLIC else f"Interner Fehler: {exc}"
    return JSONResponse({"error": detail}, status_code=500)


def page(request: Request, template: str, status_code: int = 200, **context: Any) -> HTMLResponse:
    context.setdefault("pseudonym", current_pseudonym(request))
    context.setdefault("admin", is_admin(request))
    context.setdefault("authenticator", authenticator)
    context.setdefault("debug_counts", log.counts())
    context.setdefault("is_local", is_local(request))
    context.setdefault("public", config.PUBLIC)
    context.setdefault("demo_codes", authenticator.sample_codes())
    return templates.TemplateResponse(request, template, context, status_code=status_code)


# ---------------------------------------------------------------------------
# Seiten
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    polls = service.polls()
    rows = [
        {
            "poll": p,
            "participation": service.participation(p.poll_id),
            "accounting": service.accounting(p.poll_id),
        }
        for p in polls
    ]
    return page(request, "index.html", rows=rows)


@app.get("/poll/{poll_id}", response_class=HTMLResponse)
async def poll_page(request: Request, poll_id: str) -> HTMLResponse:
    poll = service.poll(poll_id)
    return page(
        request,
        "poll.html",
        poll=poll,
        participation=service.participation(poll_id),
        n=hex(service.n)[2:],
        e=hex(service.e)[2:],
    )


@app.get("/board/{poll_id}", response_class=HTMLResponse)
async def board_page(request: Request, poll_id: str) -> HTMLResponse:
    poll = service.poll(poll_id)
    status = service.chain_status(poll_id)
    accounting = service.accounting(poll_id)
    if not status.sound or not accounting.ok:
        service.check_consistency(poll_id)
    try:
        result: dict[str, int] | None = service.tally(poll_id)
        result_error = None
    except Rejected as exc:
        result, result_error = None, str(exc)
    return page(
        request,
        "board.html",
        poll=poll,
        entries=service.board(poll_id),
        status=status,
        accounting=accounting,
        result=result,
        result_error=result_error,
        public_key=service.public_key_pem,
    )


@app.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request, poll: str = "", token: str = "") -> HTMLResponse:
    found: list[str] | None = None
    searched = bool(poll and token)
    if searched:
        found = service.lookup(poll, token)
        if found is None:
            log.reject("verifikation", "Token nicht im Board gefunden.", poll=poll)
    return page(
        request,
        "verify.html",
        polls=service.polls(),
        sel_poll=poll,
        token=token,
        found=found,
        searched=searched,
    )


@app.get("/debug", response_class=HTMLResponse)
async def debug_page(request: Request, level: str = "all") -> HTMLResponse:
    # Das Debug-Log stellt Phase-A- und Phase-B-Ereignisse mit Zeitstempel
    # nebeneinander. Wer beides sieht, kann ueber die Zeit korrelieren - genau
    # die Zuordnung, die das Verfahren verhindern soll (EIP-T-018).
    _require_admin(request)
    findings = service.check_all()
    return page(
        request,
        "debug.html",
        events=log.events(level),
        counts=log.counts(),
        level=level,
        findings={k: v for k, v in findings.items() if v},
        polls=service.polls(),
    )


MANIFEST_PATH = BASE_DIR / "MANIFEST.md"
_manifest_cache: tuple[float, str] | None = None


def manifest_html() -> str:
    """Rendert MANIFEST.md, gecacht bis die Datei sich aendert.

    Die Prosa steht bewusst nicht im Template: Sie lief dort schon einmal
    gegenueber dem Manifest auseinander und behauptete Zusagen, die das Manifest
    zurueckgenommen hatte (EIP-T-044). Nach KODEX.md bindet das Manifest jede
    Oberflaeche - eine zweite, handgepflegte Fassung ist deshalb kein
    Duplikat, sondern eine Fehlerquelle mit Aussenwirkung.

    MANIFEST.md hier ist eine abgeleitete Kopie; erzeugt wird sie von
    scripts/sync_manifest.py im Elternordner, der nicht Teil dieses Repos ist.
    """
    global _manifest_cache
    try:
        stamp = MANIFEST_PATH.stat().st_mtime
    except OSError as exc:
        log.error("manifest", f"MANIFEST.md nicht lesbar: {exc}")
        return "<p>Das Manifest ist gerade nicht abrufbar.</p>"

    if _manifest_cache is None or _manifest_cache[0] != stamp:
        text = MANIFEST_PATH.read_text(encoding="utf-8")
        # Der Sync-Hinweis am Dateikopf richtet sich an Bearbeiter, nicht an Besucher.
        if text.lstrip().startswith("<!--"):
            text = text.split("-->", 1)[1]
        html = markdown.markdown(text)
        # Erster Absatz nach der Ueberschrift ist die Lead-Zeile der Seite.
        html = html.replace("</h1>\n<p>", '</h1>\n<p class="lead">', 1)
        _manifest_cache = (stamp, html)
    return _manifest_cache[1]


@app.get("/manifest", response_class=HTMLResponse)
async def manifest_page(request: Request) -> HTMLResponse:
    return page(request, "manifest.html", manifest=manifest_html())


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    return page(request, "admin.html", polls=service.polls())


# ---------------------------------------------------------------------------
# API - Authentifizierung
# ---------------------------------------------------------------------------


@app.post("/api/auth")
async def api_auth(payload: dict) -> JSONResponse:
    pseudonym = authenticator.authenticate(str(payload.get("credential", "")))
    log.info("auth", f"Authentifiziert ueber: {authenticator.name}")
    response = JSONResponse({"ok": True, "real_identity": authenticator.is_real_identity})
    response.set_cookie(
        SESSION_COOKIE, _sign(pseudonym), httponly=True, samesite="lax", secure=config.PUBLIC
    )
    return response


@app.post("/api/auth/abort")
async def api_auth_abort() -> JSONResponse:
    log.reject("auth", "Dialog 'Ausweis auslesen' abgebrochen.")
    return JSONResponse({"ok": True})


@app.post("/api/logout")
async def api_logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


# ---------------------------------------------------------------------------
# API - Phase A und Phase B
# ---------------------------------------------------------------------------


@app.post("/api/token/{poll_id}")
async def api_token(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    pseudonym = current_pseudonym(request)
    if pseudonym is None:
        raise Rejected("Nicht authentifiziert - Phase A verlangt eine Identitaet.")
    try:
        blinded = bytes.fromhex(str(payload.get("blinded", "")))
    except ValueError as exc:
        raise Rejected("Verblindete Anfrage ist kein Hex.") from exc
    blind_sig = service.issue_blind_signature(poll_id, pseudonym, blinded)
    return JSONResponse({"blind_sig": blind_sig.hex()})


@app.post("/api/vote/{poll_id}")
async def api_vote(poll_id: str, payload: dict) -> JSONResponse:
    try:
        token = bytes.fromhex(str(payload.get("token", "")))
        sig = bytes.fromhex(str(payload.get("sig", "")))
    except ValueError as exc:
        raise Rejected("Token oder Signatur ist kein Hex.") from exc
    choices = [str(c) for c in payload.get("choices", [])]
    entry = service.cast_vote(poll_id, token, sig, choices)
    return JSONResponse(
        {
            "ok": True,
            "board_index": entry.index,
            "entry_hash": entry.entry_hash,
            "token": token.hex(),
            "participation": service.participation(poll_id),
        }
    )


@app.get("/api/status/{poll_id}")
async def api_status(poll_id: str) -> JSONResponse:
    poll = service.poll(poll_id)
    accounting = service.accounting(poll_id)
    return JSONResponse(
        {
            "poll": poll.poll_id,
            "closed": poll.closed,
            "participation": service.participation(poll_id),
            "n_eligible": accounting.n_eligible,
            "accounting_ok": accounting.ok,
        }
    )


# ---------------------------------------------------------------------------
# API - Admin
# ---------------------------------------------------------------------------


@app.post("/api/admin/login")
async def api_admin_login(payload: dict) -> JSONResponse:
    if not hmac.compare_digest(str(payload.get("token", "")), ADMIN_TOKEN):
        raise Rejected("Admin-Token falsch.")
    response = JSONResponse({"ok": True})
    # secure=True nur oeffentlich: lokal laeuft die App ueber http, dort wuerde
    # das Flag das Cookie verwerfen und die Anmeldung unmoeglich machen.
    response.set_cookie(
        ADMIN_COOKIE, _sign("admin"), httponly=True, samesite="lax", secure=config.PUBLIC
    )
    return response


@app.post("/api/admin/create")
async def api_admin_create(request: Request, payload: dict) -> JSONResponse:
    _require_admin(request)
    options = [str(o) for o in payload.get("options", [])]
    poll = service.create_poll(str(payload.get("poll_id", "")), str(payload.get("question", "")), options)
    return JSONResponse({"ok": True, "poll_id": poll.poll_id})


@app.post("/api/admin/close/{poll_id}")
async def api_admin_close(request: Request, poll_id: str) -> JSONResponse:
    _require_admin(request)
    service.close_poll(poll_id)
    return JSONResponse({"ok": True})


@app.post("/api/admin/reset/{poll_id}")
async def api_admin_reset(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    """Testbetrieb: eigene Sperre nach Token-Abholung aufheben (EIP-Reset).

    Nimmt denselben Zugangscode wie /api/auth, um das Pseudonym zu bilden -
    im echten eID-Verfahren gaebe es diesen Weg nicht (§6, dauerhafte Sperre).
    """
    _require_admin(request)
    pseudonym = authenticator.authenticate(str(payload.get("credential", "")))
    removed = service.reset_eligibility(poll_id, pseudonym)
    return JSONResponse({"ok": True, "removed": removed})


@app.post("/api/admin/demo/tamper/{poll_id}")
async def api_admin_tamper(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    _require_admin(request)
    service.demo_tamper_board(poll_id, int(payload.get("index", -1)), str(payload.get("choice", "")))
    return JSONResponse({"ok": True})


@app.post("/api/admin/demo/stuff/{poll_id}")
async def api_admin_stuff(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    _require_admin(request)
    service.demo_stuff_ballot(poll_id, str(payload.get("choice", "")))
    return JSONResponse({"ok": True})


@app.post("/api/debug/clear")
async def api_debug_clear(request: Request) -> JSONResponse:
    # Das Log ist die Stelle, an der Manipulation auffaellt - Leeren darf nicht
    # jedes Netzgeraet koennen (EIP-T-018).
    _require_admin(request)
    log.clear()
    return JSONResponse({"ok": True})


@app.post("/api/shutdown")
async def api_shutdown(request: Request) -> JSONResponse:
    """Beenden-Knopf - damit kein Terminal haengen bleibt.

    Nur vom Rechner aus, auf dem der Server laeuft: Im LAN (EIP-T-009) darf kein
    Teilnehmergeraet die App fuer alle anderen beenden koennen. Oeffentlich gibt
    es den Weg gar nicht - dort beendet die Plattform den Prozess, und eine
    erreichbare Abschaltroute waere nur eine Angriffsflaeche.
    """
    if config.PUBLIC:
        raise Rejected("Diese Instanz wird von der Plattform verwaltet.", status_code=404)
    if not is_local(request):
        raise Rejected("Beenden ist nur auf dem Rechner moeglich, auf dem die App laeuft.")
    log.info("system", "Server wird beendet (Beenden-Knopf).")
    os.kill(os.getpid(), 15)
    return JSONResponse({"ok": True})
