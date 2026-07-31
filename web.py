"""HTTP-Schicht: Seiten und JSON-API.

Wichtig fuer §6/§10: Der unverblindete Stimm-Token entsteht im Browser und
verlaesst ihn nur zweimal - verblindet in Phase A und zusammen mit der Stimme in
Phase B. Der Server sieht ihn dazwischen nie. Das Blinding liegt deshalb in
static/blind.js und nicht hier; serverseitiges "Blinding" waere kein
Wahlgeheimnis gegen den Betreiber, sondern nur eine Behauptung.

Gebaut wird die App von ``create_app(store_path, authenticator, settings)``
(EIP-T-048). Der Authenticator ist der Seam aus auth.py, an dem der Stub gegen
den echten SAML-SP getauscht wird - das muss ein Komponieren sein und kein
Eingriff in diese Datei. Die Routen halten deshalb nichts fest, sondern lesen
ihre Abhaengigkeiten ueber ``deps(request)`` aus dem App-Zustand.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import markdown
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from auth import AuthError, Authenticator, CodeAuthenticator
from config import Settings
from debug import kategorie_fuer_pfad, log
from poll_service import PollService, Rejected

BASE_DIR = Path(__file__).parent

router = APIRouter()

SESSION_COOKIE = "eidpoll_session"
ADMIN_COOKIE = "eidpoll_admin"


@dataclass(frozen=True)
class Deps:
    """Was eine laufende Instanz ausmacht - je Instanz einmal, nicht je Modul."""

    service: PollService
    authenticator: Authenticator
    settings: Settings
    templates: Jinja2Templates


def deps(request: Request) -> Deps:
    return request.app.state.deps


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
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    d: Deps = app.state.deps
    for line in d.settings.startup_banner():
        log.info("system", line)
        print(f"[eidpoll] {line}", flush=True)
    # Ohne persistente Platte (Gratis-Hosting) ist die Datenbank nach jedem
    # Neustart leer. Eine leere Startseite waere fuer einen Besucher nicht von
    # einer kaputten Instanz zu unterscheiden.
    if d.settings.seed_demo and not d.service.polls():
        try:
            d.service.create_poll(
                d.settings.seed_poll_id, d.settings.seed_question, d.settings.seed_options
            )
        except Rejected as exc:
            log.reject("system", f"Demo-Umfrage nicht angelegt: {exc}")

    # Zeitdeckel der Batch-Veroeffentlichung (EIP-ADR-20260728-001, E3): Der
    # Deckel darf nicht davon abhaengen, dass zufaellig noch eine Anfrage
    # kommt - sonst wartet ein Beleg bei stillstehender Umfrage unbegrenzt.
    async def _batch_deckel() -> None:
        while True:
            await asyncio.sleep(60)
            d.service.publiziere_faellige()
            # Derselbe Takt fuer den Ablauf des Wiederhol-Puffers (EIP-T-070):
            # eine Lebensdauer, die nur beim naechsten Zugriff geprueft wird,
            # laesst die Zeilen bei stillstehender Umfrage unbegrenzt liegen.
            try:
                d.service.verwirf_abgelaufene_wiederholungen()
            except Exception as exc:
                log.exception("phase-a", exc)

    deckel_task = asyncio.create_task(_batch_deckel())
    try:
        yield
    finally:
        deckel_task.cancel()


def create_app(
    store_path: Path,
    authenticator: Authenticator | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Baut eine eigenstaendige Instanz.

    Alles, was die Instanz von einer anderen unterscheidet, steht in der
    Signatur: wo die Datenbank liegt, wie authentifiziert wird, in welchem
    Betriebsmodus sie laeuft. ``SamlEidAuthenticator`` einzusetzen heisst
    deshalb, ihn hier zu uebergeben - ohne Aenderung an dieser Datei.
    """
    store_path.parent.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="eID-Umfrage", docs_url=None, redoc_url=None, lifespan=lifespan)
    effective = settings if settings is not None else Settings.from_env()
    app.state.deps = Deps(
        service=PollService(
            store_path,
            batch_k=effective.batch_k,
            batch_deckel_s=int(effective.batch_deckel_h * 3600),
            retry_cache_s=int(effective.retry_cache_h * 3600),
        ),
        authenticator=authenticator if authenticator is not None else CodeAuthenticator(),
        settings=effective,
        templates=Jinja2Templates(directory=str(BASE_DIR / "templates")),
    )
    # Antwortzeit-Floor der Phasen-Routen (EIP-T-033, Baustein F): /api/token
    # und /api/vote antworten fruehestens nach antwort_floor_s. Ohne den Floor
    # unterscheidet die Dauer eine schnelle Abweisung von einer langsamen
    # RSA-Signatur - die Latenz wuerde zum Seitenkanal. Als Middleware statt in
    # den Routen, damit auch Abweisungen (Rejected laeuft ueber den
    # Exception-Handler) unter dem Floor liegen. Ehrlich dazu: ein Floor, keine
    # Konstante - dauert die Bearbeitung laenger als der Floor, ist die Dauer
    # wieder sichtbar. Netz-Jitter jenseits des Servers deckt er nie ab.
    floor_s = effective.antwort_floor_s

    @app.middleware("http")
    async def _antwort_floor(request: Request, call_next):  # type: ignore[no-untyped-def]
        pfad = request.url.path
        if floor_s <= 0 or not (pfad.startswith("/api/token/") or pfad.startswith("/api/vote/")):
            return await call_next(request)
        start = time.monotonic()
        response = await call_next(request)
        rest = floor_s - (time.monotonic() - start)
        if rest > 0:
            await asyncio.sleep(rest)
        return response

    app.mount("/static", RevalidatingStatics(directory=str(BASE_DIR / "static")), name="static")
    app.add_exception_handler(Rejected, _rejected_handler)
    app.add_exception_handler(AuthError, _auth_handler)
    app.add_exception_handler(Exception, _error_handler)
    app.include_router(router)
    # Angriffsdemos (§9) haengen an einem eigenen Schalter und sind kein Teil
    # der Anwendung: Sie schreiben an ihr vorbei in die Datenbank (demo.py).
    # Der Import steht hier und nicht oben, weil die Richtung so herum gilt -
    # demo.py kennt web.py, nicht umgekehrt.
    if app.state.deps.settings.demos:
        import demo

        app.include_router(demo.router)
    return app


