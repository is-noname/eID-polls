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
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import markdown
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import rsa_raw
import stand as stand_modul
from anker import standard_zeugen
from auth import AuthError, Authenticator, CodeAuthenticator
from config import Settings, anonymitaetshinweis
import debug
from debug import kategorie_fuer_pfad, log, log_berechtigung, log_board, log_fuer
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

    # Welcher Stand hier laeuft, und ob er vom veroeffentlichten abweicht
    # (EIP-T-074, KODEX §20). Beim Start und nicht erst beim ersten Aufruf von
    # /debug: Der Fall aus V-001 war eine Instanz, die tagelang lief - wer sie
    # gestartet hat, soll die Abweichung im Startprotokoll sehen, auch wenn
    # niemand die Debug-Seite oeffnet.
    ergebnis = stand_modul.melde(log)
    kennung = f"{ergebnis.stand['commit'][:12]} ({ergebnis.stand['commit_quelle']})"
    for line in (
        f"Ausgelieferter Stand: {kennung}, {ergebnis.stand['treehash'][:19]}...",
        *(f"ABWEICHUNG: {b}" for b in ergebnis.befunde),
    ):
        print(f"[eidpoll] {line}", flush=True)
    log.info("auslieferung", f"Ausgelieferter Stand: {kennung}")

    # Signiert wird ueber OpenSSL, nicht ueber pow() (EIP-T-093, KODEX §3).
    # Fehlt libcrypto, gibt diese Instanz keine Stimm-Token aus - das soll beim
    # Start auffallen und nicht erst, wenn die erste Person abstimmen will.
    # Ein stiller Rueckfall auf die ungehaertete Rechnung waere die Alternative
    # gewesen und ist ausgeschlossen; deshalb ist das hier eine Betriebsfrage.
    signieren_ok, signieren_meldung = rsa_raw.verfuegbar()
    if signieren_ok:
        log.info("system", signieren_meldung)
    else:
        log.error("system", f"Signieroperation nicht einsatzbereit: {signieren_meldung}")
        print(f"[eidpoll] ACHTUNG: {signieren_meldung}", flush=True)
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
            # Erst schliessen, dann veroeffentlichen: close_poll leert den
            # Puffer ohnehin, und eine Umfrage, deren Laufzeit vorbei ist, soll
            # nicht noch einen Batch als offene erzeugen (EIP-T-091).
            try:
                d.service.schliesse_abgelaufene()
            except Exception as exc:
                log.exception("poll", exc)
            d.service.publiziere_faellige()
            # Derselbe Takt fuer den Ablauf des Wiederhol-Puffers (EIP-T-070):
            # eine Lebensdauer, die nur beim naechsten Zugriff geprueft wird,
            # laesst die Zeilen bei stillstehender Umfrage unbegrenzt liegen.
            try:
                d.service.verwirf_abgelaufene_wiederholungen()
            except Exception as exc:
                log.exception("phase-a", exc)
            # Und derselbe Takt fuer die externen Anker
            # (EIP-ADR-20260801-002, E4): Beauftragen und Aufwerten sind
            # Netzaufrufe und gehoeren deshalb hierher und nicht in den
            # Veroeffentlichungspfad - sonst haenge die Sichtbarkeit einer
            # Stimme an der Erreichbarkeit einer fremden TSA.
            try:
                d.service.arbeite_anker_ab()
            except Exception as exc:
                log.exception("anker", exc)

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
            zeugen=standard_zeugen() if effective.anker else (),
            anker_frist_s=int(effective.anker_frist_h * 3600),
            anker_upgrade_s=int(effective.anker_upgrade_h * 3600),
            anker_toleranz_s=int(effective.anker_toleranz_min * 60),
            anonymitaetsschwelle=effective.anonymitaetsschwelle,
            laufzeit_tage=effective.laufzeit_tage,
            auswertungsplan=effective.auswertungsplan,
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
    async def _phasentrennung(request: Request, call_next):  # type: ignore[no-untyped-def]
        pfad = request.url.path
        phasenroute = pfad.startswith("/api/token/") or pfad.startswith("/api/vote/")
        start = time.monotonic()
        response = await call_next(request)
        if phasenroute and floor_s > 0:
            rest = floor_s - (time.monotonic() - start)
            if rest > 0:
                await asyncio.sleep(rest)
        if phasenroute or _traegt_identitaet(request, response):
            response.headers["connection"] = "close"
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
    # Simulierter eID-Flow (EIP-T-095): Diensteanbieter und Ausweis-App als
    # nachgestellte Fremdsysteme, damit Testpersonen den vollstaendigen Ablauf
    # erleben. Haengt am Authenticator und nicht an einem eigenen Schalter -
    # sobald hier ein echter Ausweis geprueft wird, waere eine daneben
    # erreichbare Simulation genau der Zustand, vor dem
    # EIP-RFC-20260725-002 Schritt 4 warnt.
    if not app.state.deps.authenticator.is_real_identity:
        import eid_sim

        app.include_router(eid_sim.router)
    return app


