"""Ende-zu-Ende-Test der sieben Abnahmepunkte - ohne Browser.

Der Test spielt die Client-Seite mit blind.py nach. Damit ist der Server-Pfad
geprueft; ob die Browser-Krypto in static/blind.js bitgleich rechnet, zeigt erst
der echte Durchlauf im Browser (die PSS-Pruefung schlaegt sonst zu).

    python3 app/smoke_test.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import blind  # noqa: E402
import demo  # noqa: E402
import anker as anker_modul  # noqa: E402
from debug import DebugLog, log_board  # noqa: E402
from config import Settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from web import create_app  # noqa: E402

# Eigene Instanz statt Umgebungsvariablen vor dem Import (EIP-T-048): Datenbank,
# Betriebsmodus und Admin-Token stehen hier sichtbar, und der Test kann sich
# eine zweite Instanz mit anderen Einstellungen bauen, ohne den Import zu
# beeinflussen.
#
# batch_k=1: jeder Eintrag wird sofort als eigener Batch veroeffentlicht, damit
# die Ablauf-Pruefungen das Board direkt lesen koennen. Das Puffer-Verhalten
# selbst (k>1, Beleg, Veroeffentlichung beim Schliessen) prueft
# batch_veroeffentlichung() an einer eigenen Instanz.
#
# antwort_floor_s=0: Der Antwort-Floor der Phasen-Routen (EIP-T-033, Baustein F)
# wuerde jeden Token- und Vote-Aufruf kuenstlich verlaengern. Geprueft wird er
# gezielt in sitzungstrennung(), an einer eigenen Instanz.
DB = Path(tempfile.mkdtemp()) / "smoke.sqlite3"
app = create_app(store_path=DB, settings=Settings(admin_token="admin", batch_k=1, antwort_floor_s=0))
service = app.state.deps.service

POLL = "smoke"
OK, FAIL = "  ok  ", " FEHL "
failures: list[str] = []

# Irgendein gueltiges oeffentliches PEM fuer die Formatpruefungen: POLL_OPEN
# traegt seit EIP-T-069 den Token-Schluessel der Umfrage, und der Parser
# verlangt ihn. Fuer eintragsformat() zaehlt nur, dass es ein PEM ist.
_PUBKEY_PEM = (
    "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAK\n"
    "-----END PUBLIC KEY-----\n"
)


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{OK if condition else FAIL}] {label}{(' - ' + detail) if detail else ''}")
    if not condition:
        failures.append(label)


def get_token(client: TestClient, poll: str = POLL) -> tuple[bytes, bytes] | None:
    """Phase A wie im Browser: lokal erzeugen, verblinden, entblinden."""
    import secrets

    token = secrets.token_bytes(32)
    n, e = service.poll_params(poll)
    blinded, inv = blind.blind(token, n, e)
    response = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
    if response.status_code != 200:
        return None
    sig = blind.finalize(bytes.fromhex(response.json()["blind_sig"]), inv, n)
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
    from verifikation import verify_batches

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
    votes = [e for e in entries if e.kind == "VOTE"]
    check("Parallel: jede Stimme genau einmal im Board", len(votes) == n, f"{len(votes)} von {n}")
    issued = [e for e in entries if e.kind == "TOKEN_ISSUED"]
    check("Parallel: jede Token-Ausgabe genau einmal im Board",
          len(issued) == n, f"{len(issued)} von {n}")
    # Der Nonce kommt aus demselben Schritt wie der Anspruch selbst (EIP-T-047,
    # ADR E2). Bei gleichzeitiger Ausgabe muessen trotzdem alle Blaetter
    # verschieden sein - sonst verloere der Baum Eintraege.
    from board_eintrag import TokenIssued, parse

    nonces = [p.nonce for p in map(parse, issued) if isinstance(p, TokenIssued)]
    check("Parallel: Ausgabe-Nonces eindeutig", len(set(nonces)) == n, f"{len(set(nonces))} von {n}")
    # Alles zusammen: der Eroeffnungseintrag der Umfrage plus beide Phasen.
    check("Parallel: keine zusaetzlichen Board-Eintraege",
          len(entries) == 1 + 2 * n, f"{len(entries)} statt {1 + 2 * n}")
    chain_ok, broken_at = verify_batches(service.board_store.veroeffentlichte_batches(poll))
    check("Parallel: Batch-Kette unter Nebenlaeufigkeit intakt",
          chain_ok, f"Bruch in Batch {broken_at}")
    acc = service.accounting(poll)
    check("Parallel: Ledger-Abrechnung stimmt", acc.ok and acc.n_eligible == acc.n_votes == n,
          f"eligible={acc.n_eligible} votes={acc.n_votes}")
    check("Parallel: Konsistenzpruefung meldet nichts fuer diese Umfrage",
          not service.check_all().get(poll), str(service.check_all().get(poll)))

    import debug as debug_modul

    # Gezaehlt statt gestromt (EIP-T-041): Die Stimmen muessen vollstaendig
    # erfasst sein, aber ohne Uhrzeit und Reihenfolge.
    phase_b = [z for z in debug_modul.teilnahme_gesamt()
               if z.detail.get("poll") == poll and z.category == "phase-b"]
    check("Parallel: Debug-Modul hat jede Stimme erfasst, nichts verloren",
          sum(z.anzahl for z in phase_b) == n, f"{sum(z.anzahl for z in phase_b)} von {n}")
    check("Parallel: keine Stimme im Ereignisstrom (waere korrelierbar)",
          not [e for e in debug_modul.events_gesamt("all") if e.category in ("phase-a", "phase-b")])


def anspruch_atomar(n: int = 8) -> None:
    """Wettlauf um denselben Anspruch (EIP-T-047).

    parallel_participation zeigt, dass n *verschiedene* Teilnehmende
    gleichzeitig durchkommen. Hier laufen n Anfragen gegen genau denselben
    Ausweis und danach gegen genau dasselbe Token - der Fall, den frueher das
    `with store.lock` in poll_service.py abfing. Geprueft wird die Zusage der
    Schnittstelle ("ein Ausweis, ein Token"; "ein Token, eine Stimme"), nicht
    das Vorhandensein eines Locks: faellt die Atomizitaet weg, kommen hier zwei
    Token bzw. zwei Stimmen durch.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    poll = "wettlauf"
    admin = TestClient(app)
    admin.post("/api/admin/login", json={"token": "admin"})
    admin.post("/api/admin/create",
               json={"poll_id": poll, "question": "Zweimal?", "options": ["Ja", "Nein"]})

    def gleichzeitig(anfrage, n: int) -> list[int]:
        start = threading.Barrier(n)

        def lauf(i: int) -> int:
            client = TestClient(app)
            client.post("/api/auth", json={"credential": "testperson99"})
            start.wait()
            return anfrage(client, i)

        with ThreadPoolExecutor(max_workers=n) as pool:
            return list(pool.map(lauf, range(n)))

    # 1) Ein Ausweis, n gleichzeitige Token-Abholungen
    tokens: list[tuple[bytes, bytes]] = []
    sammel = threading.Lock()

    def hole_token(client: TestClient, _i: int) -> int:
        import secrets

        token = secrets.token_bytes(32)
        # Nicht n/e nennen: n ist hier die Anzahl der Threads.
        modulus, exponent = service.poll_params(poll)
        blinded, inv = blind.blind(token, modulus, exponent)
        response = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
        if response.status_code == 200:
            sig = blind.finalize(bytes.fromhex(response.json()["blind_sig"]), inv, modulus)
            with sammel:
                tokens.append((token, sig))
        return response.status_code

    codes = gleichzeitig(hole_token, n)
    check(f"Wettlauf: von {n} gleichzeitigen Abholungen desselben Ausweises genau eine",
          codes.count(200) == 1, f"{codes.count(200)} mal 200, Codes {sorted(codes)}")
    # Puffer mitgezaehlt: Seit EIP-T-076 loest k nur bei *Stimmen* aus, eine
    # blosse Tokenausgabe wartet also auf den naechsten Batch. Geprueft ist hier
    # die Atomizitaet der Ausgabe, nicht der Zeitpunkt ihrer Veroeffentlichung.
    ausgaben = [e for e in service.board(poll) + service.board_store.pending(poll)
                if e.kind == "TOKEN_ISSUED"]
    check("Wettlauf: genau eine Token-Ausgabe im Board", len(ausgaben) == 1, str(len(ausgaben)))

    if not tokens:
        check("Wettlauf: Token fuer den zweiten Teil vorhanden", False)
        return

    # 2) Ein Token, n gleichzeitige Stimmabgaben
    token, sig = tokens[0]

    def stimme_ab(client: TestClient, i: int) -> int:
        return client.post(
            f"/api/vote/{poll}",
            json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja" if i % 2 else "Nein"]},
        ).status_code

    codes = gleichzeitig(stimme_ab, n)
    check(f"Wettlauf: von {n} gleichzeitigen Abgaben desselben Tokens genau eine",
          codes.count(200) == 1, f"{codes.count(200)} mal 200, Codes {sorted(codes)}")
    votes = [e for e in service.board(poll) if e.kind == "VOTE"]
    check("Wettlauf: genau eine Stimme im Board", len(votes) == 1, f"{len(votes)} Stimmen")
    acc = service.accounting(poll)
    check("Wettlauf: Ledger-Abrechnung stimmt",
          acc.ok and acc.n_eligible == 1 and acc.n_votes == 1,
          f"eligible={acc.n_eligible} votes={acc.n_votes}")
    check("Wettlauf: Konsistenzpruefung meldet nichts fuer diese Umfrage",
          not service.check_all().get(poll), str(service.check_all().get(poll)))

    # Abweisungen muessen im Debug-Modul stehen - sonst faellt ein Wettlauf,
    # der schiefgeht, im Betrieb niemandem auf (§9).
    import debug as debug_modul

    # Abweisungen aus Phase A und B stehen in der Zaehlung, nicht im Strom
    # (EIP-T-041) - sichtbar bleiben sie trotzdem, sonst waere der Umbau ein
    # Verlust an Aufsicht statt ein Gewinn an Unverkettbarkeit.
    abweisungen = sum(z.anzahl for z in debug_modul.teilnahme_gesamt()
                      if z.level == "reject" and poll in str(z.detail.get("pfad", "")))
    check("Wettlauf: jede Abweisung im Debug-Modul sichtbar",
          abweisungen == 2 * (n - 1), f"{abweisungen} statt {2 * (n - 1)}")