# ---------------------------------------------------------------------------
# Signierte Cookies (Pseudonym verlaesst den Server nur signiert)
# ---------------------------------------------------------------------------


def _sign(request: Request, value: str) -> str:
    # Eigener Cookie-Schluessel, nicht die Pseudonym-Ableitung (EIP-T-048).
    key = deps(request).service.cookie_key
    mac = hmac.new(key, value.encode(), hashlib.sha256)
    return f"{value}.{mac.hexdigest()[:32]}"


def _unsign(request: Request, signed: str | None) -> str | None:
    if not signed or "." not in signed:
        return None
    value, _, mac = signed.rpartition(".")
    return value if hmac.compare_digest(_sign(request, value), f"{value}.{mac}") else None


def current_pseudonym(request: Request) -> str | None:
    return _unsign(request, request.cookies.get(SESSION_COOKIE))


def is_admin(request: Request) -> bool:
    return _unsign(request, request.cookies.get(ADMIN_COOKIE)) == "admin"


LOCAL_HOSTS = {"127.0.0.1", "::1"}


def is_local(request: Request) -> bool:
    """Nur der Rechner, auf dem der Server laeuft - nicht jedes LAN-Geraet (EIP-T-009).

    Oeffentlich ist niemand "lokal": Hinter einem Reverse Proxy ist die
    Absender-IP nicht mehr die des Besuchers, und die daran haengenden Rechte
    (Beenden, Admin-Link) waeren dann an eine Angabe geknuepft, die der Proxy
    setzt statt der Bediener.
    """
    if deps(request).settings.public:
        return False
    return request.client is not None and request.client.host in LOCAL_HOSTS


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise Rejected(
            "Dieser Bereich ist dem Betreiber der Umfrage vorbehalten. "
            "Anmeldung mit dem Admin-Token unter /admin.",
            status_code=403,
        )


# ---------------------------------------------------------------------------
# Fehlerbehandlung - jede Abweisung und jeder Fehler geht ins Debug-Modul
# ---------------------------------------------------------------------------


async def _rejected_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    # Abweisungen aus Phase A und B laufen unter ihrer Phasen-Kategorie und
    # werden dadurch gezaehlt statt gestromt (debug.TEILNAHME, EIP-T-041): Eine
    # abgewiesene Stimmabgabe um 16:00:41 neben einer Token-Ausgabe um 16:00:03
    # verkettet genauso wie zwei erfolgreiche Vorgaenge.
    log.reject(kategorie_fuer_pfad(request.url.path, "abgewiesen"), str(exc), pfad=request.url.path)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": str(exc)}, status_code=400)
    status = getattr(exc, "status_code", 400)
    return page(request, "error.html", status_code=status, message=str(exc))


