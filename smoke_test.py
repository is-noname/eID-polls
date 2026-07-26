"""Ende-zu-Ende-Test der sieben Abnahmepunkte - ohne Browser.

Der Test spielt die Client-Seite mit blind.py nach. Damit ist der Server-Pfad
geprueft; ob die Browser-Krypto in static/blind.js bitgleich rechnet, zeigt erst
der echte Durchlauf im Browser (die PSS-Pruefung schlaegt sonst zu).

    python3 app/smoke_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DB = Path(tempfile.mkdtemp()) / "smoke.sqlite3"
os.environ["EIDPOLL_DB"] = str(DB)
os.environ["EIDPOLL_ADMIN_TOKEN"] = "admin"

import blind  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from web import app, service  # noqa: E402

POLL = "smoke"
OK, FAIL = "  ok  ", " FEHL "
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{OK if condition else FAIL}] {label}{(' - ' + detail) if detail else ''}")
    if not condition:
        failures.append(label)


def get_token(client: TestClient, poll: str = POLL) -> tuple[bytes, bytes] | None:
    """Phase A wie im Browser: lokal erzeugen, verblinden, entblinden."""
    import secrets

    token = secrets.token_bytes(32)
    blinded, inv = blind.blind(token, service.n, service.e)
    response = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
    if response.status_code != 200:
        return None
    sig = blind.finalize(bytes.fromhex(response.json()["blind_sig"]), inv, service.n)
    return token, sig


def parallel_participation(n: int = 10) -> None:
    """Nebenlaeufige Teilnahme (EIP-T-019).

    Bis hierhin lief immer nur eine Person durch den Flow. WAL und busy_timeout
    in store.py sind die Antwort auf parallele Schreiber - nachgewiesen war sie
    nicht. Jeder Thread bekommt einen eigenen TestClient, damit die Anfragen
    nicht ueber denselben Event-Loop serialisiert werden und die Schreibzugriffe
    tatsaechlich zusammenfallen.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from store import verify_chain

    poll = "parallel"
    admin = TestClient(app)
    admin.post("/api/admin/login", json={"token": "admin"})
    admin.post("/api/admin/create",
               json={"poll_id": poll, "question": "Gleichzeitig?", "options": ["Ja", "Nein"]})

    start = threading.Barrier(n)
    results: list[tuple[bool, str]] = []
    lock = threading.Lock()

    def participate(i: int) -> None:
        client = TestClient(app)
        client.post("/api/auth", json={"credential": f"testperson{i + 10}"})
        start.wait()  # alle Threads treffen den Server im selben Moment
        try:
            issued = get_token(client, poll)
            if issued is None:
                raise RuntimeError("Token-Abholung abgewiesen")
            token, sig = issued
            response = client.post(
                f"/api/vote/{poll}",
                json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja" if i % 2 else "Nein"]},
            )
            if response.status_code != 200:
                raise RuntimeError(str(response.json().get("error", response.status_code)))
            ok, detail = True, ""
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        with lock:
            results.append((ok, detail))

    with ThreadPoolExecutor(max_workers=n) as pool:
        list(pool.map(participate, range(n)))

    problems = [d for ok, d in results if not ok]
    check(f"Parallel: {n} gleichzeitige Teilnahmen ohne Fehler",
          not problems, "; ".join(problems[:3]))
    check("Parallel: kein 'database is locked'",
          not any("locked" in d for d in problems))

    # Das Board fuehrt beide Phasen: TOKEN_ISSUED und VOTE. Fuer die Stimmenzahl
    # zaehlen nur die VOTE-Eintraege, die Kette dagegen laeuft ueber alle.
    entries = service.board(poll)
    votes = [e for e in entries if '"type":"VOTE"' in e.payload.replace(" ", "")]
    check("Parallel: jede Stimme genau einmal im Board", len(votes) == n, f"{len(votes)} von {n}")
    issued = [e for e in entries if "TOKEN_ISSUED" in e.payload]
    check("Parallel: jede Token-Ausgabe genau einmal im Board",
          len(issued) == n, f"{len(issued)} von {n}")
    # Alles zusammen: der Eroeffnungseintrag der Umfrage plus beide Phasen.
    check("Parallel: keine zusaetzlichen Board-Eintraege",
          len(entries) == 1 + 2 * n, f"{len(entries)} statt {1 + 2 * n}")
    indices = [e.index for e in entries]
    check("Parallel: Board-Indizes lueckenlos und ohne Dopplung",
          indices == list(range(min(indices), min(indices) + len(indices))), str(indices))
    chain_ok, broken_at = verify_chain(entries)
    check("Parallel: Hash-Kette unter Nebenlaeufigkeit intakt", chain_ok, f"Bruch ab #{broken_at}")
    acc = service.accounting(poll)
    check("Parallel: Ledger-Abrechnung stimmt", acc.ok and acc.n_eligible == acc.n_votes == n,
          f"eligible={acc.n_eligible} votes={acc.n_votes}")
    check("Parallel: Konsistenzpruefung meldet nichts fuer diese Umfrage",
          not service.check_all().get(poll), str(service.check_all().get(poll)))

    from debug import log as debug_log

    phase_b = [e for e in debug_log.events("all") if e.detail.get("poll") == poll]
    check("Parallel: Debug-Modul hat jede Stimme erfasst, nichts verloren",
          len(phase_b) == n, f"{len(phase_b)} von {n}")


