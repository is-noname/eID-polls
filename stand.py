"""Welcher Stand laeuft hier - und weicht er vom veroeffentlichten ab.

KODEX Paragraf 20 verlangt, dass der ausgelieferte Stand dem veroeffentlichten
entspricht. Bis EIP-T-074 hielt das allein Disziplin: Nichts stellte fest, ob
die oeffentliche Instanz denselben Stand zeigt wie origin/prototype. Verstoss
V-001 entstand genau so - Textkorrekturen galten als erledigt, lagen aber
uncommittet im Arbeitsbaum, waehrend die Instanz die falschen Aussagen
weiter anzeigte. Aufgefallen ist es nur, weil jemand von Hand nachgesehen hat.

Dieses Modul beantwortet die Frage, die dafuer zuerst beantwortbar sein muss:
**welchen Stand liefert diese Instanz aus?** Zwei Angaben, mit sehr
unterschiedlichem Gewicht:

  commit    Was der Hoster beim Ausrollen gesetzt hat (RENDER_GIT_COMMIT) oder
            der HEAD des Repos daneben. Eine Angabe ueber die Herkunft - sie
            sagt, woher der Stand kommen *soll*.
  treehash  Ein Hash ueber die Dateien, die tatsaechlich hier liegen. Keine
            Angabe, sondern eine Messung: er faellt auseinander, sobald eine
            ausgelieferte Datei von der veroeffentlichten abweicht, auch wenn
            der Commit unveraendert daneben steht.

Der treehash ist so definiert, dass ihn jemand ausserhalb des Projekts ohne
unser Werkzeug nachrechnen kann (Paragraf 20, letzter Satz) - im Klon des
Repos genuegt:

    LC_ALL=C sh -c 'git ls-files -z | sort -z | xargs -0 sha256sum | sha256sum'

``LC_ALL=C`` ist kein Zierat: Unter deutscher Locale sortiert ``sort`` Punkte
und Grossbuchstaben anders, und ``.gitignore`` landet an anderer Stelle als
hier - der Hash weicht dann ab, ohne dass eine Datei abweicht.

``AUSSCHLUSS`` bildet dafuer die .gitignore nach: Was hier vom Dateisystem
gelesen wird, ist genau die Menge der versionierten Dateien. Weicht das
auseinander - eine untrackte Datei im Arbeitsbaum -, ist das kein Schoenheits-
fehler, sondern der Fall aus V-001, und ``scripts/check_auslieferung.py``
meldet ihn getrennt.

**Die Grenze, weil sie nach Paragraf 4 mitzusagen ist.** Das hier ist die
Selbstauskunft des Servers, den man gerade pruefen will. Gegen ein Versehen
hilft sie, gegen einen Betreiber, der luegt, nicht: Wer den Code aendert, kann
auch diese Zeilen aendern. Dagegen hilft erst ein reproduzierbarer, von Dritten
nachgerechneter Build (EIP-T-007) - und vollstaendig auch der nicht.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent

# Bildet .gitignore nach. Bewusst hier verdoppelt und nicht aus der Datei
# gelesen: Der Container hat kein git, und eine Regel, die nur mit Werkzeug
# gilt, wuerde genau dort ausfallen, wo sie gebraucht wird. Dass beide Mengen
# uebereinstimmen, prueft check_auslieferung.py gegen `git ls-files`.
AUSSCHLUSS_ORDNER = {".git", "__pycache__", ".venv", "venv"}
AUSSCHLUSS_ENDUNGEN = (".pyc", ".pyo", ".pyd")

# Wie der Hash gebildet wird - als Text, damit die Antwort von /version ihre
# eigene Nachrechenvorschrift mitbringt.
VERFAHREN = (
    "sha256 ueber die Zeilen '<sha256 der Datei>  <Pfad>', nach Pfad sortiert, "
    "je Zeile mit \\n abgeschlossen"
)
NACHRECHNEN = (
    "im Klon des Repositorys: "
    "LC_ALL=C sh -c 'git ls-files -z | sort -z | xargs -0 sha256sum | sha256sum'"
)


def _ausgeschlossen(rel: Path) -> bool:
    """Ob ein relativer Pfad nicht zur Auslieferung gehoert (siehe .gitignore)."""
    for teil in rel.parts[:-1]:
        # data*/ statt data/: Sicherungskopien heissen data.backup.<zeit>
        # (EIP-T-041). Der Praefix trifft nur Ordner, nicht database.py.
        if teil in AUSSCHLUSS_ORDNER or teil.startswith("data"):
            return True
    name = rel.name
    return name.endswith(AUSSCHLUSS_ENDUNGEN) or ".sqlite3" in name


def dateien(basis: Path = BASE_DIR) -> list[Path]:
    """Die ausgelieferten Dateien, relativ zu ``basis``, nach Pfad sortiert."""
    gefunden = []
    for pfad in basis.rglob("*"):
        if not pfad.is_file():
            continue
        rel = pfad.relative_to(basis)
        if not _ausgeschlossen(rel):
            gefunden.append(rel)
    return sorted(gefunden, key=lambda p: p.as_posix())


def manifest(basis: Path = BASE_DIR) -> str:
    """Das Dateimanifest im Format von ``sha256sum`` - zwei Leerzeichen als Trenner."""
    zeilen = []
    for rel in dateien(basis):
        digest = hashlib.sha256((basis / rel).read_bytes()).hexdigest()
        zeilen.append(f"{digest}  {rel.as_posix()}\n")
    return "".join(zeilen)


def treehash(basis: Path = BASE_DIR) -> tuple[str, int]:
    """(Hash ueber das Manifest, Anzahl der Dateien)."""
    text = manifest(basis)
    return hashlib.sha256(text.encode()).hexdigest(), text.count("\n")


def _git(basis: Path, *args: str) -> str | None:
    """git-Aufruf im Ordner ``basis``; ``None``, wenn git oder Repo fehlen."""
    try:
        fertig = subprocess.run(
            ["git", "-C", str(basis), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if fertig.returncode != 0:
        return None
    return fertig.stdout.strip()


def commit(basis: Path = BASE_DIR) -> tuple[str, str]:
    """(Commit, woher die Angabe stammt).

    Die Reihenfolge ist die der Verlaesslichkeit von aussen: Was der Hoster
    beim Ausrollen gesetzt hat, steht ueber dem, was ein Repo daneben behauptet
    - im Container gibt es meist keins.
    """
    for name in ("RENDER_GIT_COMMIT", "EIDPOLL_COMMIT", "SOURCE_COMMIT", "GIT_COMMIT"):
        wert = os.environ.get(name, "").strip()
        if wert:
            return wert, name
    kopf = _git(basis, "rev-parse", "HEAD")
    if kopf:
        return kopf, "git rev-parse HEAD"
    return "unbekannt", "keine Quelle"


def stand(basis: Path = BASE_DIR) -> dict[str, Any]:
    """Was /version ausgibt - der Stand dieser Instanz, offen als Selbstauskunft."""
    hash_, anzahl = treehash(basis)
    kennung, quelle = commit(basis)
    return {
        "commit": kennung,
        "commit_quelle": quelle,
        "treehash": f"sha256:{hash_}",
        "dateien": anzahl,
        "verfahren": VERFAHREN,
        "nachrechnen": NACHRECHNEN,
        "repository": "https://github.com/is-noname/eID-polls (Branch prototype)",
        "grenze": (
            "Selbstauskunft dieser Instanz. Sie deckt ein Versehen auf, nicht einen "
            "Betreiber, der luegt - wer den Code aendert, kann auch diese Antwort "
            "aendern. Ein reproduzierbarer, von Dritten nachgerechneter Build steht "
            "aus (KODEX Paragraf 20, EIP-T-007)."
        ),
    }


# ---------------------------------------------------------------------------
# Abgleich: was hier liegt gegen das, was veroeffentlicht ist
# ---------------------------------------------------------------------------

BERICHT = BASE_DIR / "data" / "auslieferung.json"


@dataclass
class Abgleich:
    """Was ueber die Uebereinstimmung von Repository und Auslieferung bekannt ist."""

    befunde: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    stand: dict[str, Any] = field(default_factory=dict)
    bericht: dict[str, Any] | None = None


def lokale_abweichungen(basis: Path = BASE_DIR) -> tuple[list[str], list[str]]:
    """(Befunde, Hinweise) aus dem Repo neben der laufenden Instanz.

    Das ist der Fall aus V-001, und er ist der einzige, den eine Instanz allein
    feststellen kann: Liegt hier ein Repo, dann verraet es, ob der laufende Code
    Aenderungen enthaelt, die nie ausgeliefert wurden. Im Container gibt es kein
    Repo - dort bleibt die Liste leer, und die Frage beantwortet
    scripts/check_auslieferung.py von aussen.
    """
    befunde: list[str] = []
    hinweise: list[str] = []

    kopf = _git(basis, "rev-parse", "HEAD")
    if kopf is None:
        hinweise.append(
            "Kein Repository neben der Instanz - der Abgleich laeuft nur von aussen "
            "(scripts/check_auslieferung.py)"
        )
        return befunde, hinweise

    schmutzig = _git(basis, "status", "--porcelain")
    if schmutzig:
        anzahl = len(schmutzig.splitlines())
        befunde.append(
            f"Arbeitsbaum weicht vom Commit ab: {anzahl} Datei(en) geaendert oder "
            f"unversioniert. Genau so entstand V-001 - laufender Code, den niemand "
            f"ausgeliefert hat."
        )

    fern = _git(basis, "rev-parse", "origin/prototype")
    if fern is None:
        hinweise.append("origin/prototype ist hier nicht bekannt - noch kein Fetch?")
    elif fern != kopf:
        voraus = _git(basis, "rev-list", "--count", "origin/prototype..HEAD") or "?"
        zurueck = _git(basis, "rev-list", "--count", "HEAD..origin/prototype") or "?"
        befunde.append(
            f"HEAD ({kopf[:7]}) ist nicht origin/prototype ({fern[:7]}): "
            f"{voraus} Commit(s) nicht veroeffentlicht, {zurueck} nicht uebernommen."
        )
    return befunde, hinweise


def bericht_lesen(pfad: Path = BERICHT) -> dict[str, Any] | None:
    """Der letzte Bericht von scripts/check_auslieferung.py, falls vorhanden."""
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def abgleich(basis: Path = BASE_DIR, bericht_pfad: Path | None = None) -> Abgleich:
    """Alles, was ueber die Uebereinstimmung bekannt ist - fuer /debug.

    Bewusst zusammengefuehrt: Der lokale Teil (Repo daneben) und der aeussere
    Teil (Bericht des Pruefskripts) beantworten dieselbe Frage fuer
    verschiedene Strecken. Getrennt angezeigt saehe jede fuer sich harmlos aus.
    """
    befunde, hinweise = lokale_abweichungen(basis)
    eigener = stand(basis)
    bericht = bericht_lesen(bericht_pfad if bericht_pfad is not None else BERICHT)

    if bericht is None:
        hinweise.append(
            "Noch kein Abgleich gegen die oeffentliche Instanz gelaufen "
            "(python3 scripts/check_auslieferung.py)"
        )
    else:
        for zeile in bericht.get("befunde", []):
            befunde.append(f"Abgleich gegen die Instanz: {zeile}")
        geprueft = bericht.get("arbeitsbaum", {}).get("treehash")
        if geprueft and geprueft != eigener["treehash"]:
            hinweise.append(
                f"Der letzte Abgleich ({bericht.get('zeit', 'ohne Zeit')}) galt einem "
                f"anderen Stand als dem laufenden - er sagt ueber diesen hier nichts."
            )

    return Abgleich(befunde=befunde, hinweise=hinweise, stand=eigener, bericht=bericht)


_zuletzt_gemeldet: tuple[str, ...] | None = None


def melde(log: Any, basis: Path = BASE_DIR, bericht_pfad: Path | None = None) -> Abgleich:
    """Fuehrt den Abgleich und schreibt Abweichungen ins Debug-Modul.

    Gemeldet wird nur, was sich geaendert hat: Die Debug-Seite laedt sich alle
    drei Sekunden neu, und ein Befund, der dabei 500 Zeilen fuellt, verdraengt
    die Board-Inkonsistenzen aus dem Puffer - also genau das, wofuer er da ist.
    """
    global _zuletzt_gemeldet
    ergebnis = abgleich(basis, bericht_pfad)
    aktuell = tuple(ergebnis.befunde)
    if aktuell != _zuletzt_gemeldet:
        for zeile in ergebnis.befunde:
            log.inconsistency("auslieferung", zeile, treehash=ergebnis.stand["treehash"][:19])
        if _zuletzt_gemeldet and not aktuell:
            log.info("auslieferung", "Abweichung behoben: Auslieferung stimmt wieder ueberein")
        _zuletzt_gemeldet = aktuell
    return ergebnis