async def _auth_handler(request: Request, exc: Exception) -> JSONResponse:
    log.reject("auth", str(exc), pfad=request.url.path)
    return JSONResponse({"error": str(exc)}, status_code=400)


async def _error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Der Wortlaut einer Ausnahme traegt Pfade, SQL und Feldnamen nach aussen.
    # Lokal ist das die schnellste Diagnose, oeffentlich eine Auskunft ueber den
    # Server an Unbeteiligte - der Text bleibt dann im Debug-Modul.
    log.exception(f"unerwartet {request.url.path}", exc)
    detail = "Interner Fehler." if deps(request).settings.public else f"Interner Fehler: {exc}"
    return JSONResponse({"error": detail}, status_code=500)


def page(request: Request, template: str, status_code: int = 200, **context: Any) -> HTMLResponse:
    d = deps(request)
    context.setdefault("pseudonym", current_pseudonym(request))
    context.setdefault("admin", is_admin(request))
    context.setdefault("authenticator", d.authenticator)
    context.setdefault("debug_counts", log.counts())
    context.setdefault("is_local", is_local(request))
    context.setdefault("public", d.settings.public)
    context.setdefault("demos", d.settings.demos)
    context.setdefault("demo_codes", d.authenticator.sample_codes())
    return d.templates.TemplateResponse(request, template, context, status_code=status_code)


# ---------------------------------------------------------------------------
# Seiten
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    service = deps(request).service
    # Ein Bericht je Umfrage: Beteiligung und Abrechnung kommen aus demselben
    # Durchlauf, nicht aus zwei (EIP-T-051).
    rows = [
        {
            "poll": p,
            "participation": bericht.accounting.n_votes,
            "accounting": bericht.accounting,
        }
        for p, bericht in ((p, service.laufender_bericht(p.poll_id)) for p in service.polls())
    ]
    return page(request, "index.html", rows=rows)


@router.get("/poll/{poll_id}", response_class=HTMLResponse)
async def poll_page(request: Request, poll_id: str) -> HTMLResponse:
    service = deps(request).service
    poll = service.poll(poll_id)
    # Die Blinding-Parameter gehoeren zu genau dieser Umfrage (EIP-T-069) - ein
    # Token, das der Browser gegen sie rechnet, ist anderswo wertlos.
    n, e = service.poll_params(poll_id)
    return page(
        request,
        "poll.html",
        poll=poll,
        participation=service.participation(poll_id),
        n=hex(n)[2:],
        e=hex(e)[2:],
    )


@router.get("/board/{poll_id}", response_class=HTMLResponse)
async def board_page(request: Request, poll_id: str) -> HTMLResponse:
    service = deps(request).service
    poll = service.poll(poll_id)
    # Ein Pruefbericht fuer die ganze Seite: Kette, Signaturen, Abrechnung,
    # Auszaehlung und die Eintraege selbst kommen aus demselben Durchlauf.
    bericht = service.pruefbericht(poll_id)
    status, accounting = bericht.chain, bericht.accounting
    if not status.sound or not accounting.ok:
        service.check_consistency(poll_id, bericht)
    try:
        result: dict[str, int] | None = service.tally(poll_id, bericht)
        result_error = None
    except Rejected as exc:
        result, result_error = None, str(exc)
    return page(
        request,
        "board.html",
        poll=poll,
        batches=bericht.batches,
        n_entries=bericht.n_entries,
        status=status,
        accounting=accounting,
        result=result,
        result_error=result_error,
        public_key=service.poll_pubkey_pem(poll_id),
        beleg_public_key=service.beleg_public_key_pem,
        batch_k=service.batch_k,
        batch_deckel_h=service.batch_deckel_s // 3600,
    )


@router.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request, poll: str = "", token: str = "") -> HTMLResponse:
    service = deps(request).service
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
        batch_k=service.batch_k,
        batch_deckel_h=service.batch_deckel_s // 3600,
    )


@router.get("/debug", response_class=HTMLResponse)
async def debug_page(request: Request, level: str = "all") -> HTMLResponse:
    # Phase-A- und Phase-B-Vorgaenge stehen nicht mehr im Ereignisstrom, sondern
    # in einer stundenweisen Zaehlung ohne Reihenfolge (debug.TEILNAHME,
    # EIP-T-041). Vorher lagen sie mit Sekundenstempel nebeneinander - wer beides
    # sah, konnte ueber die Zeit korrelieren, also genau die Zuordnung
    # herstellen, die das Verfahren verhindern soll (EIP-T-018).
    require_admin(request)
    service = deps(request).service
    findings = service.check_all()
    return page(
        request,
        "debug.html",
        events=log.events(level),
        teilnahme=log.teilnahme(),
        counts=log.counts(),
        level=level,
        findings={k: v for k, v in findings.items() if v},
        polls=service.polls(),
    )


