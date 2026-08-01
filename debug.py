"""Debug-Modul - Echtzeitsicht auf Fehler, Abweisungen und Dateninkonsistenzen.

Bei diesem Projekt ist das kein Komfort. Die Sicherheitsaussagen aus
EIP-RFC-20260725-001 §9 halten nur, solange zwei Dinge sichtbar werden:
gebrochene Board-Ketten und eine Ledger-Abrechnung, die nicht aufgeht. Genau
diese beiden Faelle landen hier als `inconsistency` - zusammen mit jeder
regelkonformen Abweisung (`reject`) und jedem unerwarteten Fehler (`error`).

Der Puffer liegt im Prozessspeicher und ueberlebt keinen Neustart. Das ist
gewollt: er ist ein Beobachtungsfenster, keine zweite Wahrheit neben Board und
Ledger.

**Teilnahmevorgaenge stehen nicht im Ereignisstrom** (EIP-T-041, KODEX §1/§2).
Ein Strom mit Sekundenstempel stellt "Token ausgegeben, 16:00:03" und "Stimme
gepuffert, 16:00:41" nebeneinander - bei duennem Verkehr ist das die Zuordnung
Berechtigung -> Stimme, also genau die Verkettung, die das Verfahren verhindern
soll, nur mit Weboberflaeche davor. Deshalb werden Ereignisse der Kategorien in
``TEILNAHME`` nicht einzeln gepuffert, sondern **je Stunde gezaehlt**: kein
Sekundenstempel, keine Reihenfolge, nur "in Stunde 16 gab es n davon".

Die Grenze dieser Massnahme, weil sie nach KODEX §4 mitzusagen ist: Wer in
seiner Stunde allein teilnimmt, ist ueber die Stunde weiter zuzuordnen. Das ist
dieselbe Grenze wie bei der Batch-Granularitaet (ADR E3) - die Anonymitaetsmenge
macht die Zusage, nicht die Rundung.

Ausgenommen bleiben ``error`` und ``inconsistency``: Ein Fehler ist ein *nicht*
zustandegekommener Vorgang und verkettet nichts, was das Board zeigt, und eine
gemeldete Inkonsistenz zeigt eine Verkettung an, die bereits passiert ist - die
muss genau und sofort auffindbar sein, sonst meldet sie nichts.

**Drei getrennte Logs statt einem** (EIP-T-033, Baustein G): ``log_berechtigung``
haelt die Berechtigungsseite (eID-Anmeldung, Token-Ausgabe, Umfrage-Schluessel),
``log_board`` die Board-Seite (Stimmabgabe, Batches, Beleg-Schluessel), ``log``
den Betrieb (Anlegen/Schliessen, System, Konsistenzpruefung). Die Trennlinie ist
dieselbe wie bei den Datenbanken: Kein einzelnes Log haelt beide Phasen, und wer
beide Seiten nebeneinander sehen will, muss sie ausdruecklich zusammenfuehren
(/debug tut das - als bewusste Betreiberhandlung, nicht als Datenlage). Die
Konsistenzpruefung bleibt im Betriebs-Log: Sie *ist* der bewusste Blick ueber
die Linie und gehoert keiner Seite.
"""

from __future__ import annotations

import threading
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Level = Literal["info", "reject", "error", "inconsistency"]

MAX_EVENTS = 500

# Kategorien, deren Eintreten an einer einzelnen Teilnahmehandlung haengt.
TEILNAHME = frozenset({"auth", "phase-a", "phase-b"})

# Pfad-Praefix -> Kategorie. Die Fehlerbehandlung in web.py sieht nur den Pfad,
# nicht die Phase; ohne diese Zuordnung landeten Abweisungen aus Phase A und B
# mit Sekundenstempel im Strom und truegen die Korrelation, die der Umbau
# entfernt.
_PFAD_KATEGORIE = (
    ("/api/token/", "phase-a"),
    ("/api/vote/", "phase-b"),
    ("/api/auth", "auth"),
)


def kategorie_fuer_pfad(pfad: str, default: str) -> str:
    """Die Teilnahme-Kategorie eines Requestpfads, sonst ``default``."""
    for praefix, kategorie in _PFAD_KATEGORIE:
        if pfad.startswith(praefix):
            return kategorie
    return default


@dataclass
class Event:
    ts: str
    level: Level
    category: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Zaehlstand:
    """Ein teilnahmebezogener Vorgang, gezaehlt statt gestromt."""

    stunde: str
    level: Level
    category: str
    message: str
    detail: dict[str, Any]
    anzahl: int