def main() -> int:
    client = TestClient(app)

    # Punkt 1 - App laeuft, offene Umfrage sichtbar
    client.post("/api/admin/login", json={"token": "admin"})
    created = client.post(
        "/api/admin/create",
        json={"poll_id": POLL, "question": "Testfrage?", "options": ["Ja", "Nein", "Weiss nicht"]},
    )
    check("Punkt 1: Umfrage anlegen und Startseite sehen",
          created.status_code == 200 and POLL in client.get("/").text)

    # Punkt 2 - Authentifizieren und Token holen (Phase A)
    client.post("/api/auth", json={"credential": "testperson1"})
    issued = get_token(client)
    check("Punkt 2: authentifiziert, Stimm-Token blind signiert", issued is not None)
    if issued is None:
        return 1
    token, sig = issued
    check("Punkt 2b: Signatur ist eine gueltige RSASSA-PSS-Signatur (RFC 9474)",
          blind.verify(service._key.public_key(), token, sig))

    # Phase A ein zweites Mal mit derselben Identitaet
    check("Punkt 2c: zweites Token fuer dieselbe Identitaet wird abgewiesen", get_token(client) is None)

    # Punkt 3 - Abstimmen, waehrenddessen nur Teilnahmezaehler
    voted = client.post(f"/api/vote/{POLL}", json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja"]})
    check("Punkt 3: Stimme abgegeben", voted.status_code == 200, str(voted.json())[:80])
    poll_page = client.get(f"/poll/{POLL}").text
    check("Punkt 3b: waehrend der Laufzeit keine Verteilung sichtbar",
          "1</span> Stimmen" in poll_page or ">1<" in poll_page)
    try:
        service.tally(POLL)
        check("Punkt 3c: Ergebnis vor Umfrage-Ende verweigert", False)
    except Exception as exc:
        check("Punkt 3c: Ergebnis vor Umfrage-Ende verweigert", "nach dem Ende" in str(exc), str(exc))

    # Punkt 4 - Verifikations-Beleg / Token-Lookup
    check("Punkt 4: eigenes Token im Board auffindbar", service.lookup(POLL, token.hex()) == ["Ja"])

    # Punkt 5 - zweiter Abstimmversuch
    replay = client.post(f"/api/vote/{POLL}", json={"token": token.hex(), "sig": sig.hex(), "choices": ["Nein"]})
    check("Punkt 5: Token-Replay abgewiesen", replay.status_code == 400, replay.json().get("error", ""))

    forged = client.post(
        f"/api/vote/{POLL}",
        json={"token": ("aa" * 32), "sig": sig.hex(), "choices": ["Nein"]},
    )
    check("Punkt 5b: Token ohne gueltige Signatur abgewiesen", forged.status_code == 400,
          forged.json().get("error", ""))

    # Zweite Person, damit das Ergebnis nicht trivial ist
    client.post("/api/auth", json={"credential": "testperson2"})
    second = get_token(client)
    if second:
        client.post(f"/api/vote/{POLL}",
                    json={"token": second[0].hex(), "sig": second[1].hex(), "choices": ["Nein", "Weiss nicht"]})

    # Punkt 6 - schliessen, Ergebnis, Token wiederfinden
    closed = client.post(f"/api/admin/close/{POLL}")
    result = service.tally(POLL)
    check("Punkt 6: geschlossen und Ergebnis aus dem Board",
          closed.status_code == 200 and result == {"Ja": 1, "Nein": 1, "Weiss nicht": 1}, str(result))
    check("Punkt 6b: eigenes Token im geschlossenen Board wiederfindbar",
          service.lookup(POLL, token.hex()) == ["Ja"])

    # Punkt 7 - Abrechnung und Kettenpruefung als oeffentliche Seite
    board_page = client.get(f"/board/{POLL}")
    accounting = service.accounting(POLL)
    status = service.chain_status(POLL)
    check("Punkt 7: Board-Seite mit Abrechnung und Kettenpruefung",
          board_page.status_code == 200 and accounting.ok and status.sound,
          f"eligible={accounting.n_eligible} votes={accounting.n_votes} kette={status.ok}")

    parallel_participation()

    # Angriff 1 - Ballot-Stuffing wird von der Abrechnung entlarvt
    open_poll = "stuffdemo"
    client.post("/api/admin/create",
                json={"poll_id": open_poll, "question": "Demo?", "options": ["Ja", "Nein"]})
    service.demo_stuff_ballot(open_poll, "Ja")
    acc = service.accounting(open_poll)
    check("Angriff Ballot-Stuffing: Abrechnung schlaegt aus",
          not acc.ok, f"{acc.n_votes} Stimmen bei {acc.n_eligible} Berechtigten")

    # Angriff 2 - Board umschreiben bricht die Kette und verhindert das Ergebnis
    vote_index = next(e.index for e in service.board(POLL) if e.kind == "VOTE")
    service.demo_tamper_board(POLL, vote_index, "Nein")
    status = service.chain_status(POLL)
    check("Angriff Board-Manipulation: Kette bricht sichtbar", not status.ok, f"ab #{status.broken_at}")
    try:
        service.tally(POLL)
        check("Angriff Board-Manipulation: kein Ergebnis mehr", False)
    except Exception as exc:
        check("Angriff Board-Manipulation: kein Ergebnis mehr", "gebrochen" in str(exc), str(exc))

    # Debug-Modul hat alles mitbekommen
    from debug import log

    counts = log.counts()
    check("Debug-Modul: Abweisungen und Inkonsistenzen erfasst",
          counts["reject"] >= 3 and counts["inconsistency"] >= 2, str(counts))

    # Betreiber-Bereiche sind nicht oeffentlich (EIP-T-018). Das Debug-Log stellt
    # Phase A und Phase B mit Zeitstempel nebeneinander - offen abrufbar waere es
    # die Zuordnung Person -> Stimme.
    anon = TestClient(app)
    debug_anon = anon.get("/debug")
    check("Zugang: /debug ohne Anmeldung abgewiesen",
          debug_anon.status_code == 403 and "vorbehalten" in debug_anon.text,
          f"status={debug_anon.status_code}")
    check("Zugang: /debug liefert keine Ereignisse an Unangemeldete",
          "phase-a" not in debug_anon.text and "phase-b" not in debug_anon.text)
    clear_anon = anon.post("/api/debug/clear")
    check("Zugang: Debug-Log kann nicht anonym geleert werden",
          clear_anon.status_code == 400, f"status={clear_anon.status_code}")
    # Die Abweisung selbst wird geloggt, reject steigt also - entscheidend ist,
    # dass nichts geloescht wurde.
    check("Zugang: Log nach abgewiesenem Leeren nicht geleert",
          log.counts()["info"] == counts["info"] and log.counts()["reject"] > counts["reject"])
    admin_anon = anon.get("/admin")
    check("Zugang: /admin ohne Anmeldung zeigt nur die Anmeldung",
          "login-button" in admin_anon.text and "Angriffsdemos" not in admin_anon.text)
    check("Zugang: /admin nennt Unangemeldeten die Token-Voreinstellung nicht",
          "Voreinstellung" not in admin_anon.text)
    check("Zugang: /debug fuer den angemeldeten Betreiber erreichbar",
          client.get("/debug").status_code == 200)
    # TestClient gilt nicht als lokal (client.host == "testclient"), entspricht also
    # einem fremden Geraet im Netz - dort darf keine Betreiber-Navigation stehen.
    nav_anon = anon.get("/")
    check("Zugang: fremdes Geraet sieht keine Betreiber-Navigation",
          'href="/debug"' not in nav_anon.text and 'href="/admin"' not in nav_anon.text)
    check("Zugang: fremdes Geraet sieht keinen Beenden-Knopf",
          'id="quit-button"' not in nav_anon.text)
    check("Wahlgeheimnis: kein voter_key im Debug-Log",
          not any("voter_key" in str(e.detail) for e in log.events("all")))

    print()
    if failures:
        print(f"{len(failures)} Prueffall/Prueffaelle fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("Alle Pruefungen bestanden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