# Markdown-Dokumente, die als eigene Seite ausgeliefert werden. Erzeugt werden
# die Dateien von scripts/sync_public_docs.py im Elternordner, der nicht Teil
# dieses Repos ist.
#
# Warum Kodex, Protokoll und Transparenzbericht hier stehen (EIP-T-063):
# KODEX Paragraf 10 verlangt, dass Selbstbindung und Verstoesse von aussen
# erreichbar sind. Ein Verstossprotokoll, das nur der Betreiber lesen kann,
# erfuellt keine Offenlegungspflicht - das war der offene Punkt 4 aus V-001.
DOKUMENTE = {
    "manifest": ("MANIFEST.md", "Manifest"),
    "kodex": ("KODEX.md", "Kodex"),
    "kodex-protokoll": ("KODEX-PROTOKOLL.md", "Kodex-Protokoll"),
    "transparenz": ("TRANSPARENZ.md", "Transparenzbericht"),
}

_dokument_cache: dict[str, tuple[float, str]] = {}


def dokument_html(name: str) -> str:
    """Rendert ein Markdown-Dokument aus DOKUMENTE, gecacht bis es sich aendert.

    Die Prosa steht bewusst nicht im Template: Sie lief dort schon einmal
    gegenueber dem Manifest auseinander und behauptete Zusagen, die das Manifest
    zurueckgenommen hatte (EIP-T-044). Nach KODEX.md bindet das Manifest jede
    Oberflaeche - eine zweite, handgepflegte Fassung ist deshalb kein
    Duplikat, sondern eine Fehlerquelle mit Aussenwirkung. Fuer Kodex und
    Verstossprotokoll gilt dasselbe schaerfer: Eine abweichende Zweitfassung
    waere hier nicht nur ungenau, sondern ein Verstoss gegen Paragraf 20.
    """
    dateiname, titel = DOKUMENTE[name]
    pfad = BASE_DIR / dateiname
    try:
        stamp = pfad.stat().st_mtime
    except OSError as exc:
        log.error("dokument", f"{dateiname} nicht lesbar: {exc}")
        return f"<p>{titel} ist gerade nicht abrufbar.</p>"

    gecacht = _dokument_cache.get(name)
    if gecacht is None or gecacht[0] != stamp:
        text = pfad.read_text(encoding="utf-8")
        # Der Sync-Hinweis am Dateikopf richtet sich an Bearbeiter, nicht an Besucher.
        if text.lstrip().startswith("<!--"):
            text = text.split("-->", 1)[1]
        # Tabellen und Codebloecke: Der Kodex besteht zu einem guten Teil aus
        # beidem - ohne die Erweiterungen liest sich die Schuldenuebersicht als
        # Pipe-Wueste.
        html = markdown.markdown(text, extensions=["tables", "fenced_code"])
        # Erster Absatz nach der Ueberschrift ist die Lead-Zeile der Seite.
        html = html.replace("</h1>\n<p>", '</h1>\n<p class="lead">', 1)
        # Tabellen in den Scroll-Container der Anwendung haengen. Markdown kennt
        # ihn nicht, und ohne ihn schiebt die Schuldenuebersicht auf schmalen
        # Geraeten die ganze Seite zur Seite.
        html = html.replace("<table>", '<div class="table-wrap"><table>')
        html = html.replace("</table>", "</table></div>")
        _dokument_cache[name] = (stamp, html)
    return _dokument_cache[name][1]


@router.get("/manifest", response_class=HTMLResponse)
async def manifest_page(request: Request) -> HTMLResponse:
    return page(
        request, "dokument.html", active="manifest",
        dokument=dokument_html("manifest"), titel="Manifest",
    )


@router.get("/kodex", response_class=HTMLResponse)
async def kodex_page(request: Request) -> HTMLResponse:
    return page(
        request, "dokument.html", active="kodex",
        dokument=dokument_html("kodex"), titel="Kodex", breit=True,
    )


