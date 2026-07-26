"""Betriebsmodus: lokal auf dem eigenen Rechner oder oeffentlich im Netz.

Die App war bis hierher fuer genau eine Umgebung gebaut - localhost, ein
Bediener, Beenden-Knopf, Admin-Token "admin". Oeffentlich erreichbar gelten
andere Regeln, und sie duerfen nicht davon abhaengen, dass jemand beim Start an
die richtigen Schalter denkt. Deshalb stehen sie hier an einer Stelle und
haengen an einer einzigen Umgebungsvariable.

  EIDPOLL_PUBLIC=1   Die Instanz ist aus dem Netz erreichbar.

Was das aendert (jeweils begruendet an der Verwendungsstelle):
  - kein Beenden-Knopf, keine Shutdown-Route
  - Cookies nur ueber HTTPS
  - Fehlermeldungen ohne Innenleben nach aussen
  - Demo-Umfrage wird beim Start angelegt, damit die Instanz nie leer ist
"""

from __future__ import annotations

import os
import secrets

def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


PUBLIC = _flag("EIDPOLL_PUBLIC")

# Voreinstellung "admin" gab es, solange nur 127.0.0.1 zuhoerte. Im Netz waere
# ein Standardwert keine Zugangskontrolle, sondern eine oeffentliche Tuer - und
# ein Start, der einfach durchlaeuft, verdeckt genau das. Ohne gesetzte
# Variable wird deshalb ein zufaelliges Token erzeugt und einmal ins
# Startprotokoll geschrieben: nicht ratbar, und der Betreiber kommt ueber die
# Logs der Plattform trotzdem heran.
ADMIN_TOKEN = os.environ.get("EIDPOLL_ADMIN_TOKEN", "").strip()
ADMIN_TOKEN_GENERATED = not ADMIN_TOKEN
if ADMIN_TOKEN_GENERATED:
    ADMIN_TOKEN = secrets.token_urlsafe(12)

# Demo-Umfrage beim Start, wenn noch keine existiert. Auf Gratis-Hosting ohne
# persistente Platte ist die Datenbank nach jedem Neustart leer - ohne das hier
# stuende ein Besucher vor einer leeren Startseite und koennte nichts probieren.
SEED_DEMO = _flag("EIDPOLL_SEED_DEMO") or PUBLIC

SEED_POLL_ID = os.environ.get("EIDPOLL_SEED_POLL_ID", "demo")
SEED_QUESTION = os.environ.get(
    "EIDPOLL_SEED_QUESTION",
    "Sollte der Online-Ausweis fuer verbindliche Buergerbefragungen genutzt werden?",
)
SEED_OPTIONS = [
    o.strip()
    for o in os.environ.get("EIDPOLL_SEED_OPTIONS", "Ja,Nein,Unentschieden").split(",")
    if o.strip()
]


def startup_banner() -> list[str]:
    """Zeilen fuers Startprotokoll - das Admin-Token erscheint hier genau einmal."""
    lines = [f"Betriebsmodus: {'oeffentlich (EIDPOLL_PUBLIC=1)' if PUBLIC else 'lokal'}"]
    if ADMIN_TOKEN_GENERATED:
        lines.append(f"Admin-Token (zufaellig erzeugt, nur in diesem Log): {ADMIN_TOKEN}")
        lines.append("Dauerhaft setzen: EIDPOLL_ADMIN_TOKEN=<eigenes-token>")
    else:
        lines.append("Admin-Token: aus EIDPOLL_ADMIN_TOKEN uebernommen")
    return lines
