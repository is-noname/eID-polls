"""Simulierter eID-Flow: der Dienst eines Dritten und die Ausweis-App.

Warum das existiert (EIP-T-095): Bis hierher endete Schritt 1 der Umfrageseite
in einem Modal mit dem Feld "Ausweisnummer". Was dabei fehlte, ist nicht
Kosmetik, sondern die Haelfte des Erlebnisses - im Ernstfall verlaesst man die
Seite, landet bei einem Dritten, sieht eine Datenauskunft, wechselt in eine
zweite Anwendung, legt den Ausweis auf und tippt eine PIN. Genau an diesen
Stellen entsteht Vertrauen oder Abbruch, und genau die konnte der Probandentest
(EIP-T-010) bisher nicht beobachten.

Simuliert werden ausschliesslich die **Fremdsysteme**:

  Umfrage-App  ->  eID-Dienst (Dritter)  ->  Ausweis-App  ->  zurueck
   echt              simuliert               simuliert        echt

Die eigene App bleibt unberuehrt. Am Ende der Simulation wird derselbe
``Authenticator.authenticate()`` aufgerufen wie vorher im Modal - Pseudonym,
Blindsignatur, Ledger und Board kennen diesen Umweg nicht. Wird der Stub eines
Tages durch ``SamlEidAuthenticator`` ersetzt (EIP-T-004), faellt dieses Modul
ersatzlos weg; es ist kein Vorbau fuer den echten Flow, sondern sein Platzhalter.

WAS DIESES MODUL NICHT TUT, und zwar mit Absicht:

  - Es bildet **keine reale Organisation** nach. Kein Bundeswappen, kein
    Governikus-Logo, nicht der Markenauftritt der echten AusweisApp. Der Dienst
    heisst "eID-Dienst (Simulation)", der Client "Ausweis-App (Simulation)".
    Eine pixelgenaue Nachbildung waere keine Vorfuehrung mehr, sondern eine
    Faelschung - auch ohne Missbrauchsabsicht.
  - Es liest **keinen Ausweis** und prueft **keine Identitaet**. Jede Seite
    dieses Moduls sagt das (KODEX §4, faellig ab Betriebsstufe "oeffentlich
    erreichbar"), und der Pfad /eid-sim/ sagt es zusaetzlich in der Adresszeile.
    Der Nachtrag in EIP-RFC-20260725-002 nimmt die Kennzeichnung aus der
    *Teilnehmeransicht*; diese Seiten stellen fremde Systeme dar und fallen
    nicht darunter.
  - Es spricht **kein TR-03124**. Es gibt kein TC-Token, keinen Aufruf von
    127.0.0.1:24727, keine SAML-Assertion. Der Ablauf ist nachgestellt, nicht
    nachgebaut - wer hier eine Protokollimplementierung vermutet, irrt.

Datensparsamkeit (KODEX §1): Die Sitzung lebt im Arbeitsspeicher dieses
Prozesses, haelt nur Umfrage-ID, Schritt, Fehlversuche und - zwischen Karten-
und PIN-Schritt - die eingegebene Ausweisnummer. Sie verfaellt nach
SITZUNG_TTL_S und wird beim Abschluss sofort geloescht. Die Ausweisnummer geht
in kein Log; protokolliert wird, dass ein Schritt stattfand, nicht womit.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Literal

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import web
from auth import AuthError
from debug import log_berechtigung
from poll_service import Rejected

router = APIRouter(prefix="/eid-sim")

# Lebensdauer einer angefangenen Anmeldung. Kurz genug, dass ein abgebrochener
# Versuch nichts hinterlaesst, lang genug fuer jemanden, der die Datenauskunft
# tatsaechlich liest.
SITZUNG_TTL_S = 15 * 60

# Fehlversuche bis zur Sperre - drei, wie beim echten Ausweis. Der Zaehler ist
# der Grund, warum die PIN hier ueberhaupt vorkommt: Ohne ihn waere sie ein
# Formularfeld ohne Bedeutung, mit ihm ist sie die Stelle, an der Menschen im
# Ernstfall wirklich scheitern.
PIN_VERSUCHE = 3

# Die PIN dieser Vorfuehrung. Sie steht offen auf der Seite - eine geheime PIN
# in einer Simulation waere keine Sicherheit, sondern eine Sackgasse.
SIM_PIN = "123456"

Schritt = Literal["dienst", "karte", "auskunft", "pin", "gesperrt", "fertig"]


@dataclass
class Sitzung:
    """Eine angefangene Anmeldung. Alles daran ist fluechtig."""

    poll_id: str
    schritt: Schritt = "dienst"
    versuche_offen: int = PIN_VERSUCHE
    erstellt: float = field(default_factory=time.monotonic)
    # Nur zwischen Karten- und PIN-Schritt gesetzt. Danach geloescht, siehe
    # _abschliessen(). Absichtlich nicht in __repr__-freundlicher Form
    # protokolliert.
    ausweisnummer: str | None = None

    def abgelaufen(self) -> bool:
        return time.monotonic() - self.erstellt > SITZUNG_TTL_S


_sitzungen: dict[str, Sitzung] = {}


def _aufraeumen() -> None:
    for sid in [sid for sid, s in _sitzungen.items() if s.abgelaufen()]:
        _sitzungen.pop(sid, None)


def _sitzung(sid: str) -> Sitzung:
    _aufraeumen()
    sitzung = _sitzungen.get(sid)
    if sitzung is None:
        # Nach Ablauf, nach Abschluss und bei geratener ID dieselbe Antwort:
        # Der Unterschied waere eine Auskunft darueber, ob es diese Anmeldung
        # einmal gab.
        raise Rejected(
            "Diese Anmeldung ist abgelaufen oder wurde bereits abgeschlossen. "
            "Bitte auf der Umfrageseite neu beginnen.",
            status_code=404,
        )
    return sitzung


def _seite(request: Request, template: str, **context: object) -> HTMLResponse:
    """Rendert eine Simulationsseite.

    Bewusst nicht ueber ``web.page()``: Diese Seiten erben nicht von base.html,
    weil sie ein *fremdes* System darstellen. Wuerden sie Topbar, Navigation und
    Markenzeile der Umfrage tragen, waere der Kontextwechsel - der eigentliche
    Gegenstand dieser Simulation - genau der Teil, der fehlt.
    """
    d = web.deps(request)
    context.setdefault("public", d.settings.public)
    context.setdefault("sim_pin", SIM_PIN)
    return d.templates.TemplateResponse(request, template, context)


def _zurueck_zur_umfrage(poll_id: str) -> RedirectResponse:
    return RedirectResponse(f"/poll/{poll_id}", status_code=303)


# ---------------------------------------------------------------------------
# Schritt 0 - Weiterleitung weg von der Umfrage
# ---------------------------------------------------------------------------


@router.get("/start/{poll_id}")
async def start(request: Request, poll_id: str) -> RedirectResponse:
    """Die Umfrageseite gibt ab.

    Ein GET mit Redirect und keine JSON-Route: Was hier nachgestellt wird, ist
    ein Verlassen der Seite. Ein Modal, das im Hintergrund einen Aufruf macht,
    waere wieder genau das, was EIP-T-095 abloest.
    """
    # Existiert die Umfrage nicht, faellt das hier auf und nicht erst nach
    # Datenauskunft und PIN.
    web.deps(request).service.poll(poll_id)
    _aufraeumen()
    sid = secrets.token_urlsafe(16)
    _sitzungen[sid] = Sitzung(poll_id=poll_id)
    log_berechtigung.info("auth", "eID-Anmeldung begonnen (Simulation).", poll=poll_id)
    return RedirectResponse(f"/eid-sim/dienst/{sid}", status_code=303)


# ---------------------------------------------------------------------------
# Schritt 1 - der Dritte: Datenauskunft und Berechtigungszertifikat
# ---------------------------------------------------------------------------


@router.get("/dienst/{sid}", response_class=HTMLResponse)
async def dienst(request: Request, sid: str) -> HTMLResponse:
    sitzung = _sitzung(sid)
    return _seite(
        request,
        "eidsim_dienst.html",
        sid=sid,
        poll=web.deps(request).service.poll(sitzung.poll_id),
    )


@router.post("/dienst/{sid}/weiter")
async def dienst_weiter(sid: str) -> RedirectResponse:
    sitzung = _sitzung(sid)
    sitzung.schritt = "karte"
    return RedirectResponse(f"/eid-sim/client/{sid}", status_code=303)


# ---------------------------------------------------------------------------
# Schritt 2 - die Ausweis-App: Karte, Auskunft, PIN
# ---------------------------------------------------------------------------


@router.get("/client/{sid}", response_class=HTMLResponse)
async def client(request: Request, sid: str) -> HTMLResponse:
    sitzung = _sitzung(sid)
    return _seite(
        request,
        "eidsim_client.html",
        sid=sid,
        schritt=sitzung.schritt,
        versuche_offen=sitzung.versuche_offen,
        fehler=request.query_params.get("fehler"),
    )


@router.post("/client/{sid}/karte")
async def client_karte(request: Request, sid: str, ausweisnummer: str = Form("")) -> RedirectResponse:
    """Der Ausweis wird aufgelegt.

    Die "Ausweisnummer" ist der Zugangscode aus auth.py - dieselbe Eingabe wie
    bisher im Modal, nur an der Stelle, an der im Ernstfall der Chip antwortet.
    Geprueft wird sie hier noch nicht: Ein echter Ausweis wird erst nach der PIN
    ausgelesen, und eine Simulation, die frueher abweist, bringt Testpersonen
    eine Reihenfolge bei, die es nicht gibt.
    """
    sitzung = _sitzung(sid)
    if not ausweisnummer.strip():
        return RedirectResponse(
            f"/eid-sim/client/{sid}?fehler=Kein+Ausweis+erkannt.", status_code=303
        )
    sitzung.ausweisnummer = ausweisnummer.strip()
    sitzung.schritt = "auskunft"
    return RedirectResponse(f"/eid-sim/client/{sid}", status_code=303)


@router.post("/client/{sid}/auskunft")
async def client_auskunft(sid: str) -> RedirectResponse:
    sitzung = _sitzung(sid)
    sitzung.schritt = "pin"
    return RedirectResponse(f"/eid-sim/client/{sid}", status_code=303)


@router.post("/client/{sid}/pin")
async def client_pin(request: Request, sid: str, pin: str = Form("")) -> RedirectResponse:
    """PIN-Eingabe mit Fehlversuchszaehler.

    Der Zaehler ist der Grund, warum dieser Schritt existiert. Er bildet das
    Verhalten des echten Ausweises nach: drei Fehlversuche, dann ist die Karte
    gesperrt und nur noch mit der CAN von der Rueckseite zu entsperren. Die
    Simulation kann die CAN nicht anbieten - sie sagt stattdessen, dass es sie
    gibt, weil die Sperre sonst wie ein Defekt der Umfrage aussieht.
    """
    sitzung = _sitzung(sid)
    if sitzung.schritt == "gesperrt":
        raise Rejected("Der Ausweis ist gesperrt - diese Anmeldung ist beendet.")

    if pin.strip() != SIM_PIN:
        sitzung.versuche_offen -= 1
        if sitzung.versuche_offen <= 0:
            sitzung.schritt = "gesperrt"
            sitzung.ausweisnummer = None
            log_berechtigung.reject(
                "auth",
                "Ausweis nach drei Fehlversuchen gesperrt (Simulation).",
                poll=sitzung.poll_id,
            )
        else:
            log_berechtigung.reject(
                "auth",
                f"Falsche PIN (Simulation), {sitzung.versuche_offen} Versuche offen.",
                poll=sitzung.poll_id,
            )
        return RedirectResponse(f"/eid-sim/client/{sid}", status_code=303)

    return _abschliessen(request, sid, sitzung)


def _abschliessen(request: Request, sid: str, sitzung: Sitzung) -> RedirectResponse:
    """Rueckleitung: hier endet die Simulation und die echte App uebernimmt.

    Ab dieser Zeile passiert nichts Simuliertes mehr. Der Code geht an denselben
    Authenticator wie vorher im Modal, und das Ergebnis ist dieselbe signierte
    Sitzung - deshalb kennt der Rest der App diesen Umweg nicht.
    """
    d = web.deps(request)
    ausweisnummer = sitzung.ausweisnummer or ""
    # Die Sitzung faellt weg, bevor die Antwort gebaut wird: Was danach noch
    # gebraucht wird, sind poll_id und Pseudonym, nicht die Eingabe.
    _sitzungen.pop(sid, None)

    try:
        pseudonym = d.authenticator.authenticate(ausweisnummer)
    except AuthError as exc:
        # Im Ernstfall gaebe es diesen Fall so nicht - ein Chip, der die PIN
        # akzeptiert hat, liefert auch ein Pseudonym. Hier heisst er: der
        # Zugangscode steht nicht auf der Liste. Das gehoert an die Stelle
        # gesagt, an der es auffaellt, und nicht als stiller Rueckwurf.
        log_berechtigung.reject("auth", f"Anmeldung abgewiesen (Simulation): {exc}")
        ziel = f"/poll/{sitzung.poll_id}?eid_fehler={_quote(str(exc))}"
        return RedirectResponse(ziel, status_code=303)

    log_berechtigung.info("auth", f"Authentifiziert ueber: {d.authenticator.name}")
    antwort = _zurueck_zur_umfrage(sitzung.poll_id)
    antwort.set_cookie(
        web.SESSION_COOKIE,
        web._sign(request, pseudonym),
        httponly=True,
        samesite="lax",
        secure=d.settings.public,
    )
    return antwort


def _quote(text: str) -> str:
    from urllib.parse import quote

    return quote(text, safe="")


# ---------------------------------------------------------------------------
# Abbruch - an jeder Stelle
# ---------------------------------------------------------------------------


@router.post("/abbruch/{sid}")
async def abbruch(sid: str) -> RedirectResponse:
    """Abbrechen muss ueberall gehen und darf selbst nicht scheitern."""
    _aufraeumen()
    sitzung = _sitzungen.pop(sid, None)
    poll_id = sitzung.poll_id if sitzung else ""
    log_berechtigung.reject("auth", "eID-Anmeldung abgebrochen (Simulation).", poll=poll_id)
    return _zurueck_zur_umfrage(poll_id) if poll_id else RedirectResponse("/", status_code=303)
