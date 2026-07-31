"""Sicherungskopie der Datenbank ohne Schluessel (EIP-T-067).

    python3 app/backup.py <ziel.sqlite3> [--db app/data/eidpoll.sqlite3]

Warum es dieses Skript gibt und nicht nur eine Regel: Die Backup-Regel aus
EIP-RPT-20260731-002 §3.3 sagt, wann eine Kopie existieren darf. Der bequeme
Weg, eine anzulegen, ist trotzdem ``cp -r data data.backup.$(date +%s)`` - und
genau so ist am 2026-07-31 eine Kopie entstanden, die ein vernichtetes
``server_secret`` weitertrug. Eine Regel, deren Befolgung umstaendlicher ist
als ihr Bruch, wird gebrochen. Deshalb ein Befehl, der kuerzer ist als das
Falsche und nebenbei nennt, was er entfernt hat.

Was das Skript nicht kann: die Kopie bewachen. Sie unterliegt weiter Regel 1
(kein Backup, das eine Schluesselvernichtung ueberleben kann) und Regel 3 (wer
eine anlegt, traegt sie ein oder loescht sie am selben Tag).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from store import Store  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("ziel", type=Path, help="Pfad der neuen Kopie (darf nicht existieren)")
    p.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).parent / "data" / "eidpoll.sqlite3",
        help="Quelldatenbank (Voreinstellung: app/data/eidpoll.sqlite3)",
    )
    args = p.parse_args(argv)

    if not args.db.exists():
        print(f"Quelldatenbank {args.db} gibt es nicht.", file=sys.stderr)
        return 1

    store = Store(args.db)
    try:
        entfernt = store.kopiere_ohne_geheimnisse(args.ziel)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Kopie geschrieben: {args.ziel}")
    print(f"Entfernte Konfigurationswerte ({len(entfernt)}):")
    for key in entfernt:
        print(f"  - {key}")
    if not entfernt:
        print("  (keine - die Datenbank fuehrte keine)")
    print(
        "\nDie Kopie traegt Ledger, Board und Batches, aber keinen Schluessel. "
        "Sie bleibt trotzdem der Backup-Regel unterworfen "
        "(EIP-RPT-20260731-002 §3.3): eintragen oder am selben Tag loeschen."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
