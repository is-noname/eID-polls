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
    votes = [e for e in entries if e.kind == "VOTE"]
    check("Parallel: jede Stimme genau einmal im Board", len(votes) == n, f"{len(votes)} von {n}")
    issued = [e for e in entries if e.kind == "TOKEN_ISSUED"]
    check("Parallel: jede Token-Ausgabe genau einmal im Board",
          len(issued) == n, f"{len(issued)} von {n}")
    # Die laufende Nummer kommt aus demselben Schritt wie der Anspruch selbst
    # (EIP-T-047). Kaeme sie aus einer zweiten Abfrage, stuenden hier bei
    # gleichzeitiger Ausgabe zwei gleiche Nummern.
    from board_eintrag import TokenIssued, parse

    nummern = sorted(p.n_eligible for p in map(parse, issued) if isinstance(p, TokenIssued))
    check("Parallel: Ausgabe-Nummern lueckenlos und ohne Dopplung",
          nummern == list(range(1, n + 1)), str(nummern))
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
        blinded, inv = blind.blind(token, service.n, service.e)
        response = client.post(f"/api/token/{poll}", json={"blinded": blinded.hex()})
        if response.status_code == 200:
            sig = blind.finalize(bytes.fromhex(response.json()["blind_sig"]), inv, service.n)
            with sammel:
                tokens.append((token, sig))
        return response.status_code

    codes = gleichzeitig(hole_token, n)
    check(f"Wettlauf: von {n} gleichzeitigen Abholungen desselben Ausweises genau eine",
          codes.count(200) == 1, f"{codes.count(200)} mal 200, Codes {sorted(codes)}")
    check("Wettlauf: genau eine Token-Ausgabe im Board",
          len([e for e in service.board(poll) if e.kind == "TOKEN_ISSUED"]) == 1)

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
    from debug import log as debug_log

    abweisungen = [e for e in debug_log.events("reject") if poll in str(e.detail.get("pfad", ""))]
    check("Wettlauf: jede Abweisung im Debug-Modul sichtbar",
          len(abweisungen) == 2 * (n - 1), f"{len(abweisungen)} statt {2 * (n - 1)}")


def eintragsformat() -> None:
    """Konstruktoren und Parser (EIP-T-046) - ohne Board, ohne Store.

    Geprueft wird das Rundum: was ein Konstruktor schreibt, muss der Parser als
    dieselbe Variante zurueckgeben, und alles, was sich nicht deuten laesst,
    muss zu genau einem Ergebnis fuehren - Unlesbar mit Grund.
    """
    import board_eintrag as be

    def eintrag(payload: dict | str) -> be.Eintrag:
        line = payload if isinstance(payload, str) else be.canonical(payload)
        return be.parse(be.BoardEntry(0, be.GENESIS, line, ""))

    token, sig = bytes.fromhex("aa" * 32), bytes.fromhex("bb" * 128)
    gestimmt = eintrag(be.vote("p", token, sig, ["Nein", "Ja"]))
    check("Format: Stimme kommt als Vote zurueck",
          isinstance(gestimmt, be.Vote) and gestimmt.token == token and gestimmt.sig == sig,
          type(gestimmt).__name__)
    check("Format: Optionen im Board sortiert, Reihenfolge des Anklickens unsichtbar",
          isinstance(gestimmt, be.Vote) and gestimmt.choices == ("Ja", "Nein"),
          str(getattr(gestimmt, "choices", gestimmt)))

    varianten = [
        (be.poll_open("p", "?", ["Ja", "Nein"]), be.PollOpen),
        (be.poll_closed("p"), be.PollClosed),
        (be.token_issued("p", 3), be.TokenIssued),
    ]
    check("Format: jede Variante wird als ihr Typ gelesen",
          all(isinstance(eintrag(p), typ) for p, typ in varianten))
    check("Format: kind bleibt fuer die Anzeige erhalten",
          [be.BoardEntry(0, be.GENESIS, be.canonical(p), "").kind for p, _ in varianten]
          == ["POLL_OPEN", "POLL_CLOSED", "TOKEN_ISSUED"])

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
        ("Token-Ausgabe ohne Anzahl", {"type": "TOKEN_ISSUED", "poll": "p"}),
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


