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
  - Angriffsdemos (demo.py) sind nicht verdrahtet, ausser EIDPOLL_DEMOS=1

Gelesen wird die Umgebung nur in ``Settings.from_env()``. Ueberall sonst reicht
ein ``Settings``-Objekt herum (EIP-T-048): Ein Test, der eine oeffentliche
Instanz pruefen will, baut sie sich, statt vor dem Import an os.environ zu
drehen - und beim Import dieses Moduls entsteht kein Zufallstoken als
Nebenwirkung.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field

DEFAULT_QUESTION = "Sollte der Online-Ausweis fuer verbindliche Buergerbefragungen genutzt werden?"


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Alles, was der Betriebsmodus an der App verstellt."""

    public: bool = False
    admin_token: str = "admin"
    # Ob das Token erzeugt wurde, entscheidet nur ueber das Startprotokoll -
    # ein uebergebenes Token gehoert dort nicht hinein.
    admin_token_generated: bool = False
    # Angriffsdemos aus demo.py (§9): Board umschreiben, Stimme einschleusen,
    # Testzugang zuruecksetzen. Lokal an - dort ist das Ausprobieren der Zweck.
    # Oeffentlich aus, solange es niemand ausdruecklich einschaltet: Wer das
    # Admin-Token hat, koennte sonst das Board einer erreichbaren Instanz
    # zerschreiben. Die Vorfuehrinstanz setzt EIDPOLL_DEMOS=1 (DEPLOY.md).
    #
    # ``None`` heisst "wie der Betriebsmodus es will" und wird unten aufgeloest.
    # Ein fester Vorgabewert waere hier die falsche Sicherung: Eine oeffentliche
    # Instanz, die jemand direkt zusammenbaut (Tests, eigener Einstiegspunkt),
    # haette die Demos sonst still an.
    demos: bool | None = None
    # Batch-Veroeffentlichung (EIP-ADR-20260728-001, E3): Mindestmenge k und
    # Zeitdeckel. Beide Werte sind nach aussen zu nennen - wer einen Beleg
    # bekommt, muss wissen, wovon die Sichtbarkeit abhaengt.
    #
    # ``batch_k`` zaehlt seit EIP-T-076 **Stimmen** im Puffer, nicht Eintraege.
    # Vorher war es die Eintragszahl, und weil jede Teilnahme zwei Eintraege
    # erzeugt, war die zugesagte Menge in Wahrheit rund die Haelfte
    # (EIP-RPT-20260731-001). 10 heisst jetzt 10 Stimmen.
    batch_k: int = 10
    batch_deckel_h: float = 6.0
    # Externe Anker auf batch_root(n) (EIP-ADR-20260801-002). Standardmaessig
    # an: Eine oeffentlich erreichbare Instanz ohne Anker kann rueckwirkendes
    # Umschreiben nicht ausschliessen, und das ist Betriebsstufe 2 (KODEX §2).
    # EIDPOLL_ANKER=0 schaltet ab - fuer Tests und fuer den Betrieb ohne
    # ausgehende Netzverbindung. Abgeschaltet ist ein zulaessiger Zustand, aber
    # ein sichtbarer: Die Board-Seite sagt dann, dass keine Root datiert ist.
    anker: bool = True
    anker_frist_h: float = 1.0
    anker_upgrade_h: float = 24.0
    anker_toleranz_min: float = 15.0
    # Mindest-Antwortzeit der Phasen-Routen /api/token und /api/vote in
    # Sekunden (EIP-T-033, Baustein F): Beide Routen antworten fruehestens nach
    # dieser Zeit, damit die Bearbeitungsdauer nicht zum Seitenkanal wird
    # (schnelle Abweisung vs. langsame Signatur). Ein Floor, keine Konstante:
    # dauert die Bearbeitung laenger, wird nicht gekappt. 0 schaltet ab (Tests).
    antwort_floor_s: float = 0.3
    # Lebensdauer des Wiederhol-Puffers der Token-Ausgabe in Stunden
    # (EIP-T-070). Innerhalb dieser Zeit bekommt eine unveraendert wiederholte
    # verblindete Anfrage dieselbe Blindsignatur noch einmal - der Fall
    # "signiert, Antwort verloren, Berechtigung verbrannt".
    #
    # Warum 24 Stunden und nicht die Umfrage-Laufzeit: Der Puffer verbindet
    # voter_key mit einer verblindeten Anfrage. Das ist keine Zuordnung zur
    # Stimme, aber es ist mehr, als der Ledger danach noch braucht - und die
    # Umfrage-Laufzeit ist nach oben offen. Ein Tag deckt den Fall ab, um den es
    # geht (Abbruch, spaeter derselbe Browser), und laesst den Rest verfallen.
    # 0 schaltet den Puffer ab; dann gilt wieder "Anspruch weg, Token weg".
    retry_cache_h: float = 24.0
    # Nenner der Beteiligungsquote (EIP-T-025): Deutsche ab 18 im Inland,
    # Schaetzung der Bundeswahlleiterin zur Bundestagswahl 2025. Amtlich,
    # registerbasiert, datiert - und zu jeder Bundestagswahl neu festgestellt.
    #
    # Warum nicht "alle Ausweisinhaber", wie das Konzept es zuerst vorsah: Diese
    # Zahl gibt es nicht. Das BMI hat auf IFG-Anfrage bestaetigt, dass keine
    # zentrale Statistik ueber gueltige Personalausweise gefuehrt wird - die
    # Daten liegen bei rund 5.500 Ausweisbehoerden, Umlauf und Gueltigkeit sind
    # unbekannt. Ein Nenner, den niemand nachschlagen kann, ist keiner.
    #
    # Der Wert steht hier und nicht im Template, weil er vorab und dauerhaft
    # festgelegt sein muss: ein nachtraeglich passend gewaehlter Nenner waere
    # genau der Methodentrick, gegen den sich dieses Projekt richtet.
    nenner: int = 59_200_000
    nenner_bezeichnung: str = "Wahlberechtigte (Deutsche ab 18 im Inland)"
    nenner_quelle: str = "Bundeswahlleiterin, Schaetzung zur Bundestagswahl 2025 (Stand 2024-12-04)"
    nenner_quelle_url: str = (
        "https://www.bundeswahlleiterin.de/mitteilungen/bundestagswahlen/2025/"
        "20241204_btw25_schaetzung-wahlberechtigte.html"
    )
    seed_demo: bool = False
    seed_poll_id: str = "demo"
    seed_question: str = DEFAULT_QUESTION
    seed_options: list[str] = field(default_factory=lambda: ["Ja", "Nein", "Enthaltung"])

    def __post_init__(self) -> None:
        if self.demos is None:
            # frozen=True: der einzige Weg, den aufgeloesten Wert zu setzen.
            object.__setattr__(self, "demos", not self.public)

    @classmethod
    def from_env(cls) -> "Settings":
        public = _flag("EIDPOLL_PUBLIC")

        # Voreinstellung "admin" gab es, solange nur 127.0.0.1 zuhoerte. Im Netz
        # waere ein Standardwert keine Zugangskontrolle, sondern eine
        # oeffentliche Tuer - und ein Start, der einfach durchlaeuft, verdeckt
        # genau das. Ohne gesetzte Variable wird deshalb ein zufaelliges Token
        # erzeugt und einmal ins Startprotokoll geschrieben: nicht ratbar, und
        # der Betreiber kommt ueber die Logs der Plattform trotzdem heran.
        admin_token = os.environ.get("EIDPOLL_ADMIN_TOKEN", "").strip()
        generated = not admin_token
        if generated:
            admin_token = secrets.token_urlsafe(12)

        return cls(
            public=public,
            admin_token=admin_token,
            admin_token_generated=generated,
            demos=True if _flag("EIDPOLL_DEMOS") else None,
            batch_k=int(os.environ.get("EIDPOLL_BATCH_K", "10") or 10),
            batch_deckel_h=float(os.environ.get("EIDPOLL_BATCH_DECKEL_H", "6") or 6),
            antwort_floor_s=float(os.environ.get("EIDPOLL_ANTWORT_FLOOR_S", "0.3") or 0.3),
            anker=os.environ.get("EIDPOLL_ANKER", "1").strip() not in {"0", "false", "no", "off"},
            anker_frist_h=float(os.environ.get("EIDPOLL_ANKER_FRIST_H", "1") or 1),
            anker_upgrade_h=float(os.environ.get("EIDPOLL_ANKER_UPGRADE_H", "24") or 24),
            anker_toleranz_min=float(os.environ.get("EIDPOLL_ANKER_TOLERANZ_MIN", "15") or 15),
            retry_cache_h=float(os.environ.get("EIDPOLL_RETRY_CACHE_H", "24") or 24),
            nenner=int(os.environ.get("EIDPOLL_NENNER", "") or 59_200_000),
            # Demo-Umfrage beim Start, wenn noch keine existiert. Auf
            # Gratis-Hosting ohne persistente Platte ist die Datenbank nach
            # jedem Neustart leer - ohne das hier stuende ein Besucher vor einer
            # leeren Startseite und koennte nichts probieren.
            seed_demo=_flag("EIDPOLL_SEED_DEMO") or public,
            seed_poll_id=os.environ.get("EIDPOLL_SEED_POLL_ID", "demo"),
            seed_question=os.environ.get("EIDPOLL_SEED_QUESTION", DEFAULT_QUESTION),
            seed_options=[
                o.strip()
                for o in os.environ.get("EIDPOLL_SEED_OPTIONS", "Ja,Nein,Enthaltung").split(",")
                if o.strip()
            ],
        )

    def startup_banner(self) -> list[str]:
        """Zeilen fuers Startprotokoll - das Admin-Token erscheint hier genau einmal."""
        lines = [f"Betriebsmodus: {'oeffentlich (EIDPOLL_PUBLIC=1)' if self.public else 'lokal'}"]
        if self.admin_token_generated:
            lines.append(f"Admin-Token (zufaellig erzeugt, nur in diesem Log): {self.admin_token}")
            lines.append("Dauerhaft setzen: EIDPOLL_ADMIN_TOKEN=<eigenes-token>")
        else:
            lines.append("Admin-Token: aus EIDPOLL_ADMIN_TOKEN uebernommen")
        lines.append(
            "Angriffsdemos (§9): " + ("verdrahtet" if self.demos else "nicht verdrahtet")
        )
        lines.append(
            f"Batch-Veroeffentlichung: k={self.batch_k} Stimmen, Zeitdeckel "
            f"{self.batch_deckel_h} h (EIP-ADR-20260728-001, EIP-T-076)"
        )
        lines.append(
            "Externe Anker auf die Batch-Root: "
            + (
                "RFC 3161 + OpenTimestamps (EIP-ADR-20260801-002)"
                if self.anker
                else "abgeschaltet (EIDPOLL_ANKER=0) - keine Root ist von aussen datiert"
            )
        )
        lines.append(
            "Wiederhol-Puffer der Token-Ausgabe: "
            + (f"{self.retry_cache_h} h" if self.retry_cache_h > 0 else "abgeschaltet")
            + " (EIP-T-070)"
        )
        lines.append(
            f"Nenner der Beteiligungsquote: {self.nenner:,} ".replace(",", ".")
            + f"{self.nenner_bezeichnung} - {self.nenner_quelle} (EIP-T-025)"
        )
        return lines