# ---------------------------------------------------------------------------
# Signierte Cookies (Pseudonym verlaesst den Server nur signiert)
# ---------------------------------------------------------------------------


def _traegt_identitaet(request: Request, response: Response) -> bool:
    """Hat diese Verbindung eine Identitaet gesehen (EIP-T-034, Verbindungsebene)?

    Hintergrund. Baustein F aus EIP-T-033 nimmt dem Abstimm-Request Cookie,
    Auth-Header und Referrer. Was er nicht anfasst, ist die Schicht darunter:
    Seit EIP-ADR-20260725-002 laufen Phase A und Phase B in einem Klick, gegen
    dieselbe Origin, etwa eine Sekunde auseinander - also typischerweise ueber
    **dieselbe TCP-Verbindung**. Wer den Socket sieht, verkettet Pseudonym und
    Stimme, ohne ein einziges Feld zu lesen. Heute verdeckt Renders Loadbalancer
    das (bei uns endet nur der Proxy-Socket); ein Onion-Service oder ein eigener
    Server nimmt genau diesen Proxy weg und reicht uns den Client-Socket. Ohne
    diese Funktion tauschte der anonyme Kanal den Korrelator aus, statt ihn zu
    entfernen.

    Regel. Eine Verbindung, die eine Identitaet getragen hat, endet mit ihrer
    Antwort. Eine Verbindung, die nie eine getragen hat, darf eine Stimme
    tragen - deshalb genuegt es, hier auf das Sitzungs- und das Admin-Cookie zu
    sehen, in beiden Richtungen: mitgesandt (die Verbindung hat es schon) und
    gesetzt (sie bekommt es mit dieser Antwort). Die Phasen-Routen schliessen
    zusaetzlich immer, auch anonym - sonst haenge die Trennung daran, dass der
    Client die Reihenfolge einhaelt.

    Nicht gemessen, sondern verhindert. Feststellen, *ob* zwei Requests
    denselben Socket hatten, hiesse Absender-Port und -Adresse vorhalten - ein
    neues Datum ueber Teilnehmende und damit ein Verstoss gegen § 1. Es gibt
    hier deshalb keinen Befund im Debug-Modul, nur die Anweisung.

    Grenze. Sie wirkt auf unsere Verbindung. Steht ein fremder Proxy davor
    (heute Render und Cloudflare), sieht der die Browser-Verbindung weiter als
    eine - dagegen hilft nur, diesen Proxy loszuwerden
    (EIP-T-075). Voraussetzung also, keine Loesung.
    """
    if SESSION_COOKIE in request.cookies or ADMIN_COOKIE in request.cookies:
        return True
    gesetzt = response.headers.getlist("set-cookie")
    return any(c.startswith((SESSION_COOKIE, ADMIN_COOKIE)) for c in gesetzt)


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
    # verkettet genauso wie zwei erfolgreiche Vorgaenge. Und sie laufen ins Log
    # ihrer Seite (EIP-T-033, G): kein einzelnes Log haelt beide Phasen.
    kategorie = kategorie_fuer_pfad(request.url.path, "abgewiesen")
    log_fuer(kategorie).reject(kategorie, str(exc), pfad=request.url.path)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": str(exc)}, status_code=400)
    status = getattr(exc, "status_code", 400)
    return page(request, "error.html", status_code=status, message=str(exc))