def abbruch_nach_signatur() -> None:
    """Netzabbruch nach dem Signieren (EIP-T-070).

    Der Fall, der ohne Wiederhol-Puffer einen Berechtigten dauerhaft
    ausschliesst: Der Server hat signiert und das Pseudonym als versorgt
    vermerkt, die Antwort kommt nie an. Nachgestellt wird er, indem der Test die
    erste Antwort schlicht wegwirft - fuer den Server ist das nicht von einem
    Verbindungsabbruch zu unterscheiden.

    Geprueft wird beides: dass die *unveraendert* wiederholte Anfrage dieselbe
    Signatur zurueckbekommt, und dass eine *andere* Anfrage desselben Ausweises
    weiter abgewiesen wird. Ohne den zweiten Teil waere der Puffer ein zweites
    Token durch die Hintertuer.
    """
    import secrets as sec

    retry_app = create_app(
        store_path=Path(tempfile.mkdtemp()) / "retry.sqlite3",
        settings=Settings(admin_token="admin", batch_k=1, antwort_floor_s=0),
    )
    svc = retry_app.state.deps.service
    client = TestClient(retry_app)
    poll = "abbruch"
    client.post("/api/admin/login", json={"token": "admin"})
    client.post("/api/admin/create",
                json={"poll_id": poll, "question": "Nochmal?", "options": ["Ja", "Nein"]})
    client.post("/api/auth", json={"credential": "testperson70"})

    n, e = svc.poll_params(poll)
    token = sec.token_bytes(32)
    blinded, inv = blind.blind(token, n, e)

    # 1) Anfrage geht durch, die Antwort "erreicht den Client nicht".
    erste = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
    check("Abbruch: erste Anfrage wird signiert", erste.status_code == 200)
    check("Abbruch: Berechtigung gilt danach als verbraucht",
          svc.ledger_stand(poll)[0] == 1)

    # 2) Dieselbe verblindete Anfrage noch einmal - der Nutzer laedt neu.
    zweite = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
    check("Abbruch: unveraendert wiederholte Anfrage wird beantwortet",
          zweite.status_code == 200, str(zweite.json())[:100])
    check("Abbruch: dieselbe Blindsignatur, keine neue Ausgabe",
          zweite.status_code == 200
          and zweite.json().get("blind_sig") == erste.json()["blind_sig"])
    # Board und Puffer zusammen: Die Tokenausgabe allein loest keinen Batch aus
    # (k zaehlt Stimmen, EIP-T-076); doppelt vorhanden waere sie trotzdem hier.
    check("Abbruch: kein zweiter Ledger-Eintrag, kein zweiter Board-Eintrag",
          svc.ledger_stand(poll)[0] == 1
          and len([x for x in svc.board(poll) + svc.board_store.pending(poll)
                   if x.kind == "TOKEN_ISSUED"]) == 1)

    # Und die wiederholte Signatur taugt wirklich zum Abstimmen.
    sig = blind.finalize(bytes.fromhex(zweite.json()["blind_sig"]), inv, n)
    check("Abbruch: wiederholte Signatur ist gueltig", blind.verify(svc.poll_pubkey(poll), token, sig))
    gestimmt = client.post(f"/api/vote/{poll}",
                           json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja"]})
    check("Abbruch: damit laesst sich abstimmen", gestimmt.status_code == 200)

    # 3) Ein *anderes* blinded_msg desselben Ausweises bleibt abgewiesen.
    anderes, _ = blind.blind(sec.token_bytes(32), n, e)
    dritte = client.post(f"/api/token/{poll}", json={"blinded": anderes.hex()})
    check("Abbruch: abweichende Anfrage desselben Ausweises abgewiesen",
          dritte.status_code == 400, str(dritte.json())[:80])

    import debug as debug_modul

    sichtbar = any(z.level == "reject" and poll in str(z.detail.get("pfad", ""))
                   for z in debug_modul.teilnahme_gesamt())
    check("Abbruch: die Abweisung steht im Debug-Modul", sichtbar)

    # 4) Ablauf: nach der Lebensdauer ist der Puffer leer und die Wiederholung
    #    endet wie jede andere zweite Anfrage.
    check("Abbruch: Puffer haelt genau einen Eintrag",
          svc.berechtigung.wiederhol_puffer_stand() == 1)
    # Der Eintrag traegt die angebrochene Stunde, nicht den Zeitpunkt (keine
    # feinen Zeitstempel neben den Ledgern). Ein Ablauf laesst sich deshalb
    # nicht durch Warten pruefen, sondern nur, indem die Ablaufgrenze in die
    # Zukunft gelegt wird - geprueft ist damit der Loeschweg, nicht die Uhr.
    svc.berechtigung.verwirf_wiederhol_puffer(aelter_als=datetime.now() + timedelta(hours=1))
    check("Abbruch: abgelaufene Eintraege verschwinden", svc.berechtigung.wiederhol_puffer_stand() == 0)

    client2 = TestClient(retry_app)
    client2.post("/api/auth", json={"credential": "testperson71"})
    blinded2, _ = blind.blind(sec.token_bytes(32), n, e)
    client2.post(f"/api/token/{poll}", json={"blinded": blinded2.hex()})
    svc.berechtigung.verwirf_wiederhol_puffer(aelter_als=datetime.now() + timedelta(hours=1))
    nach_ablauf = client2.post(f"/api/token/{poll}", json={"blinded": blinded2.hex()})
    check("Abbruch: nach Ablauf keine Wiederholung mehr", nach_ablauf.status_code == 400)

    # 5) Schliessen raeumt den Puffer der Umfrage ab - eine wiederholte
    #    Signatur waere danach fuer nichts mehr gut.
    client3 = TestClient(retry_app)
    client3.post("/api/auth", json={"credential": "testperson72"})
    blinded3, _ = blind.blind(sec.token_bytes(32), n, e)
    client3.post(f"/api/token/{poll}", json={"blinded": blinded3.hex()})
    check("Abbruch: Puffer gefuellt vor dem Schliessen", svc.berechtigung.wiederhol_puffer_stand() >= 1)
    client.post(f"/api/admin/close/{poll}")
    check("Abbruch: Schliessen loescht den Puffer der Umfrage",
          svc.berechtigung.wiederhol_puffer_stand() == 0)


def puffer_abschaltbar() -> None:
    """retry_cache_h=0 stellt das alte Verhalten wieder her (EIP-T-070)."""
    import secrets as sec

    aus_app = create_app(
        store_path=Path(tempfile.mkdtemp()) / "ohne_retry.sqlite3",
        settings=Settings(admin_token="admin", batch_k=1, antwort_floor_s=0, retry_cache_h=0),
    )
    svc = aus_app.state.deps.service
    client = TestClient(aus_app)
    poll = "ohnepuffer"
    client.post("/api/admin/login", json={"token": "admin"})
    client.post("/api/admin/create",
                json={"poll_id": poll, "question": "Ohne?", "options": ["Ja", "Nein"]})
    client.post("/api/auth", json={"credential": "testperson73"})
    blinded, _ = blind.blind(sec.token_bytes(32), *svc.poll_params(poll))
    client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
    zweite = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
    check("Puffer aus: auch die identische Wiederholung wird abgewiesen",
          zweite.status_code == 400, str(zweite.json())[:80])
    check("Puffer aus: nichts gespeichert", svc.berechtigung.wiederhol_puffer_stand() == 0)


def umfrage_schluessel() -> None:
    """Umfrage-Schluessel und seine Vernichtung beim Schliessen (EIP-T-033, D).

    Geprueft wird die *Wirkung*, nicht die Speicherstelle: dass derselbe Ausweis
    in zwei Umfragen verschiedene Wahlberechtigungs-Schluessel bekommt, und dass
    nach dem Schliessen niemand - auch der Server nicht - den Eligibility-Eintrag
    noch auf sein Pseudonym zurueckrechnen kann.
    """
    from poll_service import POLL_SECRET, Rejected

    admin = TestClient(app)
    admin.post("/api/admin/login", json={"token": "admin"})
    for poll in ("schluessel-a", "schluessel-b"):
        admin.post("/api/admin/create",
                   json={"poll_id": poll, "question": "Und?", "options": ["Ja", "Nein"]})

    check("Umfrage-Schluessel: beim Anlegen erzeugt",
          service.berechtigung.get_config(POLL_SECRET + "schluessel-a") is not None)

    # Dasselbe Pseudonym, zwei Umfragen - zwei unabhaengige Schluessel. Ohne das
    # waere ein Meinungsprofil ueber Umfragen hinweg bildbar (§6).
    a = service.voter_key("testperson-d", "schluessel-a")
    b = service.voter_key("testperson-d", "schluessel-b")
    check("Umfrage-Schluessel: derselbe Ausweis ergibt je Umfrage einen anderen Voter-Key", a != b)
    check("Umfrage-Schluessel: Ableitung ist innerhalb einer Umfrage stabil",
          a == service.voter_key("testperson-d", "schluessel-a"))

    # Ein Teilnehmer holt sich ein Token, damit es beim Schliessen wirklich
    # einen Eintrag gibt, dessen Rueckrechenbarkeit verschwindet.
    teilnehmer = TestClient(app)
    teilnehmer.post("/api/auth", json={"credential": "testperson40"})
    geholt = get_token(teilnehmer, "schluessel-a")
    check("Umfrage-Schluessel: Token-Abholung funktioniert normal", geholt is not None)

    admin.post("/api/admin/close/schluessel-a")

    check("Umfrage-Schluessel: beim Schliessen vernichtet",
          service.berechtigung.get_config(POLL_SECRET + "schluessel-a") is None)

    # Der eigentliche Punkt von D: Der Server *kann* nicht mehr zuordnen.
    try:
        service.voter_key("testperson-d", "schluessel-a")
        rueckrechenbar = True
    except Rejected:
        rueckrechenbar = False
    check("Umfrage-Schluessel: Pseudonym nach Schliessung nicht mehr auf den Ledger abbildbar",
          not rueckrechenbar)

    check("Umfrage-Schluessel: Eligibility-Eintrag bleibt bestehen (Abrechnung nach §9)",
          service.ledger_stand("schluessel-a")[0] == 1)

    check("Umfrage-Schluessel: der Schluessel der anderen Umfrage ist unberuehrt",
          service.berechtigung.get_config(POLL_SECRET + "schluessel-b") is not None)

    # Debug-Modul: beide Richtungen des Lebenszyklus sind Befunde. Hier der
    # Normalfall - geschlossen und vernichtet ist *kein* Befund.
    findings = service.check_consistency("schluessel-a")
    check("Umfrage-Schluessel: geschlossene Umfrage ohne Schluessel meldet nichts",
          not any("Schluessel" in f for f in findings), detail=str(findings))

    # Und der Stoerfall: Schluessel ueberlebt das Schliessen -> sichtbar.
    service.berechtigung.set_config(POLL_SECRET + "schluessel-a", "00" * 32)
    findings = service.check_consistency("schluessel-a")
    check("Debug-Modul: Schluessel, der eine geschlossene Umfrage ueberlebt, wird gemeldet",
          any("geschlossen" in f and "Schluessel" in f for f in findings), detail=str(findings))
    service.vernichte_poll_secret("schluessel-a")

    # Umgekehrt: offene Umfrage ohne Schluessel kann niemanden mehr zulassen.
    service.vernichte_poll_secret("schluessel-b")
    findings = service.check_consistency("schluessel-b")
    check("Debug-Modul: offene Umfrage ohne Schluessel wird gemeldet",
          any("offen" in f and "Schluessel" in f for f in findings), detail=str(findings))

    verirrt = TestClient(app)
    verirrt.post("/api/auth", json={"credential": "testperson41"})
    check("Umfrage-Schluessel: ohne Schluessel wird abgewiesen statt neu abgeleitet",
          get_token(verirrt, "schluessel-b") is None)
    check("Umfrage-Schluessel: die Abweisung erzeugt keinen Eligibility-Eintrag",
          service.ledger_stand("schluessel-b")[0] == 0)


def signaturschluessel() -> None:
    """Token-Signaturschluessel je Umfrage und seine Vernichtung (EIP-T-069).

    Zwei Zusagen stehen hier auf dem Pruefstand. Erstens: Ein Token aus Umfrage
    A ist in Umfrage B wertlos - nicht weil eine Regel es verbietet, sondern
    weil die Signatur dort nicht gilt. Zweitens: Nach dem Schliessen kann
    niemand mehr gueltige Token herstellen, auch der Betreiber nicht - die
    Auszaehlung ist eingefroren. Beides wird an der *Wirkung* geprueft, nicht
    an der Speicherstelle.
    """
    import secrets as sec

    from board_eintrag import PollOpen, parse
    from poll_service import POLL_KEY, Rejected

    admin = TestClient(app)
    admin.post("/api/admin/login", json={"token": "admin"})
    for poll in ("sig-a", "sig-b"):
        admin.post("/api/admin/create",
                   json={"poll_id": poll, "question": "Wessen Schluessel?",
                         "options": ["Ja", "Nein"]})

    check("Signaturschluessel: beim Anlegen erzeugt",
          service.berechtigung.get_config(POLL_KEY + "sig-a") is not None)

    # Der oeffentliche Teil steht im Board, nicht in der Datenbankkonfiguration:
    # Nur dort ueberlebt er die Vernichtung des privaten Teils, und nur dort
    # liegt er unter der Merkle-Wurzel.
    eroeffnung = next(
        (p for p in map(parse, service.board("sig-a")) if isinstance(p, PollOpen)), None
    )
    check("Signaturschluessel: oeffentlicher Teil steht im POLL_OPEN-Eintrag",
          eroeffnung is not None and "PUBLIC KEY" in eroeffnung.pubkey)
    check("Signaturschluessel: Board und Dienst nennen denselben",
          eroeffnung is not None and eroeffnung.pubkey == service.poll_pubkey_pem("sig-a"))

    a_n, _ = service.poll_params("sig-a")
    b_n, _ = service.poll_params("sig-b")
    check("Signaturschluessel: zwei Umfragen, zwei verschiedene Schluessel", a_n != b_n)

    # Der Kern: ein in A gueltig signiertes Token in B einreichen.
    person = TestClient(app)
    person.post("/api/auth", json={"credential": "testperson50"})
    geholt = get_token(person, "sig-a")
    check("Signaturschluessel: Token-Abholung in A funktioniert normal", geholt is not None)
    if geholt is None:
        return
    token, sig = geholt

    fremd = TestClient(app)
    fremd.post("/api/auth", json={"credential": "testperson51"})
    quer = fremd.post("/api/vote/sig-b",
                      json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja"]})
    check("Signaturschluessel: Token aus Umfrage A gilt in Umfrage B nicht",
          quer.status_code == 400 and "Signatur" in quer.json().get("error", ""),
          f"status={quer.status_code} {quer.json().get('error', '')[:60]}")
    check("Signaturschluessel: das abgewiesene Token bleibt in A brauchbar",
          person.post("/api/vote/sig-a",
                      json={"token": token.hex(), "sig": sig.hex(),
                            "choices": ["Ja"]}).status_code == 200)

    # Vernichtung beim Schliessen - und was danach noch geht und was nicht.
    admin.post("/api/admin/close/sig-a")
    check("Signaturschluessel: beim Schliessen vernichtet",
          service.berechtigung.get_config(POLL_KEY + "sig-a") is None)
    check("Signaturschluessel: der Schluessel der anderen Umfrage ist unberuehrt",
          service.berechtigung.get_config(POLL_KEY + "sig-b") is not None)

    # Der oeffentliche Teil ueberlebt - sonst waere die Auszaehlung nach dem
    # Schliessen nicht mehr nachpruefbar, und die Vernichtung haette die
    # Verifizierbarkeit mitgenommen.
    bericht = service.pruefbericht("sig-a")
    check("Signaturschluessel: Board bleibt nach der Vernichtung pruefbar",
          bericht.chain.sound and bericht.schluessel_fehler is None,
          str(bericht.schluessel_fehler))
    check("Signaturschluessel: Ergebnis wird nach der Vernichtung noch ausgezaehlt",
          service.tally("sig-a") == {"Ja": 1, "Nein": 0}, str(service.tally("sig-a")))
    check("Signaturschluessel: eigenes Token bleibt auffindbar",
          service.lookup("sig-a", token.hex()) == ["Ja"])

    # Und die Aussage, um derentwillen der Schluessel ueberhaupt vernichtet
    # wird: Auch der Betreiber mit der Datenbank in der Hand kommt nicht mehr
    # an gueltige Token. demo.stuff_ballot ist genau dieser Weg (§9).
    try:
        demo.stuff_ballot(service, "sig-a", "Ja")
        gestopft = True
    except Rejected:
        gestopft = False
    check("Signaturschluessel: nach Schliessung kann auch der Betreiber kein Token mehr bauen",
          not gestopft)

    # Debug-Modul, beide Richtungen (Muster aus EIP-T-033, D).
    findings = service.check_consistency("sig-a")
    check("Signaturschluessel: geschlossene Umfrage ohne Schluessel meldet nichts",
          not any("Signaturschluessel" in f for f in findings), str(findings))

    # Ein gueltiger, aber fremder Schluessel: die Umfrage haette einen privaten
    # Schluessel, der nicht zu ihrem Board passt.
    from cryptography.hazmat.primitives import serialization as _ser

    fremdes_pem = blind.generate_key(1024).private_bytes(
        _ser.Encoding.PEM, _ser.PrivateFormat.PKCS8, _ser.NoEncryption()
    ).decode()
    service.berechtigung.set_config(POLL_KEY + "sig-a", fremdes_pem)
    findings = service.check_consistency("sig-a")
    check("Debug-Modul: Signaturschluessel, der eine geschlossene Umfrage ueberlebt, wird gemeldet",
          any("geschlossen" in f and "Signaturschluessel" in f for f in findings), str(findings))
    check("Debug-Modul: Schluessel, der nicht zum Board passt, wird gemeldet",
          any("passt nicht" in f for f in findings), str(findings))

    # Unlesbarer Schluessel: ein Zustand, den es geben kann (beschaedigte Datei,
    # halb eingespielte Sicherung). Er muss als Befund erscheinen und darf die
    # Konsistenzpruefung nicht mitreissen - sie ist das Werkzeug, mit dem man
    # ihn findet.
    service.berechtigung.set_config(POLL_KEY + "sig-a", "kein-schluessel")
    findings = service.check_consistency("sig-a")
    check("Debug-Modul: unlesbarer Signaturschluessel wird gemeldet, ohne die Pruefung zu werfen",
          any("nicht lesbar" in f for f in findings), str(findings))
    service.vernichte_poll_key("sig-a")

    service.vernichte_poll_key("sig-b")
    findings = service.check_consistency("sig-b")
    check("Debug-Modul: offene Umfrage ohne Signaturschluessel wird gemeldet",
          any("offen" in f and "Signaturschluessel" in f for f in findings), str(findings))
    verirrt = TestClient(app)
    verirrt.post("/api/auth", json={"credential": "testperson52"})
    check("Signaturschluessel: ohne Schluessel wird abgewiesen statt neu erzeugt",
          get_token(verirrt, "sig-b") is None)

    # Ein Board, dessen Eroeffnung keinen Schluessel nennt, ist nicht pruefbar -
    # und darf nicht als "alle Signaturen gueltig" durchgehen, nur weil keine
    # geprueft werden konnte.
    from verifikation import Batch, BoardEntry, pruefe

    ohne = BoardEntry.from_payload(
        {"type": "POLL_OPEN", "poll": "x", "question": "?", "options": ["Ja"]}, batch=0
    )
    import board_eintrag as _be

    root = _be.merkle_root([ohne.leaf_hash])
    blind_board = [Batch(n=0, merkle_root=root,
                         batch_root=_be.batch_root(root, _be.GENESIS), entries=(ohne,))]
    b = pruefe(blind_board, ["Ja"])
    check("Signaturschluessel: Board ohne Schluessel meldet Befund statt 'alles gueltig'",
          b.schluessel_fehler is not None and not b.chain.signatures_ok and not b.result_ok,
          str(b.schluessel_fehler))
    try:
        service.tally_von(b)
        ausgezaehlt = True
    except Rejected:
        ausgezaehlt = False
    check("Signaturschluessel: ohne Schluessel kein Ergebnis", not ausgezaehlt)


def rfc9474_testvektor() -> None:
    """Beide Blindsignatur-Seiten gegen RFC 9474 Anhang A.4 (EIP-T-008).

    Die Blindsignatur ist selbst geschrieben - das ist die dokumentierte
    Abweichung von RFC §4. Ein Roundtrip-Test wuerde daran nichts aendern: er
    ist auch dann gruen, wenn Verblinden und Entblinden denselben Fehler machen
    und sich gegenseitig aufheben. Der RFC-Vektor kommt von aussen und ist
    deshalb der einzige Korrektheitsnachweis, den es ohne Audit gibt.

    Die JS-Seite laeuft ueber node, weil sie im Browser lebt. Fehlt node, faellt
    der Prueffall nicht aus, sondern meldet sich als Luecke - eine stumm
    uebersprungene Kryptopruefung waere schlimmer als gar keine.
    """
    abweichungen = blind.testvektor()
    check("Krypto: blind.py trifft den RFC-9474-Vektor A.4 in jedem Schritt",
          not abweichungen, ", ".join(abweichungen))
    check(f"Krypto: geprueft wird die Variante, die auch benutzt wird ({blind.VARIANTE})",
          blind.VARIANTE == json.loads(
              (Path(__file__).parent / "rfc9474_a4.json").read_text())["variante"])

    node = shutil.which("node")
    if node is None:
        check("Krypto: static/blind.js gegen denselben Vektor geprueft", False,
              "node nicht gefunden - die Browser-Seite ist ungeprueft")
        return
    lauf = subprocess.run([node, "blind_vektor.mjs"], cwd=Path(__file__).parent,
                          capture_output=True, text=True)
    zeilen = (lauf.stdout + lauf.stderr).strip().splitlines()
    check("Krypto: static/blind.js trifft denselben RFC-9474-Vektor",
          lauf.returncode == 0, zeilen[-1][:110] if zeilen else "")


def eintragsformat() -> None:
    """Konstruktoren und Parser (EIP-T-046) - ohne Board, ohne Store.

    Geprueft wird das Rundum: was ein Konstruktor schreibt, muss der Parser als
    dieselbe Variante zurueckgeben, und alles, was sich nicht deuten laesst,
    muss zu genau einem Ergebnis fuehren - Unlesbar mit Grund.
    """
    import board_eintrag as be

    def eintrag(payload: dict | str) -> be.Eintrag:
        line = payload if isinstance(payload, str) else be.canonical(payload)
        return be.parse(be.BoardEntry(line, be.leaf_hash(line)))

    token, sig = bytes.fromhex("aa" * 32), bytes.fromhex("bb" * 128)
    gestimmt = eintrag(be.vote("p", token, sig, ["Nein", "Ja"]))
    check("Format: Stimme kommt als Vote zurueck",
          isinstance(gestimmt, be.Vote) and gestimmt.token == token and gestimmt.sig == sig,
          type(gestimmt).__name__)
    check("Format: Optionen im Board sortiert, Reihenfolge des Anklickens unsichtbar",
          isinstance(gestimmt, be.Vote) and gestimmt.choices == ("Ja", "Nein"),
          str(getattr(gestimmt, "choices", gestimmt)))

    varianten = [
        (be.poll_open("p", "?", ["Ja", "Nein"], _PUBKEY_PEM), be.PollOpen),
        (be.poll_closed("p"), be.PollClosed),
        (be.token_issued("p"), be.TokenIssued),
    ]
    check("Format: jede Variante wird als ihr Typ gelesen",
          all(isinstance(eintrag(p), typ) for p, typ in varianten))
    check("Format: kind bleibt fuer die Anzeige erhalten",
          [be.BoardEntry.from_payload(p).kind for p, _ in varianten]
          == ["POLL_OPEN", "POLL_CLOSED", "TOKEN_ISSUED"])
    # Der Nonce ersetzt die laufende Nummer (ADR E2): zwei Ausgaben derselben
    # Umfrage muessen verschiedene Blaetter ergeben.
    check("Format: zwei Token-Ausgaben ergeben verschiedene Blaetter",
          be.BoardEntry.from_payload(be.token_issued("p")).leaf_hash
          != be.BoardEntry.from_payload(be.token_issued("p")).leaf_hash)

    kaputt: list[tuple[str, dict | str]] = [
        ("kein JSON", "{nicht json"),
        ("JSON, aber kein Objekt", "[1,2,3]"),
        ("unbekannter Typ", {"type": "SPENDE", "poll": "p"}),
        ("Typ fehlt", {"poll": "p", "choices": ["Ja"]}),
        ("Stimme ohne choices", {"type": "VOTE", "poll": "p", "token": "aa", "sig": "bb"}),
        ("Stimme mit leeren choices",
         {"type": "VOTE", "poll": "p", "token": "aa", "sig": "bb", "choices": []}),
        ("Stimme ohne sig", {"type": "VOTE", "poll": "p", "token": "aa", "choices": ["Ja"]}),
        ("Token kein Hex",
         {"type": "VOTE", "poll": "p", "token": "zz", "sig": "bb", "choices": ["Ja"]}),
        ("choices kein Text",
         {"type": "VOTE", "poll": "p", "token": "aa", "sig": "bb", "choices": [1]}),
        ("Token-Ausgabe ohne Nonce", {"type": "TOKEN_ISSUED", "poll": "p"}),
        ("Token-Ausgabe mit Nonce falscher Laenge",
         {"type": "TOKEN_ISSUED", "poll": "p", "nonce": "abcd"}),
        ("poll fehlt", {"type": "POLL_CLOSED"}),
    ]
    fehlend = [name for name, payload in kaputt if not isinstance(eintrag(payload), be.Unlesbar)]
    check("Format: alles Ungueltige wird zu Unlesbar, nichts rutscht durch",
          not fehlend, "durchgerutscht: " + ", ".join(fehlend))
    # Dass der Parser nie wirft, prueft die Schleife oben mit: jeder dieser
    # Faelle laeuft ungeschuetzt durch parse().
    check("Format: Unlesbar nennt einen Grund",
          all(str(getattr(eintrag(p), "grund", "")).strip() for _, p in kaputt))

    check("Format: Modul kennt weder Store noch Datenbank",
          not any(m in be.__dict__ for m in ("Store", "store", "sqlite3")))


def auditor_unabhaengig() -> None:
    """Der Auditor als zweite, unabhaengige Implementierung (EIP-T-071).

    auditor.py rechnet das Board aus seiner oeffentlichen Beschreibung nach und
    importiert dafuer nichts aus der App. Genau daraus entsteht das Risiko, das
    dieser Block absichert: Zwei Implementierungen koennen auseinanderlaufen,
    und dann prueft der Auditor ein Format, das die App gar nicht schreibt.
    Geprueft wird deshalb beides - dass die Formeln uebereinstimmen, und dass
    der Auditor an einem echten Export dieselben Befunde erhebt.
    """
    import json
    import secrets

    import auditor as au
    import board_eintrag as be

    for n in (1, 2, 3, 4, 5, 8, 9):
        payloads = [be.canonical({"i": i, "x": secrets.token_hex(4)}) for i in range(n)]
        blaetter = [be.leaf_hash(p) for p in payloads]
        check(f"Auditor: Blatt-Hash und Merkle-Root stimmen ueberein (n={n})",
              [au.blatt(p) for p in payloads] == blaetter
              and au.wurzel(blaetter) == be.merkle_root(blaetter))
        # Der Inklusionspfad ist die Zusage aus EIP-T-033 B: er belegt ein
        # einzelnes Blatt, ohne dass der Pruefende das ganze Board braucht.
        root = be.merkle_root(blaetter)
        check(f"Auditor: Inklusionspfad fuehrt fuer jedes Blatt zur Root (n={n})",
              all(au.pfad_prueft(b, au.pfad(blaetter, b) or [], root) for b in blaetter))
    check("Auditor: Kettenglied stimmt ueberein",
          au.kettenglied("aa" * 32, be.GENESIS) == be.batch_root("aa" * 32, be.GENESIS))
    check("Auditor: fremdes Blatt hat keinen Pfad",
          au.pfad([be.leaf_hash("a"), be.leaf_hash("b")], "cc" * 32) is None)

    # Ein echter Export dieser Instanz, geprueft mit dem fremden Code.
    export = service.board_export(POLL)
    a = au.Auditor(export)
    a.pruefe_struktur()
    a.pruefe_eintraege(a.token_schluessel(None))
    check("Auditor: Export dieser Instanz ist unauffaellig",
          a.belastbar, "; ".join(a.befunde))
    check("Auditor: Zaehlung stimmt mit der eigenen Auszaehlung ueberein",
          a.counts == service.tally_von(service.pruefbericht(POLL)), str(a.counts))
    a.pruefe_ergebnis({"participation": len(a.stimmen), "n_eligible": a.n_token,
                       "result": a.counts})
    check("Auditor: Ergebnisabgleich ohne Abweichung", not a.befunde, "; ".join(a.befunde))

    # Umgeschriebene Stimme bei stehengelassener Root - dieselbe Demo wie in
    # pruefung_ohne_datenbank, nur mit dem Code eines Dritten.
    kaputt = json.loads(json.dumps(export))
    for batch in kaputt["batches"]:
        stimmen = [i for i, p in enumerate(batch["entries"]) if '"VOTE"' in p]
        if stimmen:
            daten = json.loads(batch["entries"][stimmen[0]])
            daten["choices"] = ["Nein" if daten["choices"] == ["Ja"] else "Ja"]
            batch["entries"][stimmen[0]] = be.canonical(daten)
            break
    b = au.Auditor(kaputt)
    b.pruefe_struktur()
    b.pruefe_eintraege(b.token_schluessel(None))
    check("Auditor: umgeschriebene Stimme faellt auf",
          not b.belastbar and any("Merkle-Root" in f for f in b.befunde), "; ".join(b.befunde))

    # Dieselbe Stimme zweimal, Roots und Kette sauber nachgerechnet. Diese
    # Pruefung hat verifikation.py nicht: dort verhindert der Ledger die
    # Doppelabgabe, und der ist von aussen nicht einsehbar.
    doppelt = json.loads(json.dumps(export))
    stimme = next(p for batch in doppelt["batches"] for p in batch["entries"] if '"VOTE"' in p)
    doppelt["batches"][-1]["entries"].append(stimme)
    vorher = be.GENESIS
    for batch in doppelt["batches"]:
        batch["merkle_root"] = be.merkle_root(be.leaf_hash(p) for p in batch["entries"])
        batch["batch_root"] = be.batch_root(batch["merkle_root"], vorher)
        vorher = batch["batch_root"]
    c = au.Auditor(doppelt)
    c.pruefe_struktur()
    c.pruefe_eintraege(c.token_schluessel(None))
    check("Auditor: zweimal dasselbe Token faellt auf",
          not c.belastbar and any("zweimal" in f for f in c.befunde), "; ".join(c.befunde))

    check("Auditor: importiert nichts aus der App",
          not any(m in au.__dict__ for m in ("board_eintrag", "verifikation", "blind", "store")))


def pruefung_ohne_datenbank() -> None:
    """Die Pruefung eines Dritten (EIP-T-045).

    Laeuft ohne SQLite, ohne TestClient und ohne den privaten Signaturschluessel
    im Pruefpfad: gebaut wird ein Board von Hand, geprueft wird mit
    verifikation.pruefe() und dem oeffentlichen Schluessel. Genau das ist die
    Zusage aus §7 - wenn dieser Block laeuft, kann sie jeder nachvollziehen.
    """
    import secrets

    import board_eintrag
    from board_eintrag import GENESIS, batch_root, leaf_hash, merkle_root
    from verifikation import Batch, BoardEntry, canonical, pruefe

    from cryptography.hazmat.primitives import serialization

    key = blind.generate_key(1024)  # klein, weil hier nur der Pfad geprueft wird
    pub = key.public_key()
    n, e, d = pub.public_numbers().n, pub.public_numbers().e, key.private_numbers().d
    # Der Schluessel geht ins Board und wird von dort geprueft (EIP-T-069) -
    # der Pruefpfad bekommt ihn nicht mehr von aussen gereicht.
    pub_pem = pub.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    options = ["Ja", "Nein"]

    def signiertes_token() -> tuple[bytes, bytes]:
        token = secrets.token_bytes(32)
        blinded, inv = blind.blind(token, n, e)
        sig = blind.finalize(blind.blind_sign(blinded, n, d, e), inv, n)
        return token, sig

    def board(batch_payloads: list[list[dict]]) -> list[Batch]:
        """Batches von Hand, mit denselben Formeln wie board_eintrag."""
        batches, prev = [], GENESIS
        for i, payloads in enumerate(batch_payloads):
            entries = tuple(BoardEntry.from_payload(p, batch=i) for p in payloads)
            root = merkle_root(en.leaf_hash for en in entries)
            glied = batch_root(root, prev)
            batches.append(Batch(n=i, merkle_root=root, batch_root=glied, entries=entries))
            prev = glied
        return batches

    t1, s1 = signiertes_token()
    t2, s2 = signiertes_token()
    # Gebaut wird mit denselben Konstruktoren wie im Server (EIP-T-046) - ein
    # von Hand getipptes Board wuerde die Pruefung gegen ein Format testen, das
    # die App gar nicht schreibt.
    eroeffnung = board_eintrag.poll_open("p", "?", options, pub_pem)
    ausgabe1 = board_eintrag.token_issued("p")
    ausgabe2 = board_eintrag.token_issued("p")
    stimme1 = board_eintrag.vote("p", t1, s1, ["Ja"])
    stimme2 = board_eintrag.vote("p", t2, s2, ["Nein"])
    batch_payloads = [[eroeffnung], [ausgabe1, ausgabe2, stimme1], [stimme2]]
    batches = board(batch_payloads)

    bericht = pruefe(batches, options)
    check("Pruefung ohne DB: intaktes Board ist unauffaellig",
          bericht.chain.sound and bericht.accounting.ok and bericht.result_ok)
    check("Pruefung ohne DB: Auszaehlung aus dem Board",
          bericht.counts == {"Ja": 1, "Nein": 1}, str(bericht.counts))
    check("Pruefung ohne DB: eigenes Token auffindbar", bericht.lookup(t1.hex()) == ["Ja"])
    check("Pruefung ohne DB: fremdes Token nicht auffindbar", bericht.lookup("aa" * 32) is None)

    # Umgeschriebene Stimme bei stehengelassener Root - genau die Demo aus §9,
    # hier ohne App
    manipuliert = canonical({**stimme1, "choices": ["Nein"]})
    tampered = list(batches)
    tampered[1] = Batch(
        n=1, merkle_root=batches[1].merkle_root, batch_root=batches[1].batch_root,
        entries=tuple(
            BoardEntry(manipuliert, leaf_hash(manipuliert), 1)
            if en.payload == canonical(stimme1) else en
            for en in batches[1].entries
        ),
    )
    b = pruefe(tampered, options)
    check("Pruefung ohne DB: umgeschriebene Stimme bricht die Batch-Kette",
          not b.chain.ok and b.chain.broken_at == 1 and not b.result_ok,
          f"Batch {b.chain.broken_at}")

    # Geloeschter Eintrag bei neu gerechneter Root: die Kette der Batch-Roots
    # entlarvt ihn (ADR Fund 3 - eine Menge allein waere nicht append-only).
    geloescht = board(batch_payloads)
    kleiner = tuple(en for en in geloescht[1].entries if en.payload != canonical(stimme1))
    neue_root = merkle_root(en.leaf_hash for en in kleiner)
    geloescht[1] = Batch(
        n=1, merkle_root=neue_root,
        batch_root=geloescht[1].batch_root,  # alte Kette bleibt stehen
        entries=kleiner,
    )
    b = pruefe(geloescht, options)
    check("Pruefung ohne DB: geloeschter Eintrag bricht die Batch-Kette",
          not b.chain.ok and b.chain.broken_at == 1, f"Batch {b.chain.broken_at}")

    # Stimme mit erfundener Signatur, Roots sauber nachgerechnet
    b = pruefe(board([[eroeffnung], [ausgabe1, ausgabe2, {**stimme1, "sig": "bb" * 128}]]),
               options)
    check("Pruefung ohne DB: erfundene Token-Signatur faellt auf",
          b.chain.ok and not b.chain.signatures_ok and b.chain.bad_signature_at is not None,
          str(b.chain.bad_signature_at)[:16])

    # Ballot-Stuffing: mehr Stimmen als ausgegebene Token
    b = pruefe(board([[eroeffnung], [ausgabe1, stimme1, stimme2]]), options)
    check("Pruefung ohne DB: Abrechnung entlarvt Ueberschuss",
          not b.accounting.ok and b.accounting.surplus == 1,
          f"{b.accounting.n_votes} Stimmen bei {b.accounting.n_eligible} Token")

    # Option, die es in der Umfrage nicht gibt
    b = pruefe(board(batch_payloads + [[{**stimme1, "choices": ["Vielleicht"]}]]), options)
    check("Pruefung ohne DB: unbekannte Option benannt",
          b.unknown_choice == "Vielleicht" and not b.result_ok, str(b.unknown_choice))

    # Kaputtgeschriebene Stimme, Roots sauber nachgerechnet: sie darf nicht
    # einfach verschwinden, sonst waere Kaputtschreiben ein Weg, Stimmen
    # loszuwerden, ohne dass es auffaellt (EIP-T-046).
    b = pruefe(board([[eroeffnung], [ausgabe1, ausgabe2, stimme1],
                      [{**stimme2, "token": "kein hex"}]]), options)
    check("Pruefung ohne DB: unlesbarer Eintrag wird benannt, nicht uebergangen",
          b.chain.ok and b.unlesbar is not None and not b.result_ok, str(b.unlesbar))
    check("Pruefung ohne DB: unlesbarer Eintrag zaehlt nirgends mit",
          b.counts == {"Ja": 1, "Nein": 0} and b.accounting.n_votes == 1, str(b.counts))

    check("Pruefung ohne DB: Pruefmodul kennt weder Store noch privaten Schluessel",
          not any(m in sys.modules["verifikation"].__dict__ for m in ("Store", "store")))


def laufende_pruefung() -> None:
    """Fortgeschriebene Pruefung im Abstimmpfad (EIP-T-051).

    Der Abstimmpfad prueft nicht mehr jede fruehere Signatur bei jeder Stimme.
    Die Ersparnis ist nur zulaessig, solange sie am Befund nichts aendert:
    dieselben Zahlen wie die Vollpruefung, und eine gebrochene Kette faellt
    weiterhin beim Abstimmen auf.
    """
    import debug as debug_modul
    from verifikation import pruefe, pruefe_weiter

    poll = "laufend"
    admin = TestClient(app)
    admin.post("/api/admin/login", json={"token": "admin"})
    admin.post("/api/admin/create",
               json={"poll_id": poll, "question": "Fortlaufend?", "options": ["Ja", "Nein"]})

    for i in range(5):
        client = TestClient(app)
        client.post("/api/auth", json={"credential": f"testperson{30 + i}"})
        issued = get_token(client, poll)
        if issued is None:
            check("Laufende Pruefung: Token-Abholung", False)
            return
        token, sig = issued
        client.post(f"/api/vote/{poll}",
                    json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja" if i % 2 else "Nein"]})

    # Nach fuenf Stimmen steht ein fortgeschriebener Bericht im Service. Er muss
    # dasselbe sagen wie ein Bericht, der bei null anfaengt.
    laufend = service.laufender_bericht(poll)
    voll = pruefe(service.board_store.veroeffentlichte_batches(poll),
                  service.poll(poll).options)
    check("Laufende Pruefung: fortgeschrieben wie voll geprueft",
          (laufend.counts, laufend.accounting, laufend.votes, laufend.chain)
          == (voll.counts, voll.accounting, voll.votes, voll.chain),
          f"{laufend.counts} vs {voll.counts}")

    # Passt der Vorbericht nicht zum Board, faellt pruefe_weiter auf die
    # Vollpruefung zurueck - sonst wuerde ein ausgetauschtes Board mit den
    # Zahlen des alten weitergerechnet.
    fremd = pruefe(service.board_store.veroeffentlichte_batches("parallel"), ["Ja", "Nein"])
    zurueckgefallen = pruefe_weiter(fremd, service.board_store.veroeffentlichte_batches(poll),
                                    service.poll(poll).options)
    check("Laufende Pruefung: fremder Vorbericht faellt auf die Vollpruefung zurueck",
          zurueckgefallen.accounting == voll.accounting and zurueckgefallen.counts == voll.counts,
          f"{zurueckgefallen.accounting} vs {voll.accounting}")

    # Kette brechen und danach abstimmen: die Abkuerzung darf das nicht
    # verschlucken, sonst ist die Aufsicht waehrend des Abstimmens weg.
    # Die erste Stimme lautet "Nein" (i=0), umgeschrieben wird auf "Ja" - sonst
    # bliebe der Payload gleich und es gaebe nichts zu entdecken.
    vote_leaf = next(e.leaf_hash for e in service.board(poll) if e.kind == "VOTE")
    demo.tamper_board(service, poll, vote_leaf, "Ja")
    vor_der_stimme = len(debug_modul.events_gesamt("inconsistency"))

    client = TestClient(app)
    client.post("/api/auth", json={"credential": "testperson35"})
    issued = get_token(client, poll)
    if issued is None:
        check("Laufende Pruefung: Token nach Manipulation", False)
        return
    token, sig = issued
    antwort = client.post(f"/api/vote/{poll}",
                          json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja"]})
    # events() liefert das Neueste zuerst (appendleft). Die neuen Ereignisse
    # stehen also *vorn*, nicht hinten - ein Slice ab `vor_der_stimme` liefert
    # die aeltesten und findet den frischen Befund nur zufaellig.
    jetzt = debug_modul.events_gesamt("inconsistency")
    neu = [e for e in jetzt[: len(jetzt) - vor_der_stimme] if "gebrochen" in e.message]
    check("Laufende Pruefung: gebrochene Kette faellt beim Abstimmen auf",
          antwort.status_code == 200 and bool(neu),
          neu[0].message if neu else "keine Meldung im Debug-Modul")


def pruefwerkzeug_auf_der_kommandozeile(client: TestClient) -> None:
    """Export + CLI: was ein Dritter tatsaechlich in die Hand bekommt."""
    import json

    import verifikation

    export = client.get(f"/api/board/{POLL}")
    check("Export: /api/board liefert das Board als Datei", export.status_code == 200)
    data = export.json()
    check("Export: Batches, Optionen und oeffentliche Schluessel enthalten",
          bool(data.get("batches")) and bool(data.get("options"))
          and "PUBLIC KEY" in str(data.get("public_key"))
          and "PUBLIC KEY" in str(data.get("beleg_public_key")))
    check("Export: kein privater Schluessel, kein voter_key im Export",
          "PRIVATE" not in json.dumps(data) and "voter_key" not in json.dumps(data))

    # Der Umfrage-Schluessel darf nicht nur nicht *benannt* sein - sein Wert
    # darf nirgends auftauchen. Mit ihm laesst sich jeder Eligibility-Eintrag
    # auf sein Pseudonym zurueckrechnen (EIP-T-033, D). Geprueft an einer noch
    # *offenen* Umfrage: Bei POLL ist der Schluessel zu diesem Zeitpunkt schon
    # vernichtet, dort koennte der Export ihn gar nicht mehr verraten.
    from poll_service import POLL_SECRET

    offen = "parallel"
    geheim = service.berechtigung.get_config(POLL_SECRET + offen)
    offener_export = client.get(f"/api/board/{offen}").text
    check("Export: der Umfrage-Schluessel einer laufenden Umfrage steht nicht im Export",
          geheim is not None and geheim not in offener_export)

    # Vergleich ueber die Payloads: POLL ist an dieser Stelle manipuliert, und
    # der Export rechnet Blatt-Hashes nach statt sie zu uebernehmen - beim
    # umgeschriebenen Eintrag weichen nachgerechneter und gespeicherter Hash
    # gerade absichtlich voneinander ab.
    batches = verifikation.batches_from_export(data)
    check("Export: exportierte Eintraege sind die des Boards",
          [e.payload for b in batches for e in b.entries]
          == [e.payload for e in service.board(POLL)])

    path = Path(tempfile.mkdtemp()) / "board.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    key_path = path.parent / "key.pem"
    key_path.write_text(service.poll_pubkey_pem(POLL), encoding="utf-8")

    # POLL ist an dieser Stelle bereits manipuliert (Angriff 2) - das
    # Pruefwerkzeug muss das melden und mit Exit-Code 1 enden.
    code = verifikation.main([str(path), "--pubkey", str(key_path), "--token", "aa" * 32])
    check("Pruefwerkzeug: meldet das manipulierte Board mit Exit-Code 1", code == 1, f"code={code}")

    # Die Umfrage aus dem Parallel-Test ist unversehrt - dort muss dasselbe
    # Werkzeug ohne Befund durchlaufen. Der Schluessel kommt aus *ihrem* Board.
    heil = Path(tempfile.mkdtemp()) / "board.json"
    heil.write_text(json.dumps(client.get("/api/board/parallel").json()), encoding="utf-8")
    heil_key = heil.parent / "key.pem"
    heil_key.write_text(service.poll_pubkey_pem("parallel"), encoding="utf-8")
    code = verifikation.main([str(heil), "--pubkey", str(heil_key)])
    check("Pruefwerkzeug: bestaetigt ein unversehrtes Board mit Exit-Code 0", code == 0, f"code={code}")

    # Derselbe unversehrte Export, aber gegengehalten mit dem Schluessel einer
    # *anderen* Umfrage: Seit EIP-T-069 gehoert ein Schluessel genau einer
    # Umfrage, also ist das ein Befund und kein Durchlauf. Frueher waren beide
    # Boards unter demselben globalen Schluessel - diese Pruefung konnte es
    # damals gar nicht geben.
    code = verifikation.main([str(heil), "--pubkey", str(key_path)])
    check("Pruefwerkzeug: fremder Umfrage-Schluessel wird als Befund gemeldet",
          code == 1, f"code={code}")


def batch_veroeffentlichung() -> None:
    """Puffer, Beleg und Batch-Veroeffentlichung (EIP-ADR-20260728-001, A/B/C).

    Eigene Instanz mit k=2 **Stimmen** (EIP-T-076 - k zaehlt keine Eintraege
    mehr): Eintraege duerfen erst erscheinen, wenn die Mindestmenge erreicht
    ist; der Beleg muss sofort da, offline pruefbar und nach der
    Veroeffentlichung eingeloest sein; beim Schliessen wird der Puffer
    vollstaendig veroeffentlicht, und ein Batch unter der Mindestmenge muss dem
    Betreiber auffallen.
    """
    import json

    from cryptography.hazmat.primitives import serialization
    from board_eintrag import canonical

    batch_app = create_app(
        store_path=Path(tempfile.mkdtemp()) / "batch.sqlite3",
        settings=Settings(admin_token="admin", batch_k=2, antwort_floor_s=0),
    )
    svc = batch_app.state.deps.service
    client = TestClient(batch_app)
    poll = "gebatcht"
    client.post("/api/admin/login", json={"token": "admin"})
    client.post("/api/admin/create",
                json={"poll_id": poll, "question": "Gebuendelt?", "options": ["Ja", "Nein"]})
    check("Batch: POLL_OPEN sofort veroeffentlicht (Betreiberhandlung)",
          len(svc.board_store.veroeffentlichte_batches(poll)) == 1)

    client.post("/api/auth", json={"credential": "testperson60"})
    import secrets as sec
    token = sec.token_bytes(32)
    blinded, inv = blind.blind(token, *svc.poll_params(poll))
    resp = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
    sig = blind.finalize(bytes.fromhex(resp.json()["blind_sig"]), inv, svc.poll_params(poll)[0])
    voted = client.post(f"/api/vote/{poll}",
                        json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja"]}).json()

    # Zwei Eintraege (TOKEN_ISSUED + VOTE), aber erst eine Stimme: Unter der
    # alten Zaehlweise waere hier bereits veroeffentlicht worden - genau der
    # Fehler aus EIP-RPT-20260731-001.
    check("Batch: eine Stimme unter k bleibt im Puffer, auch bei k Eintraegen",
          svc.lookup(poll, token.hex()) is None
          and svc.board_store.pending_stand(poll)[0] == 2
          and len(svc.board_store.veroeffentlichte_batches(poll)) == 1)
    check("Batch: oeffentlicher Teilnahmezaehler zaehlt nur Veroeffentlichtes",
          svc.participation(poll) == 0, str(svc.participation(poll)))
    check("Batch: Antwort traegt den Beleg (Blatt, Batch-Zusage, Signatur)",
          bool(voted.get("leaf_hash")) and isinstance(voted.get("batch"), int)
          and bool(voted.get("beleg_sig")), str(voted)[:100])

    # Beleg offline pruefen: Ed25519 ueber das kanonische JSON der Zusage.
    beleg_pub = serialization.load_pem_public_key(svc.beleg_public_key_pem.encode())
    botschaft = canonical({"batch": voted["batch"], "leaf": voted["leaf_hash"],
                           "poll": poll, "typ": "BELEG"})
    try:
        beleg_pub.verify(bytes.fromhex(voted["beleg_sig"]), botschaft.encode())
        beleg_ok = True
    except Exception:
        beleg_ok = False
    check("Batch: Beleg-Signatur offline pruefbar", beleg_ok)

    # Konsistenzpruefung sieht den Puffer: nichts zu melden, obwohl das Board
    # weniger zeigt als die Ledger wissen.
    check("Batch: Konsistenzpruefung kennt den Puffer",
          not svc.check_consistency(poll), str(svc.check_consistency(poll)))

    # k erreichen: die zweite Person liefert die zweite Stimme -> Veroeffentlichung.
    client2 = TestClient(batch_app)
    client2.post("/api/auth", json={"credential": "testperson61"})
    token2 = sec.token_bytes(32)
    blinded2, inv2 = blind.blind(token2, *svc.poll_params(poll))
    resp2 = client2.post(f"/api/token/{poll}", json={"blinded": blinded2.hex()})
    sig2 = blind.finalize(bytes.fromhex(resp2.json()["blind_sig"]), inv2, svc.poll_params(poll)[0])
    client2.post(f"/api/vote/{poll}",
                 json={"token": token2.hex(), "sig": sig2.hex(), "choices": ["Nein"]})

    check("Batch: bei Erreichen von k wird veroeffentlicht",
          svc.board_store.pending_stand(poll)[0] == 0
          and len(svc.board_store.veroeffentlichte_batches(poll)) == 2)
    check("Batch: Beleg eingeloest - Blatt steht im zugesagten Batch",
          any(e.leaf_hash == voted["leaf_hash"] and e.batch == voted["batch"]
              for e in svc.board(poll)))
    check("Batch: Token nach Veroeffentlichung auffindbar",
          svc.lookup(poll, token.hex()) == ["Ja"])

    # Dritte Person stimmt ab, dann wird geschlossen: der Puffer muss
    # vollstaendig mit hinaus, auch unter k (ADR E3).
    client3 = TestClient(batch_app)
    client3.post("/api/auth", json={"credential": "testperson62"})
    token3 = sec.token_bytes(32)
    blinded3, inv3 = blind.blind(token3, *svc.poll_params(poll))
    resp3 = client3.post(f"/api/token/{poll}", json={"blinded": blinded3.hex()})
    sig3 = blind.finalize(bytes.fromhex(resp3.json()["blind_sig"]), inv3, svc.poll_params(poll)[0])
    client3.post(f"/api/vote/{poll}",
                 json={"token": token3.hex(), "sig": sig3.hex(), "choices": ["Ja"]})
    check("Batch: unter k bleibt der Puffer bestehen",
          svc.board_store.pending_stand(poll)[0] == 2)

    import debug as debug_modul
    vor_dem_schliessen = len(debug_modul.events_gesamt("inconsistency"))

    client.post(f"/api/admin/close/{poll}")
    check("Batch: Schliessen veroeffentlicht den Puffer vollstaendig",
          svc.board_store.pending_stand(poll)[0] == 0)
    check("Batch: Ergebnis nach Schliessen vollstaendig",
          svc.tally(poll) == {"Ja": 2, "Nein": 1}, str(svc.tally(poll)))
    bericht = svc.pruefbericht(poll)
    check("Batch: Batch-Kette nach allem intakt",
          bericht.chain.sound and bericht.accounting.ok)

    # Der letzte Batch traegt eine Stimme statt k - zulaessig, aber eine
    # Abweichung von der Zusage aus KODEX §2. Sie muss dem Betreiber auffallen,
    # nicht nur im Ergebnis stecken (EIP-T-076).
    jetzt = debug_modul.events_gesamt("inconsistency")
    neue = jetzt[: len(jetzt) - vor_dem_schliessen]
    check("Batch: Batch unter der Mindestmenge wird als Befund gemeldet",
          any("Anonymitaetsmenge" in e.message and poll in e.message for e in neue),
          str([e.message[:60] for e in neue]))

    # Die tatsaechliche Stimmenzahl je Batch ist ein Messwert am Board, den auch
    # ein Dritter aus dem Export nachrechnet: POLL_OPEN allein, dann zwei
    # Stimmen, dann der Rest beim Schliessen.
    check("Batch: Stimmen je Batch am Board messbar",
          list(bericht.stimmen_je_batch) == [0, 2, 1], str(bericht.stimmen_je_batch))

    # Export enthaelt die Batch-Parameter - wer den Beleg bekommt, muss wissen,
    # wovon die Sichtbarkeit abhaengt (ADR E3).
    export = client.get(f"/api/board/{poll}").json()
    check("Batch: Export nennt k und Zeitdeckel",
          export.get("batch_k") == 2 and export.get("batch_deckel_s") == 6 * 3600,
          json.dumps({k: export.get(k) for k in ("batch_k", "batch_deckel_s")}))


class _TestZeuge:
    """Ein Zeitzeuge ohne Netz - fuer den Ankertest (EIP-ADR-20260801-002).

    Bezeugt wird, wie bei den echten Zeugen, ``SHA256(rohbytes der Root)``; der
    "Beleg" ist genau dieser Hash. Damit prueft der Test dieselbe Mechanik, die
    im Betrieb greift: Der Vergleich liest den Hash aus dem *Beleg*, nicht aus
    der Datenbankspalte.
    """

    endung = "test"

    def __init__(self, name: str = "testzeuge", stufen: bool = False) -> None:
        self.name = name
        self.titel = f"Testzeuge {name}"
        # stufen=True bildet OpenTimestamps nach: erst Quittung, dann endgueltig.
        self.stufen = stufen
        self.beauftragt: list[str] = []
        self.faellt_aus = False
        self.zeitversatz = timedelta(0)

    def beauftrage(self, root: str) -> "anker_modul.Quittung":
        if self.faellt_aus:
            raise anker_modul.AnkerNichtVerfuegbar("Testzeuge ausgeschaltet")
        self.beauftragt.append(root)
        return anker_modul.Quittung(
            beleg=bytes.fromhex(anker_modul.erwarteter_hash(root)),
            bezeugt_um=datetime.now() + self.zeitversatz,
            endgueltig=not self.stufen,
        )

    def werte_auf(self, beleg: bytes) -> "anker_modul.Quittung | None":
        if self.faellt_aus:
            raise anker_modul.AnkerNichtVerfuegbar("Testzeuge ausgeschaltet")
        return anker_modul.Quittung(
            beleg=beleg, bezeugt_um=datetime.now() + self.zeitversatz, endgueltig=True
        )

    def bezeugter_hash(self, beleg: bytes) -> str | None:
        return beleg.hex() if len(beleg) == 32 else None

    def pruefanleitung(self, basisname: str) -> list[str]:
        return [f"# Testzeuge, kein echter Befehl fuer {basisname}"]


def externer_anker() -> None:
    """Zeitstempel auf die Batch-Root (EIP-ADR-20260801-002, EIP-T-006).

    Sechs Zusagen, und die dritte ist der eigentliche Zweck:

    1. Jeder veroeffentlichte Batch wird bei jedem Zeugen beauftragt - ohne
       Netzaufruf im Veroeffentlichungspfad.
    2. Der Durchlauf der Hintergrundaufgabe holt die Belege.
    3. Wird das Board **umgeschrieben und die Kette neu gerechnet**, faellt das
       am Anker auf. Genau das kann die Kettenpruefung nicht (Angriffsdemo
       "Board umschreiben").
    4. Ein zweistufiger Zeuge (OpenTimestamps-Muster) wird aufgewertet.
    5. Ein ausgefallener Dienst haelt die Veroeffentlichung nicht auf und wird
       nach der Versuchsgrenze zum Befund.
    6. Zeugen, die dieselbe Root verschieden datieren, sind ein Befund.
    """
    import board_eintrag as be

    zeuge = _TestZeuge()
    zweistufig = _TestZeuge("zweistufig", stufen=True)
    anker_app = create_app(
        store_path=Path(tempfile.mkdtemp()) / "anker.sqlite3",
        settings=Settings(admin_token="admin", batch_k=2, antwort_floor_s=0),
    )
    svc = anker_app.state.deps.service
    svc.zeugen = {z.name: z for z in (zeuge, zweistufig)}
    # Ohne Wartezeit zwischen den Anlaeufen - im Betrieb sind es Minuten, damit
    # die Instanz nicht im Minutentakt an fremden Gratis-Diensten klopft; hier
    # sollen zwei Durchlaeufe hintereinander auch zwei Versuche sein.
    svc.anker_wiederholung_s = 0
    svc.anker_aufwertung_s = 0
    client = TestClient(anker_app)
    poll = "verankert"
    client.post("/api/admin/login", json={"token": "admin"})
    client.post("/api/admin/create",
                json={"poll_id": poll, "question": "Verankert?", "options": ["Ja", "Nein"]})

    # 1 - POLL_OPEN ist veroeffentlicht, also beauftragt, aber noch ohne Beleg.
    zeilen = svc.anker_je_batch(poll).get(0, [])
    check("Anker: Veroeffentlichung beauftragt jeden Zeugen",
          len(zeilen) == 2 and all(z.zustand == "ausstehend" for z in zeilen),
          str([(z.dienst, z.zustand) for z in zeilen]))
    check("Anker: Veroeffentlichungspfad ruft keinen Dienst auf",
          zeuge.beauftragt == [], str(zeuge.beauftragt))

    # 2 - Erst die Hintergrundaufgabe geht ans Netz.
    svc.arbeite_anker_ab()
    zeilen = {z.dienst: z for z in svc.anker_je_batch(poll)[0]}
    root0 = svc.board_store.veroeffentlichte_batches(poll)[0].batch_root
    check("Anker: Durchlauf holt den Beleg auf batch_root(0)",
          zeilen["testzeuge"].zustand == "endgueltig"
          and zeuge.beauftragt == [root0],
          str(zeilen["testzeuge"].zustand))
    check("Anker: zweistufiger Zeuge ist erst quittiert, nicht endgueltig",
          zeilen["zweistufig"].zustand == "bezeugt")
    check("Anker: keine Befunde bei unveraendertem Board",
          svc.pruefe_anker(poll) == [], str(svc.pruefe_anker(poll)))

    # 4 - Aufwertung (OpenTimestamps-Muster).
    svc.arbeite_anker_ab()
    check("Anker: zweiter Durchlauf wertet die Quittung zur Bezeugung auf",
          svc.anker_je_batch(poll)[0][1].zustand == "endgueltig"
          or {z.dienst: z.zustand for z in svc.anker_je_batch(poll)[0]}["zweistufig"]
          == "endgueltig")

    # 3 - Der Kern: Board umschreiben *mit* neu gerechneter Kette.
    #     Die Kettenpruefung sieht danach nichts. Der Anker schon.
    with svc.board_store._lock:  # bewusst am Store vorbei - das ist der Angriff
        alt = svc.board_store._conn.execute(
            "SELECT leaf_hash, payload FROM board WHERE poll_id = ? AND batch = 0", (poll,)
        ).fetchone()
        neu = json.loads(alt["payload"])
        neu["question"] = "Manipuliert?"
        neu_payload = be.canonical(neu)
        neu_hash = be.leaf_hash(neu_payload)
        svc.board_store._conn.execute(
            "UPDATE board SET leaf_hash = ?, payload = ? WHERE poll_id = ? AND leaf_hash = ?",
            (neu_hash, neu_payload, poll, alt["leaf_hash"]),
        )
        # Und die Pruefsummen hinterher, wie es ein Betreiber taete:
        neue_root = be.merkle_root([neu_hash])
        svc.board_store._conn.execute(
            "UPDATE batches SET merkle_root = ?, batch_root = ? WHERE poll_id = ? AND batch = 0",
            (neue_root, be.batch_root(neue_root, be.GENESIS), poll),
        )
        svc.board_store._conn.commit()
    svc._letzte_pruefung.pop(poll, None)
    bericht = svc.pruefbericht(poll)
    befunde = svc.pruefe_anker(poll, bericht)
    check("Anker: umgeschriebenes Board mit neu gerechneter Kette faellt nicht "
          "an der Kette auf", bericht.chain.ok)
    check("Anker: ... aber am Zeitstempel", len(befunde) >= 1 and
          any("andere Root" in b for b in befunde), str(befunde))
    check("Anker: der Befund steht auf der oeffentlichen Board-Seite",
          "passen nicht zu diesem Board" in client.get(f"/board/{poll}").text)

    # 5 - Ausgefallener Dienst: Veroeffentlichung laeuft weiter, Befund kommt.
    #     Eigene Umfrage, weil die erste eben absichtlich beschaedigt wurde -
    #     dort gibt es zu Recht keine Token mehr.
    import secrets as sec

    poll2 = "verankert2"
    ausfall = _TestZeuge("ausfall")
    ausfall.faellt_aus = True
    svc.zeugen = {"ausfall": ausfall}
    svc.anker_max_versuche = 2
    client.post("/api/admin/create",
                json={"poll_id": poll2, "question": "Und ohne Dienst?", "options": ["Ja", "Nein"]})
    client.post("/api/auth", json={"credential": "testperson71"})
    tok = sec.token_bytes(32)
    blinded, inv = blind.blind(tok, *svc.poll_params(poll2))
    resp = client.post(f"/api/token/{poll2}", json={"blinded": blinded.hex()})
    sig = blind.finalize(bytes.fromhex(resp.json()["blind_sig"]), inv, svc.poll_params(poll2)[0])
    gestimmt = client.post(f"/api/vote/{poll2}",
                           json={"token": tok.hex(), "sig": sig.hex(), "choices": ["Ja"]})
    check("Anker: Stimmabgabe haengt nicht am Anker-Dienst", gestimmt.status_code == 200)
    for _ in range(3):
        svc.arbeite_anker_ab()
    inkonsistenzen = [e.message for e in log_board.events("inconsistency")]
    check("Anker: aufgegebener Auftrag wird als Inkonsistenz gemeldet",
          any("bleibt ohne ausfall-Anker" in m for m in inkonsistenzen),
          str(inkonsistenzen[:2]))

    # 6 - Zwei Zeugen, die dieselbe Root verschieden datieren.
    a, b = _TestZeuge("frueh"), _TestZeuge("spaet")
    b.zeitversatz = timedelta(hours=3)
    svc.zeugen = {"frueh": a, "spaet": b}
    svc.anker_max_versuche = 5
    svc.close_poll(poll2)
    for _ in range(2):
        svc.arbeite_anker_ab()
    befunde = svc.pruefe_anker(poll2)
    check("Anker: auseinanderlaufende Datierung ist ein Befund",
          any("auseinander" in x for x in befunde), str(befunde))


def sitzungstrennung() -> None:
    """Phase B ohne Sitzungskontext (EIP-T-033, Baustein F).

    Der Abstimm-Request braucht keine Identitaet - das Token ist die ganze
    Berechtigung. Drei Zusagen werden geprueft: Eine Stimme ohne Cookie wird
    angenommen und erzeugt keinen Befund; eine Stimme, die trotzdem das
    Session-Cookie mitbringt (Altclient), zaehlt, landet aber als Befund im
    Debug-Modul; und die Phasen-Routen antworten nie schneller als der
    Antwort-Floor, damit die Dauer keine Auskunft gibt. Dazu: keine der
    Phase-B-Antworten setzt ein Cookie.
    """
    import secrets as sec
    import time as zeit

    import debug as debug_modul

    floor = 0.2
    eigen = create_app(
        store_path=Path(tempfile.mkdtemp()) / "sitzung.sqlite3",
        settings=Settings(admin_token="admin", batch_k=1, antwort_floor_s=floor),
    )
    svc = eigen.state.deps.service
    poll = "sitzung"
    admin = TestClient(eigen)
    admin.post("/api/admin/login", json={"token": "admin"})
    admin.post("/api/admin/create",
               json={"poll_id": poll, "question": "Getrennt?", "options": ["Ja", "Nein"]})

    def hole_token(credential: str) -> tuple[TestClient, bytes, bytes, float]:
        client = TestClient(eigen)
        client.post("/api/auth", json={"credential": credential})
        token = sec.token_bytes(32)
        blinded, inv = blind.blind(token, *svc.poll_params(poll))
        start = zeit.monotonic()
        resp = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
        dauer = zeit.monotonic() - start
        sig = blind.finalize(bytes.fromhex(resp.json()["blind_sig"]), inv, svc.poll_params(poll)[0])
        return client, token, sig, dauer

    # Regulaerer Weg: Phase A angemeldet, Phase B auf einem Client ohne
    # Cookie-Speicher - das Gegenstueck zu credentials "omit" in ballot.js.
    _, token, sig, dauer_a = hole_token("testperson70")
    vorher = debug_modul.counts_gesamt()["inconsistency"]
    anon = TestClient(eigen)
    start = zeit.monotonic()
    voted = anon.post(f"/api/vote/{poll}",
                      json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja"]})
    dauer_b = zeit.monotonic() - start
    check("Sitzungstrennung: Stimme ohne Sitzungskontext angenommen",
          voted.status_code == 200, str(voted.json())[:80])
    check("Sitzungstrennung: sauberer Abstimm-Request erzeugt keinen Befund",
          debug_modul.counts_gesamt()["inconsistency"] == vorher)
    check("Sitzungstrennung: Abstimm-Antwort setzt kein Cookie",
          "set-cookie" not in voted.headers)
    board = anon.get(f"/board/{poll}")
    check("Sitzungstrennung: Board-Seite setzt kein Cookie",
          board.status_code == 200 and "set-cookie" not in board.headers)
    check("Sitzungstrennung: Antwort-Floor auf beiden Phasen-Routen",
          dauer_a >= floor * 0.95 and dauer_b >= floor * 0.95,
          f"A={dauer_a:.3f}s B={dauer_b:.3f}s floor={floor}s")

    # Altclient-Fall: Der angemeldete Client stimmt selbst ab, das
    # Session-Cookie faehrt mit. Die Stimme zaehlt (die Verkettung ist mit dem
    # Empfang passiert, eine Abweisung schuetzte nichts mehr), aber der
    # Betreiber sieht den Befund statt einer stillen Duldung.
    client2, token2, sig2, _ = hole_token("testperson71")
    voted2 = client2.post(f"/api/vote/{poll}",
                          json={"token": token2.hex(), "sig": sig2.hex(), "choices": ["Nein"]})
    befunde = [e for e in debug_modul.events_gesamt("inconsistency")
               if e.category == "unverkettbarkeit" and e.detail.get("poll") == poll]
    check("Sitzungstrennung: mitgesandtes Session-Cookie wird als Befund gemeldet",
          voted2.status_code == 200 and len(befunde) == 1,
          f"status={voted2.status_code} befunde={len(befunde)}")
    check("Sitzungstrennung: Befund benennt, was mitkam",
          bool(befunde) and "eidpoll_session" in befunde[0].detail.get("mitgesandt", ""),
          str(befunde[0].detail if befunde else {}))

    # Verbindungsebene (EIP-T-034): Eine Verbindung, die eine Identitaet
    # getragen hat, endet mit ihrer Antwort - sonst laufen Phase A und Phase B
    # ueber denselben Socket und sind verkettet, ohne dass ein Feld mitfaehrt.
    # Geprueft wird die Anweisung im Header, nicht der Socket: TestClient
    # spricht ASGI, da gibt es keine TCP-Verbindung, die sich schliessen
    # liesse. Dass uvicorn "connection: close" befolgt, ist dessen Zusage;
    # unsere ist, sie zu geben.
    angemeldet = TestClient(eigen)
    angemeldet.post("/api/auth", json={"credential": "testperson72"})
    seite = angemeldet.get(f"/poll/{poll}")
    phase_a = angemeldet.post(f"/api/token/{poll}", json={"blinded": "zz"})
    anonym_seite = anon.get(f"/board/{poll}")
    check("Verbindungsebene: Phase-Routen schliessen die Verbindung",
          phase_a.headers.get("connection") == "close"
          and voted.headers.get("connection") == "close",
          f"A={phase_a.headers.get('connection')} B={voted.headers.get('connection')}")
    check("Verbindungsebene: Seite mit Sitzungs-Cookie schliesst die Verbindung",
          seite.headers.get("connection") == "close", str(seite.headers.get("connection")))
    check("Verbindungsebene: anonymer Abruf bleibt wiederverwendbar",
          anonym_seite.headers.get("connection") != "close",
          "eine Verbindung ohne Identitaet darf eine Stimme tragen")

    # Kanal-Blindheit (EIP-T-034, Akzeptanzkriterium 3): Wird der anonyme Kanal
    # eine Option neben dem normalen Weg, ist die Kanalwahl selbst ein Merkmal -
    # und zwar genau dann, wenn der Server sie festhaelt. Heute haelt er sie
    # nicht fest; dieser Test haelt es so. Gesucht wird nach dem, was den Kanal
    # verriete: Absender-IP aus der Proxy-Kette und der angesprochene Hostname
    # (eine Onion-Adresse steht im Host-Header und sonst nirgends).
    kanal = TestClient(eigen)
    kanal.post("/api/auth", json={"credential": "testperson74"})
    kopfzeilen = {"x-forwarded-for": "203.0.113.77", "host": "kanaltest.onion"}
    kanal.post(f"/api/token/{poll}", json={"blinded": "zz"}, headers=kopfzeilen)
    anon.post(f"/api/vote/{poll}", json={"token": "zz", "sig": "zz", "choices": ["Ja"]},
              headers=kopfzeilen)
    kanal_abzug = "\n".join(
        f"{e.category} {e.message} {e.detail}" for e in debug_modul.events_gesamt("all"))
    check("Kanal-Blindheit: weder Absender-IP noch Zielhost im Debug-Modul",
          "203.0.113.77" not in kanal_abzug and "kanaltest.onion" not in kanal_abzug,
          "sonst unterscheidet der Betreiber Onion- von Normalweg-Teilnehmenden")


def _verzeichnis_bytes(verzeichnis: Path) -> bytes:
    """Alle Dateien unter ``verzeichnis`` als rohe Bytes, rekursiv.

    Bewusst das Verzeichnis und keine Dateiliste: Bis EIP-T-041 las der Abzug
    die drei Pfade, die er erwartete - Datenbank, ``-wal``, ``-shm``. Genau das
    hat der Fehler ausgenutzt, den dieselbe Durchsicht gefunden hat: Neben der
    Datenbank lagen zwei liegengebliebene Kopien aus Testlaeufen, eine davon mit
    dem laengst vernichteten ``server_secret``. Ein Datenleck nimmt das
    Verzeichnis mit, nicht die Namen, die im Test stehen.
    """
    return b"".join(
        p.read_bytes() for p in sorted(verzeichnis.rglob("*")) if p.is_file()
    )


def datenabzug_nach_schluss() -> None:
    """Abzug aus Datenbank und Log gibt nach Umfrage-Schluss keine Zuordnung her
    (EIP-T-041, Akzeptanzkriterien 3 und 5).

    Nicht als Zusicherung, sondern als Abzug: eine Umfrage vollstaendig
    durchlaufen, schliessen, und dann alles auslesen, was ein Datenleck oder
    eine Beschlagnahme in die Hand bekaeme - die SQLite-Datei als SQL-Abzug
    *und* **jede Datei im Datenverzeichnis** als rohe Bytes (ein DELETE gibt
    Seiten nur frei), dazu den vollstaendigen Inhalt des Debug-Moduls. Darin
    wird nach genau dem gesucht, was Person -> Stimme herstellen wuerde.

    Der Test prueft Abwesenheit. Das ist so viel wert wie die Liste dessen,
    wonach er sucht - deshalb steht jede Suche mit ihrer Begruendung hier und
    nicht als stille Zeichenkette. Und weil eine Suche, die nichts findet, noch
    nicht funktioniert haben muss, stellt der letzte Abschnitt eine
    liegengebliebene Sicherungskopie nach und verlangt, dass der Abzug sie
    findet.
    """
    import sqlite3

    from auth import STUB_PREFIX
    from debug import TEILNAHME
    import debug as debug_modul
    from poll_service import POLL_KEY, POLL_SECRET

    pfad = Path(tempfile.mkdtemp()) / "abzug.sqlite3"
    eigen = create_app(
        store_path=pfad,
        settings=Settings(admin_token="admin", batch_k=1, antwort_floor_s=0),
    )
    svc = eigen.state.deps.service
    poll = "abzug"
    admin = TestClient(eigen)
    admin.post("/api/admin/login", json={"token": "admin"})
    admin.post("/api/admin/create",
               json={"poll_id": poll, "question": "Abziehbar?", "options": ["Ja", "Nein"]})

    codes = ["testperson50", "testperson51", "testperson52"]
    pseudonyme = [eigen.state.deps.authenticator.authenticate(c) for c in codes]
    voter_keys = [svc.voter_key(p, poll) for p in pseudonyme]
    geheim = svc.berechtigung.get_config(POLL_SECRET + poll) or ""
    signierschluessel = svc.berechtigung.get_config(POLL_KEY + poll) or ""

    for i, code in enumerate(codes):
        client = TestClient(eigen)
        client.post("/api/auth", json={"credential": code})
        token = __import__("secrets").token_bytes(32)
        blinded, inv = blind.blind(token, *svc.poll_params(poll))
        resp = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
        sig = blind.finalize(bytes.fromhex(resp.json()["blind_sig"]), inv, svc.poll_params(poll)[0])
        anonym = TestClient(eigen)
        anonym.post(f"/api/vote/{poll}",
                    json={"token": token.hex(), "sig": sig.hex(),
                          "choices": ["Ja" if i else "Nein"]})

    # Zustand *vor* dem Schliessen, solange die Schluessel noch da sind. Er
    # dient weiter unten als Probe: genau so sieht eine Sicherungskopie aus, die
    # jemand vor dem Schliessen gezogen und danach vergessen hat.
    vor_schluss = {p.name: p.read_bytes() for p in pfad.parent.iterdir() if p.is_file()}

    admin.post(f"/api/admin/close/{poll}")

    # -- Der Abzug ---------------------------------------------------------
    # Beide Dateien (Baustein G): Wer das Datenverzeichnis mitnimmt, hat Board-
    # und Berechtigungsseite - der Abzug muss also ueber beide gehen, sonst
    # pruefte er nur die halbe Beute.
    sql_teile = []
    for db in (pfad, svc.berechtigung.path):
        zweite = sqlite3.connect(db)
        sql_teile.append("\n".join(zweite.iterdump()))
        zweite.close()
    sql_abzug = "\n".join(sql_teile)
    roh = _verzeichnis_bytes(pfad.parent)
    debug_abzug = "\n".join(
        f"{e.ts} {e.level} {e.category} {e.message} {e.detail}" for e in debug_modul.events_gesamt("all")
    ) + "\n" + "\n".join(
        f"{z.stunde} {z.level} {z.category} {z.message} {z.detail} {z.anzahl}"
        for z in debug_modul.teilnahme_gesamt()
    )

    # -- Identitaet: darf nirgends stehen ----------------------------------
    check("Abzug: kein Pseudonym in der Datenbank",
          STUB_PREFIX not in sql_abzug and STUB_PREFIX.encode() not in roh)
    check("Abzug: kein Pseudonym im Debug-Modul", STUB_PREFIX not in debug_abzug)
    check("Abzug: kein Zugangscode irgendwo im Abzug",
          not any(c in sql_abzug or c.encode() in roh or c in debug_abzug for c in codes))

    # -- Rueckrechenbarkeit: der Schluessel ist wirklich weg, nicht nur
    #    aus der Tabelle geloescht (Store.vernichte_config, EIP-T-033 D) ----
    check("Abzug: Umfrage-Schluessel nicht mehr in der Datei",
          bool(geheim) and geheim not in sql_abzug and geheim.encode() not in roh)
    check("Abzug: Signaturschluessel nicht mehr in der Datei",
          bool(signierschluessel) and signierschluessel not in sql_abzug)

    # -- Verkettung: Voter-Key und Stimme duerfen sich nicht beruehren -----
    # Die Voter-Keys *stehen* im Abzug - der Eligibility-Ledger traegt sie, und
    # ohne ihn gaebe es keine Abrechnung nach §9. Der Punkt ist, dass keine
    # Zeile sie mit einem Board-Eintrag oder einem verbrauchten Token
    # zusammenbringt.
    leaf_hashes = [e.leaf_hash for e in svc.board(poll)]
    spent = [r[0] for r in sqlite3.connect(pfad).execute(
        "SELECT token_hex FROM spent WHERE poll_id = ?", (poll,)).fetchall()]
    check("Abzug: Voter-Keys stehen im Ledger (sonst pruefte der Test nichts)",
          all(k in sql_abzug for k in voter_keys))
    gemeinsam = [
        zeile for zeile in sql_abzug.splitlines()
        if any(k in zeile for k in voter_keys)
        and any(w in zeile for w in leaf_hashes + spent)
    ]
    check("Abzug: keine Zeile nennt Voter-Key und Stimme zusammen",
          not gemeinsam, gemeinsam[0][:120] if gemeinsam else "")

    # -- Zeit: kein Teilnahmevorgang mit Sekundenstempel -------------------
    # Der eigentliche Fund von EIP-T-041. Vorher lagen Token-Ausgabe und
    # Stimmabgabe sekundengenau untereinander im Debug-Modul; wer die Seite
    # offen hatte, konnte beides ueber die Zeit zusammenbringen.
    im_strom = [e for e in debug_modul.events_gesamt("all") if e.category in TEILNAHME]
    check("Abzug: kein Teilnahmevorgang im Ereignisstrom",
          not im_strom, im_strom[0].message[:80] if im_strom else "")
    check("Abzug: Teilnahmezaehler nur stundengenau",
          all(z.stunde.endswith(":00") for z in debug_modul.teilnahme_gesamt()))
    check("Abzug: Teilnahmezaehler haben die Vorgaenge trotzdem erfasst",
          sum(z.anzahl for z in debug_modul.teilnahme_gesamt()
              if z.category == "phase-b" and z.detail.get("poll") == poll) == len(codes))

    # -- Zeit in der Datenbank: nur der Batch, nicht der Eintrag ------------
    check("Abzug: kein Zeitstempel je Board-Eintrag",
          "published" in sql_abzug and all(
              "pending_since" not in zeile for zeile in sql_abzug.splitlines()))

    # -- Probe: faengt der Abzug eine liegengebliebene Kopie? --------------
    # Alle Pruefungen oben suchen Abwesenheit. Eine Suche, die nichts findet,
    # ist nur so viel wert wie der Beweis, dass sie etwas finden *koennte* -
    # sonst haette der Wechsel auf das ganze Verzeichnis (EIP-T-041,
    # Akzeptanzkriterium 3) keine nachweisbare Wirkung.
    #
    # Deshalb der reale Fall, nachgestellt: eine Kopie des Datenverzeichnisses
    # von *vor* dem Schliessen, unter einem Namen, den keine feste Dateiliste
    # kennt. So lag ``data.backup.<zeit>/`` am 2026-07-31 auf der
    # Entwicklungsmaschine - mit einem Schluessel, den die Datenbank daneben
    # laengst vernichtet hatte.
    check("Probe: die Kopie traegt den Schluessel wirklich (sonst prueft die Probe nichts)",
          any(geheim.encode() in b for b in vor_schluss.values()))

    probe = pfad.parent / "data.backup.probe"
    probe.mkdir()
    for name, inhalt in vor_schluss.items():
        (probe / name).write_bytes(inhalt)
    try:
        check("Probe: eine liegengebliebene Kopie faellt im Abzug auf",
              geheim.encode() in _verzeichnis_bytes(pfad.parent))
    finally:
        shutil.rmtree(probe)

    check("Probe: nach dem Aufraeumen ist der Schluessel wieder fort",
          geheim.encode() not in _verzeichnis_bytes(pfad.parent))


def sicherungskopie_ohne_geheimnisse() -> None:
    """Eine Kopie nach ``Store.kopiere_ohne_geheimnisse`` traegt keinen Schluessel
    (EIP-T-067, Akzeptanzkriterium 2).

    Der Test spielt genau den Fall nach, der das Ticket ausgeloest hat, nur
    richtigherum: eine Kopie einer **offenen** Umfrage - also zu dem Zeitpunkt,
    an dem alle Schluessel noch da sind und eine gedankenlose Dateikopie am
    meisten anrichtet.

    Geprueft wird beides, was eine Kopie taugen laesst: dass die Geheimnisse
    fehlen *und* dass die Ledger vollstaendig sind. Eine Kopie, die nichts mehr
    enthaelt, waere trivial sicher und nutzlos.
    """
    import sqlite3

    from poll_service import POLL_KEY, POLL_SECRET

    pfad = Path(tempfile.mkdtemp()) / "kopie-quelle.sqlite3"
    eigen = create_app(
        store_path=pfad,
        settings=Settings(admin_token="admin", batch_k=1, antwort_floor_s=0),
    )
    svc = eigen.state.deps.service
    poll = "kopie"
    admin = TestClient(eigen)
    admin.post("/api/admin/login", json={"token": "admin"})
    admin.post("/api/admin/create",
               json={"poll_id": poll, "question": "Kopierbar?", "options": ["Ja", "Nein"]})

    client = TestClient(eigen)
    client.post("/api/auth", json={"credential": "testperson60"})
    token = __import__("secrets").token_bytes(32)
    blinded, inv = blind.blind(token, *svc.poll_params(poll))
    resp = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
    sig = blind.finalize(bytes.fromhex(resp.json()["blind_sig"]), inv, svc.poll_params(poll)[0])
    anonym = TestClient(eigen)
    anonym.post(f"/api/vote/{poll}",
                json={"token": token.hex(), "sig": sig.hex(), "choices": ["Ja"]})

    geheimnisse = {
        "poll_secret": svc.berechtigung.get_config(POLL_SECRET + poll) or "",
        "poll_key": svc.berechtigung.get_config(POLL_KEY + poll) or "",
        "cookie_secret": svc.berechtigung.get_config("cookie_secret") or "",
        "beleg_key": svc.board_store.get_config("beleg_key_pem") or "",
    }
    check("Kopie: die Quelle fuehrt die Schluessel wirklich (sonst prueft der Test nichts)",
          all(geheimnisse.values()), str({k: bool(v) for k, v in geheimnisse.items()}))

    # Seit Baustein G sind es zwei Dateien - beide Kopien in dasselbe
    # Verzeichnis, wie backup.py es tut.
    ziel_verzeichnis = Path(tempfile.mkdtemp()) / "backup"
    ziel_board = ziel_verzeichnis / "board-ohne-geheimnisse.sqlite3"
    ziel_berechtigung = ziel_verzeichnis / "berechtigung-ohne-geheimnisse.sqlite3"
    entfernt_board = svc.board_store.kopiere_ohne_geheimnisse(ziel_board)
    entfernt_berechtigung = svc.berechtigung.kopiere_ohne_geheimnisse(ziel_berechtigung)

    check("Kopie: nennt die entfernten Konfigurationswerte (je Seite)",
          set(entfernt_berechtigung) >= {POLL_SECRET + poll, POLL_KEY + poll, "cookie_secret"}
          and "beleg_key_pem" in entfernt_board,
          f"board={entfernt_board} berechtigung={entfernt_berechtigung}")

    # Der Abzug wieder als rohe Bytes ueber das ganze Verzeichnis, nicht ueber
    # die Tabelle: ein DELETE gaebe die Seite nur frei (V-003).
    roh = _verzeichnis_bytes(ziel_verzeichnis)
    for name, wert in geheimnisse.items():
        check(f"Kopie: kein {name} in den Kopien", wert.encode() not in roh)

    check("Kopie: kein WAL neben den Kopien liegengeblieben",
          sorted(p.name for p in ziel_verzeichnis.iterdir())
          == sorted([ziel_board.name, ziel_berechtigung.name]),
          str(sorted(p.name for p in ziel_verzeichnis.iterdir())))

    # ... und trotzdem brauchbar: die Kopie ist der Grund, sie zu haben.
    def _zeilen(db: Path, tabellen: tuple[str, ...]) -> dict[str, int]:
        conn = sqlite3.connect(db)
        try:
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tabellen}
        finally:
            conn.close()

    board_tabellen = ("spent", "board", "batches", "polls")
    zeilen = _zeilen(ziel_board, board_tabellen)
    zeilen["eligibility"] = _zeilen(ziel_berechtigung, ("eligibility",))["eligibility"]
    original = _zeilen(pfad, board_tabellen)
    original["eligibility"] = _zeilen(svc.berechtigung.path, ("eligibility",))["eligibility"]
    check("Kopie: Ledger, Board und Batches sind vollstaendig",
          zeilen == original and zeilen["board"] > 0, f"{zeilen} vs {original}")

    # Eine bestehende Datei wird nicht ueberschrieben - sonst bliebe ihr alter
    # Inhalt im Freispeicher stehen, und die Kopie waere schlechter als keine.
    try:
        svc.board_store.kopiere_ohne_geheimnisse(ziel_board)
        check("Kopie: bestehende Datei wird nicht ueberschrieben", False)
    except FileExistsError as exc:
        check("Kopie: bestehende Datei wird nicht ueberschrieben", True, str(exc)[:60])

    shutil.rmtree(ziel_verzeichnis)


def offenlegungsseiten() -> None:
    """Kodex, Verstossprotokoll und Transparenzbericht sind von aussen erreichbar.

    KODEX Paragraf 10 verlangt genau das (EIP-T-063): Eine Selbstbindung, die
    nur der Betreiber lesen kann, ist keine. Der Test prueft die Erreichbarkeit
    ohne Anmeldung - der urspruengliche Fehler in V-001 war, den Stand am
    falschen Ort zu pruefen.
    """
    besucher = TestClient(app)  # bewusst ohne Login und ohne Admin-Cookie

    seiten = {
        "/manifest": "Manifest",
        "/kodex": "Kodex",
        "/kodex/protokoll": "Verstoßprotokoll",
        "/transparenz": "Transparenzbericht",
    }
    for pfad, erwartet in seiten.items():
        antwort = besucher.get(pfad)
        check(f"Offenlegung: {pfad} ist ohne Anmeldung erreichbar",
              antwort.status_code == 200 and erwartet in antwort.text,
              f"status={antwort.status_code}")

    kodex = besucher.get("/kodex").text
    check("Offenlegung: Kodex nennt die Schuldenuebersicht",
          "Schuldenübersicht" in kodex)
    check("Offenlegung: Kodex-Seite verlinkt das Protokoll",
          'href="/kodex/protokoll"' in kodex)
    check("Offenlegung: Kodex ist aus der Hauptnavigation erreichbar",
          'href="/kodex"' in besucher.get("/").text)

    # Unaufgeloeste Wikilinks waeren ein Verweis, den ein Besucher fuer
    # aufloesbar haelt und der ins Leere zeigt - das erledigt der Sync im
    # Elternordner, hier wird sein Ergebnis geprueft.
    for pfad in seiten:
        check(f"Offenlegung: {pfad} ohne unaufgeloeste [[Wikilinks]]",
              "[[" not in besucher.get(pfad).text)

    protokoll = besucher.get("/kodex/protokoll").text
    check("Offenlegung: Verstossprotokoll traegt die bisherigen Eintraege",
          "V-001" in protokoll and "V-002" in protokoll)


def ausgelieferter_stand() -> None:
    """/version weist den Stand aus, und Abweichungen landen im Debug-Modul.

    KODEX Paragraf 20, EIP-T-074. Geprueft wird beides, was die Auskunft
    tragen muss: Sie ist ohne Anmeldung erreichbar - wer die Instanz prueft,
    hat kein Admin-Token -, und sie nennt ihre eigene Grenze, statt
    Uebereinstimmung zu behaupten (Paragraf 4).
    """
    import stand as stand_modul

    besucher = TestClient(app)  # bewusst ohne Login
    antwort = besucher.get("/version")
    check("Stand: /version ist ohne Anmeldung erreichbar",
          antwort.status_code == 200, f"status={antwort.status_code}")
    daten = antwort.json()
    check("Stand: /version nennt Commit und Dateihash",
          daten.get("commit") and daten.get("treehash", "").startswith("sha256:"),
          str(daten)[:80])
    check("Stand: /version bringt die Nachrechenvorschrift mit (Paragraf 20)",
          "git ls-files" in daten.get("nachrechnen", ""))
    check("Stand: /version nennt seine Grenze statt Uebereinstimmung zu behaupten",
          "Selbstauskunft" in daten.get("grenze", ""))

    # Der Dateihash ist eine Messung, keine Angabe: Eine geaenderte
    # ausgelieferte Datei muss ihn bewegen, sonst misst er nichts.
    verzeichnis = Path(tempfile.mkdtemp())
    (verzeichnis / "static").mkdir()
    (verzeichnis / "static" / "blind.js").write_text("// Blinding\n")
    vorher, anzahl = stand_modul.treehash(verzeichnis)
    check("Stand: Dateihash zaehlt die ausgelieferten Dateien", anzahl == 1, f"n={anzahl}")
    (verzeichnis / "static" / "blind.js").write_text("// Blinding, aber anders\n")
    nachher, _ = stand_modul.treehash(verzeichnis)
    check("Stand: geaenderter Client-Code aendert den Dateihash", vorher != nachher)

    # Was .gitignore ausnimmt, darf den Hash nicht bewegen - sonst meldete
    # jede Datenbankschreibung eine Abweichung und niemand sieht mehr hin.
    (verzeichnis / "data").mkdir()
    (verzeichnis / "data" / "eidpoll.sqlite3").write_text("x")
    (verzeichnis / "__pycache__").mkdir()
    (verzeichnis / "__pycache__" / "web.cpython-312.pyc").write_text("x")
    check("Stand: Laufzeitdaten und Bytecode bleiben ausserhalb des Hashs",
          stand_modul.treehash(verzeichnis)[0] == nachher)

    # Ein Bericht, der einen anderen Stand geprueft hat, sagt ueber den
    # laufenden nichts - das war der Kern von V-001: eine Pruefung, die
    # stattgefunden hat, aber nicht am ausgelieferten Stand.
    bericht = verzeichnis / "auslieferung.json"
    bericht.write_text(json.dumps({
        "zeit": "2026-01-01 00:00",
        "ergebnis": "gleich",
        "arbeitsbaum": {"treehash": "sha256:einanderer"},
        "befunde": [],
    }), encoding="utf-8")
    ergebnis = stand_modul.abgleich(Path(__file__).parent, bericht_pfad=bericht)
    check("Stand: Abgleich eines fremden Standes gilt nicht fuer den laufenden",
          any("anderen Stand" in h for h in ergebnis.hinweise), str(ergebnis.hinweise)[:90])

    gemeldet = json.dumps({
        "zeit": "2026-01-01 00:00",
        "ergebnis": "Abweichung",
        "arbeitsbaum": {"treehash": "sha256:egal"},
        "befunde": ["Die Instanz liefert nicht origin/prototype aus"],
    })
    bericht.write_text(gemeldet, encoding="utf-8")
    mit_befund = stand_modul.abgleich(Path(__file__).parent, bericht_pfad=bericht)
    check("Stand: gemeldete Abweichung erscheint als Befund, nicht als Hinweis",
          any("liefert nicht" in b for b in mit_befund.befunde), str(mit_befund.befunde)[:90])

    # Und zwar dort, wo bei diesem Projekt hingesehen wird: als Inkonsistenz
    # im Debug-Modul, nicht nur im Terminal des Betreibers.
    protokoll = DebugLog()
    stand_modul._zuletzt_gemeldet = None
    stand_modul.melde(protokoll, Path(__file__).parent, bericht_pfad=bericht)
    inkonsistenzen = [e for e in protokoll.events() if e.level == "inconsistency"]
    check("Stand: Abweichung steht im Debug-Modul als Inkonsistenz",
          any("liefert nicht" in e.message for e in inkonsistenzen),
          f"{len(inkonsistenzen)} Inkonsistenz(en)")
    check("Stand: Abweichung liegt unter einer eigenen Kategorie",
          all(e.category == "auslieferung" for e in inkonsistenzen))
    stand_modul._zuletzt_gemeldet = None


def nachrechenbarer_client() -> None:
    """Der Code im Browser laesst sich gegen das Repository halten (EIP-T-007).

    Der Unterschied zu ``ausgelieferter_stand`` ist der, auf den es bei
    Paragraf 20 ankommt: Dort beantwortet der Server eine Frage ueber sich
    selbst, hier gibt er eine Liste heraus, die man gegen etwas halten kann,
    das nicht von ihm stammt. Geprueft wird deshalb nicht, dass die Antwort
    plausibel aussieht, sondern dass der gemeldete Hash der Hash dessen ist,
    was die Instanz tatsaechlich ueber die Leitung schickt - und dass kein
    ausfuehrbarer Client-Code an der Liste vorbei laeuft.
    """
    import stand as stand_modul

    besucher = TestClient(app)  # ohne Login: wer prueft, hat kein Admin-Token
    daten = besucher.get("/version").json().get("client", {})
    check("Client: /version listet die ausgelieferten Client-Dateien einzeln",
          daten.get("clienthash", "").startswith("sha256:") and len(daten.get("dateien", {})) > 1,
          str(list(daten.get("dateien", {})))[:80])
    check("Client: die Nachrechenvorschrift kommt ohne unser Werkzeug aus",
          "sha256sum" in daten.get("nachrechnen", "") and "curl" in daten.get("nachrechnen", ""))
    check("Client: die Antwort nennt ihre Grenze statt Unversehrtheit zu behaupten",
          "anderen Code schickt" in daten.get("grenze", ""))

    # Der Kern: gemeldeter Hash gegen den Hash der tatsaechlichen Auslieferung.
    # Faellt das auseinander, ist die Liste eine Behauptung ueber Dateien im
    # Repo, nicht ueber die Seite, die jemand gerade benutzt.
    abweichungen = []
    for pfad, digest in daten.get("dateien", {}).items():
        antwort = besucher.get(f"/{pfad}")
        if antwort.status_code != 200 or hashlib.sha256(antwort.content).hexdigest() != digest:
            abweichungen.append(pfad)
    check("Client: jede gemeldete Datei kommt so ueber die Leitung, wie sie gehasht ist",
          not abweichungen, ", ".join(abweichungen)[:90])

    check("Client: blind.js und ballot.js stehen in der Liste",
          {"static/blind.js", "static/ballot.js"} <= set(daten.get("dateien", {})))

    # Vollstaendigkeit: Inline-Code in einer Seite liefe im Browser, stuende
    # aber in keiner Datei - der Hash sagte dann weniger, als er aussieht.
    check("Client: kein ausfuehrbarer Inline-Code in den Seiten",
          not stand_modul.client_luecken(), str(stand_modul.client_luecken())[:120])

    verzeichnis = Path(tempfile.mkdtemp())
    (verzeichnis / "templates").mkdir()
    (verzeichnis / "static").mkdir()
    (verzeichnis / "static" / "blind.js").write_text("// Blinding\n")
    vorher = stand_modul.clienthash(verzeichnis)
    (verzeichnis / "templates" / "poll.html").write_text(
        '<script type="module" src="/static/blind.js"></script>\n'
        '<script type="application/json" id="poll-params">{"poll_id": "x"}</script>\n'
    )
    check("Client: geladene Dateien und JSON-Daten gelten nicht als Luecke",
          not stand_modul.client_luecken(verzeichnis), str(stand_modul.client_luecken(verzeichnis))[:120])
    (verzeichnis / "templates" / "poll.html").write_text(
        '<script type="module">\n  const POLL = "x";\n</script>\n'
    )
    check("Client: ein Rueckfall zu Inline-Code wird gemeldet",
          any("Inline-Code" in b for b in stand_modul.client_luecken(verzeichnis)))
    check("Client: die Luecke erscheint im Debug-Modul als Befund, nicht als Hinweis",
          any("Inline-Code" in b for b in stand_modul.abgleich(verzeichnis).befunde))

    (verzeichnis / "static" / "blind.js").write_text("// Blinding, aber anders\n")
    check("Client: geaenderter Client-Code bewegt den Client-Hash",
          stand_modul.clienthash(verzeichnis) != vorher)

    # Und die Stelle, an der geprueft wird, zeigt es auch - eine Auskunft, die
    # nur unter /version steht, findet niemand, der nicht schon sucht.
    board = besucher.get(f"/board/{POLL}").text
    check("Client: die Nachweis-Seite nennt den Hash und den Weg, ihn nachzurechnen",
          daten["clienthash"] in board and "sha256sum" in board)
    check("Client: die Nachweis-Seite benennt die Grenze der Massnahme",
          "anderen Code schickt als allen anderen" in board)


def demo_schalter() -> None:
    """Angriffsdemos haengen an EIDPOLL_DEMOS, nicht an der Anwendung (EIP-T-050).

    Geprueft wird die Abwesenheit der *Route*, nicht eine Abweisung: Ohne
    verdrahtetes demo.py gibt es in der laufenden App keinen Weg mehr, der ein
    Board umschreibt - das ist die Aussage, nicht "der Server sagt nein".
    """
    oeffentlich = create_app(
        store_path=Path(tempfile.mkdtemp()) / "public.sqlite3",
        settings=Settings(public=True, admin_token="admin", antwort_floor_s=0),
    )
    pub = TestClient(oeffentlich)
    pub.post("/api/admin/login", json={"token": "admin"})
    tamper = pub.post("/api/admin/demo/tamper/x", json={"index": 0, "choice": "Ja"})
    check("Demo-Schalter: oeffentlich gibt es die Manipulationsroute nicht",
          tamper.status_code == 404, f"status={tamper.status_code}")
    reset = pub.post("/api/admin/reset/x", json={"credential": "testperson1"})
    check("Demo-Schalter: oeffentlich gibt es die Reset-Route nicht",
          reset.status_code == 404, f"status={reset.status_code}")
    check("Demo-Schalter: oeffentliche Admin-Seite bietet keine Demos an",
          "Angriffsdemos" not in pub.get("/admin").text)

    # Dieselbe oeffentliche Instanz mit ausdruecklich gesetztem Schalter - die
    # Vorfuehrinstanz aus DEPLOY.md.
    vorfuehrung = TestClient(
        create_app(
            store_path=Path(tempfile.mkdtemp()) / "vorfuehrung.sqlite3",
            settings=Settings(public=True, admin_token="admin", demos=True, antwort_floor_s=0),
        )
    )
    ohne_anmeldung = vorfuehrung.post("/api/admin/demo/stuff/x", json={"choice": "Ja"})
    check("Demo-Schalter: mit EIDPOLL_DEMOS erreichbar, aber nur fuer den Betreiber",
          ohne_anmeldung.status_code == 400 and "vorbehalten" in ohne_anmeldung.text,
          f"status={ohne_anmeldung.status_code}")


def main() -> int:
    client = TestClient(app)

    rfc9474_testvektor()
    eintragsformat()
    pruefung_ohne_datenbank()
    umfrage_schluessel()
    signaturschluessel()

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
          blind.verify(service.poll_pubkey(POLL), token, sig))

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

    # Erst hier: der Auditor prueft den *echten* Export dieser Umfrage, es muss
    # also abgestimmt und geschlossen sein.
    auditor_unabhaengig()

    parallel_participation()
    anspruch_atomar()
    laufende_pruefung()
    batch_veroeffentlichung()
    externer_anker()
    abbruch_nach_signatur()
    puffer_abschaltbar()
    sitzungstrennung()
    datenabzug_nach_schluss()
    sicherungskopie_ohne_geheimnisse()
    offenlegungsseiten()
    ausgelieferter_stand()
    nachrechenbarer_client()
    demo_schalter()

    # Angriff 1 - Ballot-Stuffing wird von der Abrechnung entlarvt
    open_poll = "stuffdemo"
    client.post("/api/admin/create",
                json={"poll_id": open_poll, "question": "Demo?", "options": ["Ja", "Nein"]})
    demo.stuff_ballot(service, open_poll, "Ja")
    acc = service.accounting(open_poll)
    check("Angriff Ballot-Stuffing: Abrechnung schlaegt aus",
          not acc.ok, f"{acc.n_votes} Stimmen bei {acc.n_eligible} Berechtigten")

    # Angriff 2 - Board umschreiben bricht die Batch-Kette und verhindert das Ergebnis
    vote_leaf = next(e.leaf_hash for e in service.board(POLL) if e.kind == "VOTE")
    demo.tamper_board(service, POLL, vote_leaf, "Nein")
    status = service.chain_status(POLL)
    check("Angriff Board-Manipulation: Batch-Kette bricht sichtbar",
          not status.ok, f"Batch {status.broken_at}")
    try:
        service.tally(POLL)
        check("Angriff Board-Manipulation: kein Ergebnis mehr", False)
    except Exception as exc:
        check("Angriff Board-Manipulation: kein Ergebnis mehr", "gebrochen" in str(exc), str(exc))

    pruefwerkzeug_auf_der_kommandozeile(client)

    # Debug-Modul hat alles mitbekommen - ueber alle drei Logs (Baustein G)
    import debug as debug_modul

    counts = debug_modul.counts_gesamt()
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
          debug_modul.counts_gesamt()["info"] == counts["info"]
          and debug_modul.counts_gesamt()["reject"] > counts["reject"])
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
          not any("voter_key" in str(e.detail) for e in debug_modul.events_gesamt("all")))

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