@router.get("/kodex/protokoll", response_class=HTMLResponse)
async def kodex_protokoll_page(request: Request) -> HTMLResponse:
    return page(
        request,
        "dokument.html",
        active="kodex",
        dokument=dokument_html("kodex-protokoll"),
        titel="Kodex-Protokoll",
        breit=True,
    )


@router.get("/transparenz", response_class=HTMLResponse)
async def transparenz_page(request: Request) -> HTMLResponse:
    return page(
        request,
        "dokument.html",
        active="kodex",
        dokument=dokument_html("transparenz"),
        titel="Transparenzbericht",
        breit=True,
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    return page(request, "admin.html", polls=deps(request).service.polls())


# ---------------------------------------------------------------------------
# API - Authentifizierung
# ---------------------------------------------------------------------------


@router.post("/api/auth")
async def api_auth(request: Request, payload: dict) -> JSONResponse:
    d = deps(request)
    pseudonym = d.authenticator.authenticate(str(payload.get("credential", "")))
    log.info("auth", f"Authentifiziert ueber: {d.authenticator.name}")
    response = JSONResponse({"ok": True, "real_identity": d.authenticator.is_real_identity})
    response.set_cookie(
        SESSION_COOKIE,
        _sign(request, pseudonym),
        httponly=True,
        samesite="lax",
        secure=d.settings.public,
    )
    return response


@router.post("/api/auth/abort")
async def api_auth_abort() -> JSONResponse:
    log.reject("auth", "Dialog 'Ausweis auslesen' abgebrochen.")
    return JSONResponse({"ok": True})


@router.post("/api/logout")
async def api_logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


# ---------------------------------------------------------------------------
# API - Phase A und Phase B
# ---------------------------------------------------------------------------


@router.post("/api/token/{poll_id}")
async def api_token(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    pseudonym = current_pseudonym(request)
    if pseudonym is None:
        raise Rejected("Nicht authentifiziert - Phase A verlangt eine Identitaet.")
    try:
        blinded = bytes.fromhex(str(payload.get("blinded", "")))
    except ValueError as exc:
        raise Rejected("Verblindete Anfrage ist kein Hex.") from exc
    blind_sig = deps(request).service.issue_blind_signature(poll_id, pseudonym, blinded)
    return JSONResponse({"blind_sig": blind_sig.hex()})


@router.post("/api/vote/{poll_id}")
async def api_vote(request: Request, poll_id: str, payload: dict) -> JSONResponse:
    # Phase B kommt ohne Identitaet aus - das Token ist die ganze Berechtigung.
    # Traegt der Request trotzdem Sitzungskontext aus Phase A (Cookie,
    # Auth-Header, Referrer), empfaengt der Server Identitaet und Stimme im
    # selben Request und die Trennung aus §2 ist Behauptung statt Struktur
    # (EIP-T-033, Baustein F). Der Client sendet deshalb nichts davon
    # (ballot.js, credentials "omit"); kommt doch etwas an, ist das ein
    # sichtbarer Befund, keine stille Duldung. Nicht abweisen: Die Verkettung
    # ist mit dem Empfang bereits passiert, eine Abweisung wuerde nur die
    # Stimme kosten, nichts schuetzen.
    mitgesandt = [name for name in (SESSION_COOKIE, ADMIN_COOKIE) if name in request.cookies]
    if request.headers.get("authorization"):
        mitgesandt.append("authorization")
    if request.headers.get("referer"):
        mitgesandt.append("referer")
    if mitgesandt:
        log.inconsistency(
            "unverkettbarkeit",
            "Abstimm-Request traegt Sitzungskontext aus Phase A - "
            "Identitaet und Stimme im selben Request (EIP-T-033 F).",
            poll=poll_id,
            mitgesandt=", ".join(mitgesandt),
        )
    service = deps(request).service
    try:
        token = bytes.fromhex(str(payload.get("token", "")))
        sig = bytes.fromhex(str(payload.get("sig", "")))
    except ValueError as exc:
        raise Rejected("Token oder Signatur ist kein Hex.") from exc
    choices = [str(c) for c in payload.get("choices", [])]
    beleg = service.cast_vote(poll_id, token, sig, choices)
    return JSONResponse(
        {
            "ok": True,
            "leaf_hash": beleg.entry.leaf_hash,
            "batch": beleg.batch,
            "beleg_sig": beleg.sig_hex,
            "token": token.hex(),
            # Oeffentlich gezaehlt wird nur Veroeffentlichtes: die eigene
            # Stimme erscheint erst mit ihrem Batch (ADR E4).
            "participation": service.participation(poll_id),
        }
    )


@router.get("/api/board/{poll_id}")
async def api_board(request: Request, poll_id: str) -> JSONResponse:
    """Das Board als Datei - Grundlage der Pruefung durch Dritte (§7).

    Zusammen mit verifikation.py rechnet damit jeder das Ergebnis nach, ohne
    diesem Server etwas zu glauben:

        curl -sO http://.../api/board/{poll_id}
        python3 verifikation.py board.json
    """
    return JSONResponse(deps(request).service.board_export(poll_id))


@router.get("/api/status/{poll_id}")
async def api_status(request: Request, poll_id: str) -> JSONResponse:
    service = deps(request).service
    poll = service.poll(poll_id)
    accounting = service.laufender_bericht(poll_id).accounting
    return JSONResponse(
        {
            "poll": poll.poll_id,
            "closed": poll.closed,
            "participation": accounting.n_votes,
            "n_eligible": accounting.n_eligible,
            "accounting_ok": accounting.ok,
        }
    )


# ---------------------------------------------------------------------------
# API - Admin
# ---------------------------------------------------------------------------


@router.post("/api/admin/login")
async def api_admin_login(request: Request, payload: dict) -> JSONResponse:
    settings = deps(request).settings
    if not hmac.compare_digest(str(payload.get("token", "")), settings.admin_token):
        raise Rejected("Admin-Token falsch.")
    response = JSONResponse({"ok": True})
    # secure=True nur oeffentlich: lokal laeuft die App ueber http, dort wuerde
    # das Flag das Cookie verwerfen und die Anmeldung unmoeglich machen.
    response.set_cookie(
        ADMIN_COOKIE,
        _sign(request, "admin"),
        httponly=True,
        samesite="lax",
        secure=settings.public,
    )
    return response


@router.post("/api/admin/create")
async def api_admin_create(request: Request, payload: dict) -> JSONResponse:
    require_admin(request)
    options = [str(o) for o in payload.get("options", [])]
    poll = deps(request).service.create_poll(
        str(payload.get("poll_id", "")), str(payload.get("question", "")), options
    )
    return JSONResponse({"ok": True, "poll_id": poll.poll_id})


@router.post("/api/admin/close/{poll_id}")
async def api_admin_close(request: Request, poll_id: str) -> JSONResponse:
    require_admin(request)
    deps(request).service.close_poll(poll_id)
    return JSONResponse({"ok": True})


@router.post("/api/debug/clear")
async def api_debug_clear(request: Request) -> JSONResponse:
    # Das Log ist die Stelle, an der Manipulation auffaellt - Leeren darf nicht
    # jedes Netzgeraet koennen (EIP-T-018).
    require_admin(request)
    log.clear()
    return JSONResponse({"ok": True})


@router.post("/api/shutdown")
async def api_shutdown(request: Request) -> JSONResponse:
    """Beenden-Knopf - damit kein Terminal haengen bleibt.

    Nur vom Rechner aus, auf dem der Server laeuft: Im LAN (EIP-T-009) darf kein
    Teilnehmergeraet die App fuer alle anderen beenden koennen. Oeffentlich gibt
    es den Weg gar nicht - dort beendet die Plattform den Prozess, und eine
    erreichbare Abschaltroute waere nur eine Angriffsflaeche.
    """
    if deps(request).settings.public:
        raise Rejected("Diese Instanz wird von der Plattform verwaltet.", status_code=404)
    if not is_local(request):
        raise Rejected("Beenden ist nur auf dem Rechner moeglich, auf dem die App laeuft.")
    log.info("system", "Server wird beendet (Beenden-Knopf).")
    os.kill(os.getpid(), 15)
    return JSONResponse({"ok": True})


def app_from_env() -> FastAPI:
    """Die Instanz, wie sie aus Umgebungsvariablen hervorgeht (uvicorn-Start)."""
    return create_app(
        store_path=Path(os.environ.get("EIDPOLL_DB", BASE_DIR / "data" / "eidpoll.sqlite3")),
        authenticator=CodeAuthenticator(),
        settings=Settings.from_env(),
    )


_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    """``web:app`` bleibt der Einstieg fuer uvicorn - aber erst beim Zugriff.

    Wuerde die Instanz beim Import entstehen, haette schon `import web` eine
    Datenbank angelegt und ein Admin-Token erzeugt. Ein Test, der sich seine
    eigene Instanz baut (EIP-T-048), bekaeme daneben still eine zweite auf dem
    Standardpfad.
    """
    if name == "app":
        global _app
        if _app is None:
            _app = app_from_env()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
