"""Durchlauf der sieben Abnahmepunkte im echten Browser (Playwright).

Prueft vor allem static/blind.js: nur hier zeigt sich, ob die Browser-Krypto
bitgleich zu blind.py rechnet - sonst weist der Server die Stimme als
"Token-Signatur ungueltig" ab.

    # Server mit frischer Datenbank starten. Ohne EIDPOLL_ADMIN_TOKEN wuerde
    # config.py ein Zufallstoken erzeugen und die Admin-Anmeldung scheitern.
    EIDPOLL_DB=/tmp/bt.sqlite3 EIDPOLL_ADMIN_TOKEN=admin python3 -m uvicorn web:app --port 8899 &
    python3 browser_test.py            # optional: EIDPOLL_URL=http://127.0.0.1:8899

Die Datenbank muss leer sein - der Test legt eine Umfrage 'browsertest' an und
holt Tokens fuer feste Identitaeten.
"""

import json
import os
import re
import sys
import tempfile

from playwright.sync_api import sync_playwright

BASE = os.environ.get("EIDPOLL_URL", "http://127.0.0.1:8899")
SHOTS = tempfile.mkdtemp(prefix="eidpoll-shots-")
POLL = "browsertest"
fails: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(f"[{'  ok  ' if cond else ' FEHL '}] {label}{(' - ' + detail) if detail else ''}")
    if not cond:
        fails.append(label)