def pruefung_ohne_datenbank() -> None:
    """Die Pruefung eines Dritten (EIP-T-045).

    Laeuft ohne SQLite, ohne TestClient und ohne den privaten Signaturschluessel
    im Pruefpfad: gebaut wird ein Board von Hand, geprueft wird mit
    verifikation.pruefe() und dem oeffentlichen Schluessel. Genau das ist die
    Zusage aus §7 - wenn dieser Block laeuft, kann sie jeder nachvollziehen.
    """
    import secrets

    import board_eintrag
    from verifikation import BoardEntry, GENESIS, canonical, entry_hash, pruefe

    key = blind.generate_key(1024)  # klein, weil hier nur der Pfad geprueft wird
    pub = key.public_key()
    n, e, d = pub.public_numbers().n, pub.public_numbers().e, key.private_numbers().d
    options = ["Ja", "Nein"]

    def signiertes_token() -> tuple[bytes, bytes]:
        token = secrets.token_bytes(32)
        blinded, inv = blind.blind(token, n, e)
        sig = blind.finalize(blind.blind_sign(blinded, n, d), inv, n)
        return token, sig

    def board(payloads: list[dict]) -> list[BoardEntry]:
        entries, prev = [], GENESIS
        for i, payload in enumerate(payloads):
            line = canonical(payload)
            digest = entry_hash(i, prev, line)
            entries.append(BoardEntry(i, prev, line, digest))
            prev = digest
        return entries

    t1, s1 = signiertes_token()
    t2, s2 = signiertes_token()
    # Gebaut wird mit denselben Konstruktoren wie im Server (EIP-T-046) - ein
    # von Hand getipptes Board wuerde die Pruefung gegen ein Format testen, das
    # die App gar nicht schreibt.
    payloads = [
        board_eintrag.poll_open("p", "?", options),
        board_eintrag.token_issued("p", 1),
        board_eintrag.token_issued("p", 2),
        board_eintrag.vote("p", t1, s1, ["Ja"]),
        board_eintrag.vote("p", t2, s2, ["Nein"]),
    ]
    entries = board(payloads)

    bericht = pruefe(entries, pub, options)
    check("Pruefung ohne DB: intaktes Board ist unauffaellig",
          bericht.chain.sound and bericht.accounting.ok and bericht.result_ok)
    check("Pruefung ohne DB: Auszaehlung aus dem Board",
          bericht.counts == {"Ja": 1, "Nein": 1}, str(bericht.counts))
    check("Pruefung ohne DB: eigenes Token auffindbar", bericht.lookup(t1.hex()) == ["Ja"])
    check("Pruefung ohne DB: fremdes Token nicht auffindbar", bericht.lookup("aa" * 32) is None)

    # Umgeschriebene Stimme - genau die Demo aus §9, hier ohne App
    tampered = list(entries)
    tampered[3] = BoardEntry(
        3, entries[3].prev_hash,
        canonical({**payloads[3], "choices": ["Nein"]}), entries[3].entry_hash,
    )
    b = pruefe(tampered, pub, options)
    check("Pruefung ohne DB: umgeschriebene Stimme bricht die Kette",
          not b.chain.ok and b.chain.broken_at == 3 and not b.result_ok, f"ab #{b.chain.broken_at}")

    # Stimme mit erfundener Signatur, Kette sauber nachgerechnet
    gefaelscht = board(payloads[:3] + [{**payloads[3], "sig": "bb" * 128}])
    b = pruefe(gefaelscht, pub, options)
    check("Pruefung ohne DB: erfundene Token-Signatur faellt auf",
          b.chain.ok and not b.chain.signatures_ok and b.chain.bad_signature_at == 3,
          f"#{b.chain.bad_signature_at}")

    # Ballot-Stuffing: mehr Stimmen als ausgegebene Token
    b = pruefe(board([payloads[0], payloads[1], payloads[3], payloads[4]]), pub, options)
    check("Pruefung ohne DB: Abrechnung entlarvt Ueberschuss",
          not b.accounting.ok and b.accounting.surplus == 1,
          f"{b.accounting.n_votes} Stimmen bei {b.accounting.n_eligible} Token")

    # Option, die es in der Umfrage nicht gibt
    b = pruefe(board(payloads + [{**payloads[3], "choices": ["Vielleicht"]}]), pub, options)
    check("Pruefung ohne DB: unbekannte Option benannt",
          b.unknown_choice == "Vielleicht" and not b.result_ok, str(b.unknown_choice))

    # Kaputtgeschriebene Stimme, Kette sauber nachgerechnet: sie darf nicht
    # einfach verschwinden, sonst waere Kaputtschreiben ein Weg, Stimmen
    # loszuwerden, ohne dass es auffaellt (EIP-T-046).
    verstuemmelt = board(payloads[:4] + [{**payloads[4], "token": "kein hex"}])
    b = pruefe(verstuemmelt, pub, options)
    check("Pruefung ohne DB: unlesbarer Eintrag wird benannt, nicht uebergangen",
          b.chain.ok and b.unlesbar is not None and b.unlesbar.index == 4 and not b.result_ok,
          str(b.unlesbar))
    check("Pruefung ohne DB: unlesbarer Eintrag zaehlt nirgends mit",
          b.counts == {"Ja": 1, "Nein": 0} and b.accounting.n_votes == 1, str(b.counts))

    check("Pruefung ohne DB: Pruefmodul kennt weder Store noch privaten Schluessel",
          not any(m in sys.modules["verifikation"].__dict__ for m in ("Store", "store")))