class DebugLog:
    def __init__(self, name: str = "betrieb", maxlen: int = MAX_EVENTS) -> None:
        self.name = name
        self._events: deque[Event] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {"info": 0, "reject": 0, "error": 0, "inconsistency": 0}
        # Schluessel: (Stunde, Level, Kategorie, Meldung, Detail als Paare).
        # Das Detail gehoert in den Schluessel, damit sich Vorgaenge
        # verschiedener Umfragen nicht zu einer Zahl vermischen.
        self._teilnahme: dict[tuple[Any, ...], int] = {}

    def log(self, level: Level, category: str, message: str, **detail: Any) -> None:
        jetzt = datetime.now()
        if category in TEILNAHME and level in ("info", "reject"):
            schluessel = (
                jetzt.strftime("%H:00"),
                level,
                category,
                message,
                tuple(sorted((k, str(v)) for k, v in detail.items())),
            )
            with self._lock:
                self._teilnahme[schluessel] = self._teilnahme.get(schluessel, 0) + 1
                self._counts[level] += 1
            return
        event = Event(
            ts=jetzt.strftime("%H:%M:%S"),
            level=level,
            category=category,
            message=message,
            detail=detail,
        )
        with self._lock:
            self._events.appendleft(event)
            self._counts[level] += 1

    def info(self, category: str, message: str, **detail: Any) -> None:
        self.log("info", category, message, **detail)

    def reject(self, category: str, message: str, **detail: Any) -> None:
        self.log("reject", category, message, **detail)

    def error(self, category: str, message: str, **detail: Any) -> None:
        self.log("error", category, message, **detail)

    def inconsistency(self, category: str, message: str, **detail: Any) -> None:
        self.log("inconsistency", category, message, **detail)

    def exception(self, category: str, exc: BaseException) -> None:
        self.log(
            "error",
            category,
            f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(limit=6),
        )

    def events(self, level: str | None = None) -> list[Event]:
        with self._lock:
            events = list(self._events)
        if level and level != "all":
            events = [e for e in events if e.level == level]
        return events

    def teilnahme(self) -> list[Zaehlstand]:
        """Die gezaehlten Teilnahmevorgaenge, sortiert nach Stunde und Kategorie.

        Sortiert wird bewusst **nicht** nach Eintragungszeit: Die Reihenfolge des
        ``dict`` waere die Eingangsreihenfolge und damit wieder die Korrelation,
        die das Zaehlen entfernt.
        """
        with self._lock:
            eintraege = list(self._teilnahme.items())
        staende = [
            Zaehlstand(
                stunde=k[0],
                level=k[1],
                category=k[2],
                message=k[3],
                detail=dict(k[4]),
                anzahl=n,
            )
            for k, n in eintraege
        ]
        staende.sort(key=lambda z: (z.stunde, z.category, z.level, z.message))
        return staende

    def counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._teilnahme.clear()
            self._counts = {k: 0 for k in self._counts}


log = DebugLog("betrieb")
log_berechtigung = DebugLog("berechtigung")
log_board = DebugLog("board")

# Kategorie -> Log. Was hier nicht steht, ist Betrieb. Die Zuordnung folgt der
# Speicher-Trennlinie (Baustein G): Berechtigungsseite kennt das Pseudonym,
# Board-Seite Token und Stimme - und die Logs entsprechend.
_KATEGORIE_LOG = {
    "auth": "berechtigung",
    "phase-a": "berechtigung",
    "phase-b": "board",
    "batch": "board",
    "unverkettbarkeit": "board",
    "verifikation": "board",
}


def log_fuer(kategorie: str) -> DebugLog:
    """Das Log der Seite, zu der eine Kategorie gehoert."""
    return {"berechtigung": log_berechtigung, "board": log_board}.get(
        _KATEGORIE_LOG.get(kategorie, "betrieb"), log
    )


ALLE_LOGS = (log, log_berechtigung, log_board)


def events_gesamt(level: str | None = None) -> list[Event]:
    """Alle drei Logs in einer Sicht - der bewusste Blick ueber die Trennlinie.

    Sortiert nach Uhrzeit (absteigend wie die Einzel-Logs). Die Zusammenfuehrung
    passiert erst hier, beim Anzeigen: gehalten werden die Ereignisse getrennt.
    """
    zusammen = [e for l in ALLE_LOGS for e in l.events(level)]
    zusammen.sort(key=lambda e: e.ts, reverse=True)
    return zusammen


def teilnahme_gesamt() -> list[Zaehlstand]:
    staende = [z for l in ALLE_LOGS for z in l.teilnahme()]
    staende.sort(key=lambda z: (z.stunde, z.category, z.level, z.message))
    return staende


def counts_gesamt() -> dict[str, int]:
    gesamt: dict[str, int] = {"info": 0, "reject": 0, "error": 0, "inconsistency": 0}
    for l in ALLE_LOGS:
        for k, v in l.counts().items():
            gesamt[k] += v
    return gesamt


def clear_alle() -> None:
    for l in ALLE_LOGS:
        l.clear()