async def _auth_handler(request: Request, exc: Exception) -> JSONResponse:
    log_berechtigung.reject("auth", str(exc), pfad=request.url.path)
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
    context.setdefault("debug_counts", debug.counts_gesamt())
    context.setdefault("is_local", is_local(request))
    context.setdefault("public", d.settings.public)
    context.setdefault("demos", d.settings.demos)
    context.setdefault("demo_codes", d.authenticator.sample_codes())
    # Der Nenner steht jeder Vorlage zur Verfuegung, nicht nur der Board-Seite:
    # Eine Teilnahmezahl ohne ihn ist nach EIP-T-025 keine Aussage (KODEX §8).
    context.setdefault("nenner", d.settings.nenner)
    context.setdefault("nenner_bezeichnung", d.settings.nenner_bezeichnung)
    context.setdefault("nenner_quelle", d.settings.nenner_quelle)
    context.setdefault("nenner_quelle_url", d.settings.nenner_quelle_url)
    # Der Zugangshinweis begleitet den Nenner ueberall dorthin, wo er steht
    # (KODEX §11, EIP-T-092): Die Quote sagt, wie viele teilgenommen haben, der
    # Hinweis, wer gar nicht erst konnte.
    context.setdefault("zugang_hinweis", d.settings.zugang_hinweis)
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
    # Die Batch-Groessen stehen im Text unter der Umfrageliste (EIP-T-056): Sie
    # sagen, wie aktuell der aus dem Board ablesbare Stand ueberhaupt ist. Aus
    # der Konfiguration, nicht aus der Vorlage - eine Zahl, die im Template
    # steht, ueberlebt die erste Aenderung an config.py nicht.
    return page(
        request,
        "index.html",
        rows=rows,
        batch_k=service.batch_k,
        batch_deckel_h=service.batch_deckel_s // 3600,
    )


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
        batch_k=service.batch_k,
        batch_deckel_h=service.batch_deckel_s // 3600,
        # Rueckmeldung aus dem eID-Flow (EIP-T-095). Sie kommt als Query-Wert
        # zurueck, weil die Simulation die Seite verlaesst und ueber einen
        # Redirect zurueckkommt - ein Fehler aus einem fremden System hat sonst
        # keinen Weg an die Stelle, an der er entstanden ist.
        eid_fehler=request.query_params.get("eid_fehler"),
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
    # Die Ankerpruefung laeuft bei *jedem* Aufruf, nicht nur bei gebrochener
    # Kette: Ein umgeschriebenes Board hat eine intakte Kette - das ist der
    # ganze Grund fuer den Anker (EIP-ADR-20260801-002, E6.1).
    anker_befunde = service.pruefe_anker(poll_id, bericht)
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
        # Gemessen am veroeffentlichten Board, nicht die Zusage k: Die Zusage
        # kann der Zeitdeckel und das Schliessen unterschreiten, und wer sich
        # auf die Menge verlaesst, muss die kleinste sehen (EIP-T-076).
        stimmen_je_batch=bericht.stimmen_je_batch,
        kleinste_menge=min((s for s in bericht.stimmen_je_batch if s), default=None),
        status=status,
        accounting=accounting,
        result=result,
        result_error=result_error,
        # Aus dem Board gelesen, nicht aus den Einstellungen (EIP-T-090): Die
        # Schwelle gilt fuer *diese* Umfrage und steht in ihrem
        # POLL_OPEN-Eintrag. Ein Wert aus der laufenden Konfiguration waere
        # nachtraeglich zu drehen, bis das Label ausbleibt.
        anonymitaetsschwelle=bericht.anonymitaetsschwelle,
        anonymitaetshinweis=(
            anonymitaetshinweis(accounting.n_votes, bericht.anonymitaetsschwelle)
            if bericht.anonymitaetswarnung
            else None
        ),
        # Aus demselben Grund aus dem Board und nicht aus den Einstellungen
        # (EIP-T-091): Was die Seite als zugesagte Laufzeit und zugesagten Plan
        # zeigt, muss das sein, was im POLL_OPEN-Eintrag steht - sonst zeigt sie
        # die gerade geltende Absicht und nennt sie Praeregistrierung.
        laufzeit_start=bericht.laufzeit_start,
        laufzeit_ende=bericht.laufzeit_ende,
        auswertungsplan=bericht.auswertungsplan,
        public_key=service.poll_pubkey_pem(poll_id),
        beleg_public_key=service.beleg_public_key_pem,
        batch_k=service.batch_k,
        batch_deckel_h=service.batch_deckel_s // 3600,
        anker_je_batch=service.anker_je_batch(poll_id),
        anker_befunde=anker_befunde,
        # Die Pruefbefehle kommen von den Zeugen selbst, nicht aus der Vorlage:
        # Wer den Dienst austauscht, tauscht die Anleitung mit - eine Anleitung,
        # die auf einen frueheren Dienst zeigt, ist schlimmer als keine.
        anker_zeugen=[
            {"name": z.name, "titel": z.titel, "befehle": z.pruefanleitung(f"{poll_id}-batch-N")}
            for z in service.zeugen.values()
        ],
        # Der ausgelieferte Client, Datei fuer Datei: Die Nachweis-Seite ist die
        # Stelle, an der geprueft wird - und der Code im Browser gehoert zu dem,
        # was zu pruefen ist (Paragraf 20, EIP-T-007).
        client=stand_modul.client(),
    )