def pruefwerkzeug_auf_der_kommandozeile(client: TestClient) -> None:
    """Export + CLI: was ein Dritter tatsaechlich in die Hand bekommt."""
    import json

    import verifikation

    export = client.get(f"/api/board/{POLL}")
    check("Export: /api/board liefert das Board als Datei", export.status_code == 200)
    data = export.json()
    check("Export: Eintraege, Optionen und oeffentlicher Schluessel enthalten",
          bool(data.get("entries")) and bool(data.get("options"))
          and "PUBLIC KEY" in str(data.get("public_key")))
    check("Export: kein privater Schluessel, kein voter_key im Export",
          "PRIVATE" not in json.dumps(data) and "voter_key" not in json.dumps(data))

    entries = verifikation.entries_from_export(data)
    check("Export: exportierte Eintraege sind die des Boards",
          [e.entry_hash for e in entries] == [e.entry_hash for e in service.board(POLL)])

    path = Path(tempfile.mkdtemp()) / "board.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    key_path = path.parent / "key.pem"
    key_path.write_text(service.public_key_pem, encoding="utf-8")

    # POLL ist an dieser Stelle bereits manipuliert (Angriff 2) - das
    # Pruefwerkzeug muss das melden und mit Exit-Code 1 enden.
    code = verifikation.main([str(path), "--pubkey", str(key_path), "--token", "aa" * 32])
    check("Pruefwerkzeug: meldet das manipulierte Board mit Exit-Code 1", code == 1, f"code={code}")

    # Die Umfrage aus dem Parallel-Test ist unversehrt - dort muss dasselbe
    # Werkzeug ohne Befund durchlaufen.
    heil = Path(tempfile.mkdtemp()) / "board.json"
    heil.write_text(json.dumps(client.get("/api/board/parallel").json()), encoding="utf-8")
    code = verifikation.main([str(heil), "--pubkey", str(key_path)])
    check("Pruefwerkzeug: bestaetigt ein unversehrtes Board mit Exit-Code 0", code == 0, f"code={code}")


def main() -> int:
    client = TestClient(app)

    eintragsformat()
    pruefung_ohne_datenbank()

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
    anspruch_atomar()

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

    pruefwerkzeug_auf_der_kommandozeile(client)

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