def anmelden(page, code: str, pin: str = "123456") -> None:
    """Der vollstaendige eID-Weg, wie eine Testperson ihn geht (EIP-T-095).

    Seit die Anmeldung die Umfrageseite verlaesst, ist sie kein Dialog mehr,
    sondern eine Folge echter Seitenwechsel: eID-Dienst, Ausweis-App, Karte,
    Datenauskunft, PIN. Der Test geht denselben Weg statt an ihm vorbei - eine
    Abkuerzung ueber /api/auth wuerde genau die Strecke ueberspringen, die
    dieses Ticket gebaut hat.
    """
    page.click("#auth-open-button")
    page.wait_for_selector("#dienst-weiter")
    page.click("#dienst-weiter")
    page.wait_for_selector("#ausweisnummer")
    page.fill("#ausweisnummer", code)
    page.click("#karte-lesen")
    page.wait_for_selector("#auskunft-ok")
    page.click("#auskunft-ok")
    page.wait_for_selector("#pin")
    page.fill("#pin", pin)
    page.click("#pin-ok")
    page.wait_for_load_state("networkidle")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    # accept_downloads: Der gespeicherte Beleg ist seit EIP-T-099 nicht nur eine
    # Datei zum Aufheben, sondern die Eingabe von /verify - er muss echt durch
    # den Download gegangen sein, damit der Test etwas ueber den Alltag sagt.
    page = browser.new_context(
        accept_downloads=True,
        permissions=["clipboard-read", "clipboard-write"],
    ).new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    # --- Admin: Umfrage anlegen
    page.goto(f"{BASE}/admin")
    page.wait_for_load_state("networkidle")
    page.fill("#admin-token", os.environ.get("EIDPOLL_ADMIN_TOKEN", "admin"))
    page.click("#login-button")
    page.wait_for_timeout(1200)
    page.goto(f"{BASE}/admin")
    page.wait_for_load_state("networkidle")
    page.fill("#poll-id", POLL)
    page.fill("#question", "Funktioniert der Durchlauf?")
    page.fill("#options", "Ja\nNein\nEnthaltung")
    page.click("#create-button")
    page.wait_for_timeout(1500)

    # --- Punkt 1: offene Umfrage auf der Startseite
    page.goto(f"{BASE}/")
    page.wait_for_load_state("networkidle")
    check("Punkt 1: Umfrage angelegt, auf Startseite sichtbar", POLL in page.content())
    check("Punkt 1b: OFFEN-Status auf der Startseite", "OFFEN" in page.content())
    page.screenshot(path=f"{SHOTS}/01_start.png", full_page=True)

    # --- EIP-T-100: Schritt 2 ist vor der Anmeldung gesperrt, nicht nur optisch
    page.goto(f"{BASE}/poll/{POLL}")
    page.wait_for_load_state("networkidle")
    check("T-100: Auswahlfelder vor der Anmeldung disabled",
          page.get_attribute("input[value='Ja']", "disabled") is not None)
    page.click("label.choice", force=True)
    check("T-100: Klick auf eine Auswahl vor der Anmeldung setzt kein Haekchen",
          not page.is_checked("input[value='Ja']"))
    check("T-100: Klick fuehrt zu Schritt 1 statt ins Leere",
          "ausweisen" in page.inner_text(".toast.err").lower())
    check("T-100: Abgabeknopf nennt den Grund statt nur grau zu sein",
          page.inner_text("#vote-button").strip() == "Erst ausweisen")

    # --- Punkt 2: authentifizieren und Token holen (Phase A, Blinding im Browser)
    page.goto(f"{BASE}/poll/{POLL}")
    page.wait_for_load_state("networkidle")
    anmelden(page, "testperson1")
    check("Punkt 2a: eID-Weg endet zurueck auf der Umfrageseite", f"/poll/{POLL}" in page.url,
          page.url)
    page.goto(f"{BASE}/poll/{POLL}")
    page.wait_for_load_state("networkidle")
    check("Punkt 2: authentifiziert (Schritt 1 erledigt)",
          "Ausweis erfolgreich ausgelesen." in page.content())
    check("Punkt 2b: kein roher Stub-Praefix in der Teilnehmeransicht",
          "STUB-NO-REAL-IDENTITY" not in page.content())
    check("Punkt 2c: kein Wort ueber Test/Stub/Simulation/Code in der Teilnehmeransicht",
          not any(w in page.content() for w in ["Stub", "Simulation", "Zugangscode"]))

    check("Punkt 2d: kein eigener Schritt zum Abholen des Stimm-Tokens mehr (T-021)",
          page.query_selector("#step-token") is None
          and page.query_selector("#token-button") is None)

    # --- Punkt 3: abstimmen. Ein Klick macht Token, Signatur und Stimmabgabe.
    check("Punkt 3: waehrend der Laufzeit keine Verteilung sichtbar", "Ergebnis" not in page.content())
    page.check("input[value='Ja']")
    page.click("#vote-button")
    page.wait_for_selector("#step-receipt:not(.hidden)", timeout=20000)
    check("Punkt 3b: Stimme angenommen (Server akzeptiert die PSS-Signatur)", True)
    page.screenshot(path=f"{SHOTS}/02_abgestimmt.png", full_page=True)

    stored_after_vote = page.evaluate(f"() => localStorage.getItem('eidpoll:{POLL}')")
    check(
        "Punkt 3c: Token nach Abgabe aus dem Speicher entfernt, Belegdaten bleiben",
        stored_after_vote is not None
        and '"token"' not in stored_after_vote
        and '"leaf"' in stored_after_vote,
        stored_after_vote,
    )

    # --- Punkt 4: Verifikations-Beleg
    page.wait_for_timeout(500)
    token_node = page.query_selector("#receipt-token")
    receipt = (token_node.text_content() or "") if token_node else ""
    token = re.search(r"^([0-9a-f]{64})$", receipt.strip())
    check("Punkt 4: Verifikations-Beleg mit Token angezeigt", token is not None)
    if token is None:
        browser.close()
        sys.exit(1)

    # Den Beleg wirklich speichern - diese Datei geht spaeter auf /verify zurueck.
    beleg_pfad = os.path.join(SHOTS, "beleg.txt")
    with page.expect_download() as dl:
        page.click("#receipt-download")
    dl.value.save_as(beleg_pfad)
    with open(beleg_pfad, encoding="utf-8") as fh:
        beleg_text = fh.read()
    check("Punkt 4c: Beleg gespeichert, Token steht unter seinem Label",
          f"Stimm-Token:  {token.group(1)}" in beleg_text, beleg_text.splitlines()[1][:60])

    page.click("#receipt-copy")
    page.wait_for_selector(".toast", timeout=5000)
    check("Punkt 4d: Token kopieren meldet sich", "Token kopiert" in page.inner_text(".toast"),
          page.inner_text(".toast"))

    # --- Punkt 5: zweiter Abstimmversuch
    page.check("input[value='Nein']")
    page.click("#vote-button")
    page.wait_for_selector(".toast.err", timeout=10000)
    message = page.inner_text(".toast.err")
    check("Punkt 5: zweiter Abstimmversuch abgewiesen", "verbraucht" in message, message)
    page.screenshot(path=f"{SHOTS}/03_abgewiesen.png", full_page=True)

    # --- zweite Identitaet, damit das Ergebnis nicht trivial ist
    page2 = browser.new_context().new_page()
    page2.goto(f"{BASE}/poll/{POLL}")
    anmelden(page2, "testperson2")
    page2.goto(f"{BASE}/poll/{POLL}")
    page2.wait_for_load_state("networkidle")
    page2.check("input[value='Nein']")
    page2.click("#vote-button")
    page2.wait_for_selector("#step-receipt:not(.hidden)", timeout=20000)

    # --- Punkt 5b: zweites Token fuer dieselbe Identitaet (Phase A)
    page3 = browser.new_context().new_page()
    page3.goto(f"{BASE}/poll/{POLL}")
    anmelden(page3, "TESTPERSON1")  # gleicher Code, andere Schreibweise
    page3.goto(f"{BASE}/poll/{POLL}")
    page3.wait_for_load_state("networkidle")
    page3.check("input[value='Nein']")
    page3.click("#vote-button")
    page3.wait_for_selector(".toast.err", timeout=20000)
    message3 = page3.inner_text(".toast.err")
    check("Punkt 5b: zweite Stimmberechtigung fuer dieselbe Identitaet abgewiesen",
          "Stimmberechtigung ausgegeben" in message3, message3)
    check("Punkt 5c: Abweisung nennt keine abgeschaffte Sicherungsdatei",
          "Datei" not in message3 and "abgeholt" not in message3, message3)

    # --- EIP-T-095: die Simulation als eigene Strecke
    # Geprueft wird nicht, dass sie huebsch ist, sondern dass sie das sagt, was
    # sie nach KODEX §4 sagen muss, und dass ihre Fehlerwege irgendwo enden.
    page4 = browser.new_context().new_page()
    page4.goto(f"{BASE}/poll/{POLL}")
    page4.click("#auth-open-button")
    page4.wait_for_selector("#dienst-weiter")
    dienst = page4.content()
    check("T-095: eID-Dienst kennzeichnet sich als Simulation (KODEX §4)",
          "Simulation" in page4.inner_text(".sim-leiste")
          and "kein Ausweis" in page4.inner_text(".sim-leiste"))
    check("T-095: Datenauskunft nennt das fehlende Berechtigungszertifikat",
          "Berechtigungszertifikat" in dienst and "simuliert" in dienst)
    check("T-095: nur das dienstespezifische Kennzeichen wird angefordert",
          "Restricted Identification" in dienst
          and "aus" in (page4.get_attribute(".feldzeile:nth-child(2)", "class") or ""))
    check("T-095: keine Marke einer realen Anwendung nachgebaut",
          "AusweisApp" not in dienst and "Governikus" not in dienst
          and "Bundesverwaltungsamt" in dienst)

    page4.click("#dienst-weiter")
    page4.wait_for_selector("#karte-lesen")
    page4.click("#karte-lesen")  # leeres Feld
    page4.wait_for_load_state("networkidle")
    check("T-095: ohne Ausweisnummer bleibt der Kartenschritt stehen",
          "Kein Ausweis erkannt" in page4.content() and page4.query_selector("#ausweisnummer"))

    page4.fill("#ausweisnummer", "unbekannt-999")
    page4.click("#karte-lesen")
    page4.wait_for_selector("#auskunft-ok")
    page4.click("#auskunft-ok")
    page4.wait_for_selector("#pin")

    # Fehlversuchszaehler: die Stelle, an der Menschen im Ernstfall scheitern
    for erwartet in ("2", "1"):
        page4.fill("#pin", "000000")
        page4.click("#pin-ok")
        page4.wait_for_selector(".meldung.fehler")
        check(f"T-095: falsche PIN zaehlt herunter auf {erwartet}",
              f"Noch {erwartet}" in page4.inner_text(".meldung.fehler").replace("\n", " "),
              page4.inner_text(".meldung.fehler").replace("\n", " ")[:80])

    page4.fill("#pin", "000000")
    page4.click("#pin-ok")
    page4.wait_for_selector("#sim-zurueck")
    check("T-095: dritter Fehlversuch sperrt den Ausweis und nennt die CAN",
          "gesperrt" in page4.content() and "CAN" in page4.content())

    page4.click("#sim-zurueck")
    page4.wait_for_load_state("networkidle")
    check("T-095: gesperrte Anmeldung landet zurueck auf der Umfrageseite",
          f"/poll/{POLL}" in page4.url, page4.url)

    # Unbekannter Zugangscode: faellt erst nach der PIN auf, wie im Ernstfall
    # die Abweisung durch den Dienst - und muss auf der Umfrageseite ankommen.
    anmelden(page4, "unbekannt-999")
    check("T-095: unbekannte Ausweisnummer wird auf der Umfrageseite erklaert",
          "nicht hinterlegt" in page4.content() and page4.query_selector("#auth-open-button"),
          page4.url)

    # Abbruch muss an jeder Stelle gehen
    page4.goto(f"{BASE}/poll/{POLL}")
    page4.click("#auth-open-button")
    page4.wait_for_selector("#sim-abbruch")
    page4.click("#sim-abbruch")
    page4.wait_for_load_state("networkidle")
    check("T-095: Abbruch beim eID-Dienst fuehrt zurueck, ohne anzumelden",
          f"/poll/{POLL}" in page4.url and page4.query_selector("#auth-open-button") is not None,
          page4.url)

    # --- EIP-T-021: Abbruch zwischen Signatur und Stimmabgabe
    # Der einzige Moment, in dem die Berechtigung verbraucht ist, ohne dass die
    # Stimme steht. Der Browser haelt Token und Signatur bis dahin fest; der
    # naechste Klick muss dieselben wiederverwenden statt neue anzufordern -
    # eine zweite Berechtigung gibt der Server bewusst nicht aus.
    page5 = browser.new_context().new_page()
    page5.goto(f"{BASE}/poll/{POLL}")
    anmelden(page5, "testperson5")
    page5.goto(f"{BASE}/poll/{POLL}")
    page5.wait_for_load_state("networkidle")

    page5.route("**/api/vote/**", lambda route: route.abort())  # Netz weg nach der Signatur
    # 'Enthaltung' und nicht 'Teilweise': Die Umfrage dieses Tests hat drei
    # Optionen, und 'Teilweise' ist keine davon - der Klick lief ins Leere und
    # brach den Durchlauf mit einem Timeout ab, noch bevor T-021 geprueft war.
    # Vorbestandener Fehler, gefunden beim Umbau auf den eID-Weg (EIP-T-095).
    page5.check("input[value='Enthaltung']")
    page5.click("#vote-button")
    page5.wait_for_selector(".toast.err", timeout=20000)
    stored_mid = page5.evaluate(f"() => localStorage.getItem('eidpoll:{POLL}')")
    check(
        "T-021: Berechtigung nach Abbruch im Browser gesichert, noch nicht abgestimmt",
        stored_mid is not None and '"sig"' in stored_mid and '"voted"' not in stored_mid,
        stored_mid,
    )
    token_before = json.loads(stored_mid)["token"] if stored_mid else None

    page5.unroute("**/api/vote/**")  # Netz wieder da, zweiter Versuch
    page5.click("#vote-button")
    page5.wait_for_selector("#step-receipt:not(.hidden)", timeout=20000)
    node5 = page5.query_selector("#receipt-token")
    token_after = (node5.text_content() or "").strip() if node5 else ""
    check("T-021: zweiter Klick verwendet dasselbe Token, keine neue Berechtigung",
          token_after != "" and token_after == token_before, token_after)

    # --- Punkt 6: schliessen, Ergebnis, eigenes Token wiederfinden
    page.goto(f"{BASE}/admin")
    page.wait_for_load_state("networkidle")
    page.once("dialog", lambda d: d.accept())
    page.click(f".close-button[data-poll='{POLL}']")
    page.wait_for_timeout(1500)

    page.goto(f"{BASE}/board/{POLL}")
    page.wait_for_load_state("networkidle")
    content = page.content()
    check("Punkt 6: Ergebnis auf dem Board sichtbar", "Ergebnis" in content)
    check("Punkt 6b: eigenes Token im Board wiederfindbar", token.group(1) in content)
    page.screenshot(path=f"{SHOTS}/04_board.png", full_page=True)

    # Token im Fragment (#), nicht in den Query-Parametern: Das Fragment sendet
    # der Browser nie mit - die Suche laeuft client-seitig (EIP-T-033, F).
    page.goto(f"{BASE}/verify#poll={POLL}&token={token.group(1)}")
    page.wait_for_selector("#verify-result.ok", timeout=10_000)
    check("Punkt 4b: Verifikationsseite findet die eigene Stimme (im Browser)",
          "Token gefunden" in page.content() and "Ja" in page.inner_text("#verify-result"))
    page.screenshot(path=f"{SHOTS}/05_verify.png", full_page=True)

    # Derselbe Weg noch einmal, aber so, wie ihn jemand ohne zweites Geraet geht
    # (EIP-T-099): die gespeicherte Datei ablegen, statt 64 Zeichen abzutippen.
    # Genommen wird die Datei aus Punkt 4c - der echte Download, nicht ein hier
    # zusammengebauter Text.
    page.goto(f"{BASE}/verify")
    page.wait_for_load_state("networkidle")
    page.set_input_files("#beleg-file", beleg_pfad)
    page.wait_for_selector("#verify-result.ok", timeout=10_000)
    check("Punkt 4e: Beleg-Datei auf /verify eingelesen, Suche laeuft von selbst",
          "Token gefunden" in page.content() and page.input_value("#token") == token.group(1),
          page.input_value("#token")[:20])
    check("Punkt 4f: Umfrage aus der Datei uebernommen", page.input_value("#poll") == POLL,
          page.input_value("#poll"))

    # Eine fremde Datei muss abgewiesen werden, ohne das Board anzufassen.
    fremd_pfad = os.path.join(SHOTS, "einkaufsliste.txt")
    with open(fremd_pfad, "w", encoding="utf-8") as fh:
        fh.write("Einkaufsliste\nMilch\nBrot\n")
    page.goto(f"{BASE}/verify")
    page.wait_for_load_state("networkidle")
    board_abrufe: list[str] = []
    page.on("request", lambda r: board_abrufe.append(r.url) if "/api/board/" in r.url else None)
    page.set_input_files("#beleg-file", fremd_pfad)
    page.wait_for_selector("#verify-result.err", timeout=10_000)
    check("Punkt 4g: fremde Datei nennt den Grund und laedt das Board nicht",
          "Stimm-Token" in page.inner_text("#verify-result") and not board_abrufe,
          page.inner_text("#verify-result").replace("\n", " ")[:90])
    page.screenshot(path=f"{SHOTS}/06_verify_datei.png", full_page=True)

    # --- Punkt 7: Abrechnung und Kettenpruefung als oeffentliche Seite
    page.goto(f"{BASE}/board/{POLL}")
    page.wait_for_load_state("networkidle")
    stats = page.inner_text(".stats")
    check("Punkt 7: Kettenpruefung und Ledger-Abrechnung oeffentlich",
          "Kette" in stats and "Ledger-Abrechnung" in stats and "BRUCH" not in stats,
          stats.replace("\n", " ")[:110])

    # Teilnehmersicht: Betreiber-Bereiche sind weder sichtbar noch erreichbar
    # (EIP-T-018). page7 ist ein Kontext ohne Admin-Cookie, also ein fremdes Geraet.
    page7 = browser.new_context().new_page()
    page7.goto(f"{BASE}/")
    page7.wait_for_load_state("networkidle")
    topbar = page7.inner_text(".topbar")
    # Der Admin-Link haengt an is_local und ist hier zu Recht da: der Testbrowser
    # laeuft auf demselben Rechner wie der Server. Dass er auf einem fremden Geraet
    # verschwindet, prueft smoke_test.py - im Browser ist das nicht darstellbar.
    check("T-018: Teilnehmeransicht zeigt keinen Debug-Zugang",
          "Debug" not in topbar, topbar.replace("\n", " "))
    page7.goto(f"{BASE}/debug")
    page7.wait_for_load_state("networkidle")
    body7 = page7.content()
    check("T-018: /debug fuer Teilnehmende abgewiesen, mit verstaendlichem Text",
          "vorbehalten" in body7 and "phase-a" not in body7)
    page7.close()

    page.goto(f"{BASE}/debug")
    page.wait_for_load_state("networkidle")
    check("Debug-Modul zeigt Ereignisse", "abgewiesen" in page.content())
    check("Debug-Seite zeigt den Authentifizierungsmodus unuebersehbar",
          "Authentifizierungsmodus" in page.content())
    page.screenshot(path=f"{SHOTS}/07_debug.png", full_page=True)

    page.goto(f"{BASE}/admin")
    page.wait_for_load_state("networkidle")
    check("Admin-Seite zeigt den Authentifizierungsmodus unuebersehbar",
          "Authentifizierungsmodus" in page.content())

    real_errors = [e for e in errors if "Failed to load resource" not in e]
    check("Keine JS-Fehler im Browser", not real_errors, "; ".join(real_errors[:3]))

    browser.close()

print(f"\nScreenshots: {SHOTS}")
if fails:
    print(f"{len(fails)} fehlgeschlagen:")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("Browser-Durchlauf komplett bestanden.")