@router.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request) -> HTMLResponse:
    """Die Pruefseite - die Suche selbst laeuft im Browser (static/verify.js).

    Bewusst ohne Token-Parameter (EIP-T-033, Baustein F): Bis hierher nahm die
    Route das Token als GET-Parameter entgegen, und weil das Session-Cookie
    (path=/) an derselben Route mitfaehrt, lieferte, wer nach der Abstimmung
    angemeldet pruefte, dem Server Pseudonym und Token in einem Request. Jetzt
    steht das Token im URL-Fragment, das der Browser nie mitsendet, und die
    Suche laeuft ueber den Board-Export - der Server sieht nur noch, dass
    jemand das Board laedt, nicht wonach er sucht.
    """
    return page(request, "verify.html", polls=deps(request).service.polls())


@router.get("/version")
async def version() -> JSONResponse:
    """Welcher Stand hier laeuft - ohne Anmeldung, absichtlich.

    KODEX Paragraf 20 verlangt, dass die Uebereinstimmung von Repository und
    Auslieferung von aussen nachpruefbar ist und der Pruefweg ohne Rueckfrage
    bei uns begehbar (EIP-T-074). Eine Auskunft, fuer die man das Admin-Token
    braucht, waere keine: Pruefen will die Instanz gerade, wer uns nicht
    vertraut. Die Antwort traegt ihre Nachrechenvorschrift und ihre Grenze
    selbst mit - was sie nicht leistet, steht in ``grenze``.
    """
    return JSONResponse(stand_modul.stand())


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
    # Drei getrennte Logs, eine Sicht (EIP-T-033, G): Die Zusammenfuehrung
    # passiert erst hier, beim Anzeigen an den angemeldeten Betreiber - das
    # ist der bewusste Blick ueber die Trennlinie, keine Datenlage.
    return page(
        request,
        "debug.html",
        events=debug.events_gesamt(level),
        teilnahme=debug.teilnahme_gesamt(),
        counts=debug.counts_gesamt(),
        level=level,
        findings={k: v for k, v in findings.items() if v},
        polls=service.polls(),
        # Ausgelieferter Stand gegen veroeffentlichten (EIP-T-074, KODEX §20).
        # Gehoert hierher und nicht auf eine eigene Seite: Eine Instanz, die
        # anderen Code ausliefert als den veroeffentlichten, ist eine
        # Dateninkonsistenz wie eine gebrochene Board-Kette - nur eine, die
        # das Board selbst nicht sehen kann.
        auslieferung=stand_modul.melde(log),
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
    d = deps(request)
    return page(
        request,
        "admin.html",
        polls=d.service.polls(),
        # Die Vorgaben der Praeregistrierung gehoeren an das Formular, an dem sie
        # verbindlich werden (EIP-T-091): Wer anlegt, soll den Grundplan gelesen
        # haben, den er damit unterschreibt.
        laufzeit_tage=d.settings.laufzeit_tage,
        auswertungsplan=d.settings.auswertungsplan,
    )


# ---------------------------------------------------------------------------
# API - Authentifizierung
# ---------------------------------------------------------------------------


@router.post("/api/auth")
async def api_auth(request: Request, payload: dict) -> JSONResponse:
    d = deps(request)
    pseudonym = d.authenticator.authenticate(str(payload.get("credential", "")))
    log_berechtigung.info("auth", f"Authentifiziert ueber: {d.authenticator.name}")
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
    log_berechtigung.reject("auth", "Dialog 'Ausweis auslesen' abgebrochen.")
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


@router.post("/api/melde/signatur/{poll_id}")
async def api_melde_signatur(request: Request, poll_id: str) -> JSONResponse:
    """Der Client meldet, dass die entblindete Signatur nicht aufgeht (EIP-T-080).

    Der Fehler faellt dort auf, wo er nicht behoben werden kann: Die Pruefung
    nach RFC 9474 §4.4 laeuft im Browser, die Ursache liegt beim Server
    (falscher Umfrage-Schluessel, verrechnet, unterwegs verstuemmelt). Ohne
    diese Route wuesste der Betreiber davon nichts - und genau die
    Verwechslung, die das Ticket beschreibt, bliebe im Debug-Modul stehen:
    ein Serverfehler, der wie eine abgewiesene Stimme aussieht.

    Bewusst ohne Nutzlast. Es gibt nur eine Sache zu melden; ein Freitextfeld
    waere ein Kanal in das Log des Betreibers und kein Befund (§1). Die
    Anmeldung wird verlangt, damit die Meldung nicht von aussen erzeugbar ist -
    sie tritt ohnehin nur zwischen Phase A und der Ausgabe des Tokens auf.
    Protokolliert wird das Pseudonym dabei nicht.

    Kategorie ``signatur`` und nicht ``phase-a``: Gemeldet wird ein Defekt der
    Signaturausgabe, kein Teilnahmevorgang. Die Unterscheidung ist die aus
    EIP-T-041 - Teilnahmehandlungen werden je Stunde gezaehlt, damit ihre
    Reihenfolge nicht zur Verkettung wird; ein Defekt muss dagegen sofort und
    genau auffindbar sein. Denselben Weg geht die Unverkettbarkeits-Meldung in
    api_vote, die unter ``unverkettbarkeit`` statt unter ``phase-b`` steht.
    """
    if current_pseudonym(request) is None:
        raise Rejected("Nicht authentifiziert - diese Meldung entsteht nur in Phase A.")
    log_berechtigung.error(
        "signatur",
        "Client meldet: entblindete Signatur haelt der Pruefung nicht stand "
        "(RFC 9474 §4.4). Serverfehler, keine abgewiesene Stimme.",
        poll=poll_id,
    )
    return JSONResponse({"ok": True})


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
        log_board.inconsistency(
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

    ``zugang`` kommt aus KODEX §11 (EIP-T-092) und wird hier angehaengt, nicht in
    ``board_export()`` erzeugt: Alles, was der Kern in die Datei schreibt, liegt
    unter der Merkle-Root und ist nachrechenbar. Der Hinweis ist das nicht - er
    ist eine Aussage des Betreibers ueber die Zahl, und die gehoert nicht in
    denselben Topf wie das, was ein Dritter selbst pruefen kann.
    """
    export = deps(request).service.board_export(poll_id)
    export["zugang"] = deps(request).settings.zugang_hinweis
    return JSONResponse(export)


@router.get("/anker/{poll_id}/{batch}/root")
async def anker_root(request: Request, poll_id: str, batch: int) -> Response:
    """Die Batch-Root als 32 Rohbytes - die Datei, gegen die geprueft wird.

    Bewusst binaer und nicht als Hex-Text: Beide Zeugen bezeugen
    ``SHA256(rohbytes)``. Wer die Hex-Zeile prueft, prueft den Hash einer
    Zeichenkette und bekommt eine Abweichung, die nach Betrug aussieht und
    keiner ist.
    """
    service = deps(request).service
    for b in service.pruefbericht(poll_id).batches:
        if b.n == batch:
            return Response(
                content=bytes.fromhex(b.batch_root),
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{poll_id}-batch-{batch}.root"'
                },
            )
    raise Rejected(f"Batch {batch} gibt es in '{poll_id}' nicht.", 404)


@router.get("/anker/{poll_id}/{batch}/{dienst}")
async def anker_download(request: Request, poll_id: str, batch: int, dienst: str) -> Response:
    """Der Ankerbeleg eines Batches - pruefbar mit fremden Standardwerkzeugen.

    Oeffentlich und nicht im Admin-Bereich: Ein Anker, den nur der Betreiber
    herunterladen kann, bezeugt nichts (KODEX §7, §20).
    """
    beleg, name = deps(request).service.anker_beleg(poll_id, batch, dienst)
    return Response(
        content=beleg,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/api/status/{poll_id}")
async def api_status(request: Request, poll_id: str) -> JSONResponse:
    """Die veroeffentlichten Zahlen dieser Umfrage - maschinenlesbar.

    ``result`` ist dieselbe Auszaehlung, die /board/{poll_id} anzeigt, und steht
    hier, damit ein unabhaengiger Pruefer sie gegen seine eigene halten kann
    (auditor.py, EIP-T-071). Ohne sie muesste er die HTML-Seite auslesen und
    haette am Ende verglichen, was er selbst geparst hat. Solange die Umfrage
    laeuft, gibt es kein Ergebnis - dann steht in ``result_error``, warum.

    ``nenner`` und ``zugang`` stehen dabei neben ``result``, weil beide zur Zahl
    gehoeren und nicht zur Seite, die sie anzeigt (KODEX §8, §11; EIP-T-025,
    EIP-T-092): Wer das Ergebnis von hier holt, bekommt den Nenner und die
    Zugangsvoraussetzung mit, statt sie aus dem HTML klauben zu muessen.
    """
    d = deps(request)
    service, settings = d.service, d.settings
    poll = service.poll(poll_id)
    bericht = service.laufender_bericht(poll_id)
    accounting = bericht.accounting
    try:
        result: dict[str, int] | None = service.tally(poll_id, bericht)
        result_error: str | None = None
    except Rejected as exc:
        result, result_error = None, str(exc)
    return JSONResponse(
        {
            "poll": poll.poll_id,
            "closed": poll.closed,
            "participation": accounting.n_votes,
            "n_eligible": accounting.n_eligible,
            "accounting_ok": accounting.ok,
            "nenner": settings.nenner,
            "nenner_bezeichnung": settings.nenner_bezeichnung,
            "nenner_quelle": settings.nenner_quelle,
            "zugang": settings.zugang_hinweis,
            # Wie Nenner und Zugangshinweis: Das Warnlabel darf beim
            # Weitertragen nicht abfallen (EIP-T-090). Der Wert kommt aus dem
            # POLL_OPEN-Eintrag dieser Umfrage, nicht aus den Einstellungen.
            "min_anonymity_threshold": bericht.anonymitaetsschwelle,
            "anonymitaetswarnung": bericht.anonymitaetswarnung,
            "anonymitaetshinweis": (
                anonymitaetshinweis(accounting.n_votes, bericht.anonymitaetsschwelle)
                if bericht.anonymitaetswarnung
                else None
            ),
            # Die Praeregistrierung geht mit dem Ergebnis mit (EIP-T-091,
            # KODEX §7), aus dem Grund, der schon fuer Nenner und Warnlabel
            # gilt: Wer die Zahl von hier holt, soll die Zusage danebenhaben -
            # sonst faellt genau der Massstab weg, an dem eine nachtraegliche
            # Aenderung erkennbar waere.
            "laufzeit_start": (
                bericht.laufzeit_start.isoformat() if bericht.laufzeit_start else None
            ),
            "laufzeit_ende": (
                bericht.laufzeit_ende.isoformat() if bericht.laufzeit_ende else None
            ),
            "auswertungsplan": bericht.auswertungsplan,
            "result": result,
            "result_error": result_error,
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
    # Laufzeit-Ende als ISO-8601 aus dem Formular (EIP-T-091). Unlesbar heisst
    # abweisen und nicht "dann eben die Vorgabe": Wer ein Ende angibt, hat eines
    # gemeint, und still ein anderes zu praeregistrieren waere die Sorte
    # Abweichung, gegen die dieser ganze Eintrag steht.
    ende_roh = str(payload.get("laufzeit_ende", "")).strip()
    try:
        ende = datetime.fromisoformat(ende_roh) if ende_roh else None
    except ValueError as exc:
        raise Rejected(
            f"Das Ende der Laufzeit ist kein lesbarer Zeitpunkt: '{ende_roh}'. "
            "Erwartet wird ISO 8601, etwa 2026-08-17T18:00."
        ) from exc
    poll = deps(request).service.create_poll(
        str(payload.get("poll_id", "")),
        str(payload.get("question", "")),
        options,
        laufzeit_ende=ende,
        auswertungsplan_zusatz=str(payload.get("auswertungsplan_zusatz", "")),
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
    debug.clear_alle()
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
