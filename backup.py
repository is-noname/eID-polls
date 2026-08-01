"""Sicherungskopie der Datenbanken ohne Schluessel (EIP-T-067).

    python3 app/backup.py <zielverzeichnis> [--db app/data/eidpoll.sqlite3]

Warum es dieses Skript gibt und nicht nur eine Regel: Die Backup-Regel aus
EIP-RPT-20260731-002 §3.3 sagt, wann eine Kopie existieren darf. Der bequeme
Weg, eine anzulegen, ist trotzdem ``cp -r data data.backup.$(date +%s)`` - und
genau so ist am 2026-07-31 eine Kopie entstanden, die ein vernichtetes
``server_secret`` weitertrug. Eine Regel, deren Befolgung umstaendlicher ist
als ihr Bruch, wird gebrochen. Deshalb ein Befehl, der kuerzer ist als das
Falsche und nebenbei nennt, was er entfernt hat.

Seit der Speicher-Trennung (EIP-T-033, Baustein G) sind es **zwei Dateien**:
die Board-Datenbank (--db) und die Berechtigungs-Datenbank daneben. Beide
werden ohne ihre Schluessel kopiert; das Ziel ist deshalb ein Verzeichnis,
keine Datei - eine halbe Sicherung (nur eine der beiden) waere sonst der
naechste stille Sonderfall.

Was das Skript nicht kann: die Kopie bewachen. Sie unterliegt weiter Regel 1
(kein Backup, das eine Schluesselvernichtung ueberleben kann) und Regel 3 (wer
eine anlegt, traegt sie ein oder loescht sie am selben Tag).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from berechtigung_store import BerechtigungsStore  # noqa: E402
from poll_service import berechtigungs_pfad  # noqa: E402
from store import Store  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "ziel", type=Path, help="Zielverzeichnis der Kopien (Dateien darin duerfen nicht existieren)"
    )
    p.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).parent / "data" / "eidpoll.sqlite3",
        help="Board-Datenbank (Voreinstellung: app/data/eidpoll.sqlite3); die "
        "Berechtigungs-Datenbank liegt daneben und wird mitgesichert",
    )
    args = p.parse_args(argv)

    quellen = [
        ("Board", Store, args.db),
        ("Berechtigung", BerechtigungsStore, berechtigungs_pfad(args.db)),
    ]
    fehlend = [pfad for _, _, pfad in quellen if not pfad.exists()]
    if fehlend:
        for pfad in fehlend:
            print(f"Quelldatenbank {pfad} gibt es nicht.", file=sys.stderr)
        return 1

    for name, klasse, pfad in quellen:
        ziel = args.ziel / pfad.name
        try:
            entfernt = klasse(pfad).kopiere_ohne_geheimnisse(ziel)
        except FileExistsError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"{name}-Kopie geschrieben: {ziel}")
        print(f"  entfernte Konfigurationswerte ({len(entfernt)}):")
        for key in entfernt:
            print(f"    - {key}")
        if not entfernt:
            print("    (keine - die Datenbank fuehrte keine)")

    print(
        "\nDie Kopien tragen Ledger, Board und Batches, aber keinen Schluessel. "
        "Sie bleiben trotzdem der Backup-Regel unterworfen "
        "(EIP-RPT-20260731-002 §3.3): eintragen oder am selben Tag loeschen."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
