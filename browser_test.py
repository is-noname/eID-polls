"""Durchlauf der sieben Abnahmepunkte im echten Browser (Playwright).

Prueft vor allem static/blind.js: nur hier zeigt sich, ob die Browser-Krypto
bitgleich zu blind.py rechnet - sonst weist der Server die Stimme als
"Token-Signatur ungueltig" ab.

    # Server mit frischer Datenbank starten
    EIDPOLL_DB=/tmp/bt.sqlite3 python3 -m uvicorn web:app --port 8899 &
    python3 browser_test.py            # optional: EIDPOLL_URL=http://127.0.0.1:8899

Die Datenbank muss leer sein - der Test legt eine Umfrage 'browsertest' an und
holt Tokens fuer feste Identitaeten.
"""

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


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
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
    page.fill("#options", "Ja\nNein\nTeilweise")
    page.click("#create-button")
    page.wait_for_timeout(1500)

    # --- Punkt 1: offene Umfrage auf der Startseite
    page.goto(f"{BASE}/")
    page.wait_for_load_state("networkidle")
    check("Punkt 1: Umfrage angelegt, auf Startseite sichtbar", POLL in page.content())
    check("Punkt 1b: OFFEN-Status auf der Startseite", "OFFEN" in page.content())
    page.screenshot(path=f"{SHOTS}/01_start.png", full_page=True)

    # --- Punkt 2: authentifizieren und Token holen (Phase A, Blinding im Browser)
    page.goto(f"{BASE}/poll/{POLL}")
    page.wait_for_load_state("networkidle")
    page.click("#auth-open-button")
    page.wait_for_selector("#auth-modal-backdrop:not(.hidden)")
    page.fill("#credential", "testperson1")
    page.click("#auth-confirm-button")
    page.wait_for_timeout(1500)
    page.goto(f"{BASE}/poll/{POLL}")
    page.wait_for_load_state("networkidle")
    check("Punkt 2: authentifiziert (Schritt 1 erledigt)",
          "Ausweis erfolgreich ausgelesen." in page.content())
    check("Punkt 2b: kein roher Stub-Praefix in der Teilnehmeransicht",
          "STUB-NO-REAL-IDENTITY" not in page.content())
    check("Punkt 2c: kein Wort ueber Test/Stub/Simulation/Code in der Teilnehmeransicht",
          not any(w in page.content() for w in ["Stub", "Simulation", "Zugangscode"]))

    page.click("#token-button")
    page.wait_for_selector("#token-state:not(.hidden)", timeout=20000)
    state = page.evaluate(f"() => localStorage.getItem('eidpoll:{POLL}')")
    check("Punkt 2b: im Browser verblindet, Token signiert im localStorage",
          state is not None and '"sig"' in state)

    # --- EIP-T-016: Tab schliessen und zurueckkommen - Token bleibt da (localStorage)
    page.evaluate("() => sessionStorage.clear()")
    page.goto(f"{BASE}/poll/{POLL}")
    page.wait_for_load_state("networkidle")
    check("T-016: Token ueberlebt Tab-Schliessen (Schritt 2 bleibt erledigt)",
          "done" in (page.get_attribute("#step-token", "class") or ""))

    # --- EIP-T-016: Sicherungsdatei aus Schritt 2 herunterladbar
    with page.expect_download() as dl_info:
        page.click("#token-save-button")
    download_backup = dl_info.value
    backup_path = f"{SHOTS}/stimm-token_{POLL}.json"
    download_backup.save_as(backup_path)
    check("T-016: Stimm-Token-Sicherungsdatei aus Schritt 2 heruntergeladen",
          os.path.exists(backup_path))

    # --- Punkt 3: abstimmen
    check("Punkt 3: waehrend der Laufzeit keine Verteilung sichtbar", "Ergebnis" not in page.content())
    page.check("input[value='Ja']")
    page.click("#vote-button")
    page.wait_for_selector("#step-receipt:not(.hidden)", timeout=20000)
    check("Punkt 3b: Stimme angenommen (Server akzeptiert die PSS-Signatur)", True)
    page.screenshot(path=f"{SHOTS}/02_abgestimmt.png", full_page=True)

    # --- Punkt 4: Verifikations-Beleg
    page.wait_for_timeout(500)
    token_node = page.query_selector("#receipt-token")
    receipt = (token_node.text_content() or "") if token_node else ""
    token = re.search(r"^([0-9a-f]{64})$", receipt.strip())
    check("Punkt 4: Verifikations-Beleg mit Token angezeigt", token is not None)
    if token is None:
        browser.close()
        sys.exit(1)

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
    page2.click("#auth-open-button")
    page2.wait_for_selector("#auth-modal-backdrop:not(.hidden)")
    page2.fill("#credential", "testperson2")
    page2.click("#auth-confirm-button")
    page2.wait_for_timeout(1500)
    page2.goto(f"{BASE}/poll/{POLL}")
    page2.wait_for_load_state("networkidle")
    page2.click("#token-button")
    page2.wait_for_selector("#token-state:not(.hidden)", timeout=20000)
    page2.check("input[value='Nein']")
    page2.click("#vote-button")
    page2.wait_for_selector("#step-receipt:not(.hidden)", timeout=20000)

    # --- Punkt 5b: zweites Token fuer dieselbe Identitaet (Phase A)
    page3 = browser.new_context().new_page()
    page3.goto(f"{BASE}/poll/{POLL}")
    page3.click("#auth-open-button")
    page3.wait_for_selector("#auth-modal-backdrop:not(.hidden)")
    page3.fill("#credential", "TESTPERSON1")  # gleicher Code, andere Schreibweise
    page3.click("#auth-confirm-button")
    page3.wait_for_timeout(1500)
    page3.goto(f"{BASE}/poll/{POLL}")
    page3.wait_for_load_state("networkidle")
    page3.click("#token-button")
    page3.wait_for_selector(".toast.err", timeout=20000)
    check("Punkt 5b: zweites Stimm-Token fuer dieselbe Identitaet abgewiesen",
          "abgeholt" in page3.inner_text(".toast.err"), page3.inner_text(".toast.err"))

    # --- Fehlerfaelle im Dialog: unbekannte Nummer, leeres Feld, Abbruch
    page4 = browser.new_context().new_page()
    page4.goto(f"{BASE}/poll/{POLL}")
    page4.click("#auth-open-button")
    page4.wait_for_selector("#auth-modal-backdrop:not(.hidden)")
    page4.fill("#credential", "unbekannt-999")
    page4.click("#auth-confirm-button")
    page4.wait_for_selector(".toast.err", timeout=10000)
    check("Fehlerfall: unbekannte Ausweisnummer abgewiesen, finaler Text",
          "nicht hinterlegt" in page4.inner_text(".toast.err"), page4.inner_text(".toast.err"))

    page4.fill("#credential", "")
    page4.click("#auth-confirm-button")
    page4.wait_for_timeout(500)
    check("Fehlerfall: leeres Feld abgewiesen, finaler Text",
          "Ausweisnummer eingeben" in page4.inner_text(".toast.err"), page4.inner_text(".toast.err"))

    page4.click("#auth-cancel-button")
    page4.wait_for_timeout(300)
    classes = page4.get_attribute("#auth-modal-backdrop", "class") or ""
    check("Fehlerfall: Dialog abbrechbar, schliesst sich wieder", "hidden" in classes, classes)

    # --- EIP-T-016: Wiederherstellung nach Geraetewechsel aus der Sicherungsdatei
    page5 = browser.new_context().new_page()
    page5.goto(f"{BASE}/poll/{POLL}")
    page5.click("#auth-open-button")
    page5.wait_for_selector("#auth-modal-backdrop:not(.hidden)")
    page5.fill("#credential", "testperson5")
    page5.click("#auth-confirm-button")
    page5.wait_for_timeout(1200)
    page5.goto(f"{BASE}/poll/{POLL}")
    page5.wait_for_load_state("networkidle")
    page5.click("#token-button")
    page5.wait_for_selector("#token-state:not(.hidden)", timeout=20000)
    with page5.expect_download() as dl5:
        page5.click("#token-save-button")
    restore_path = f"{SHOTS}/restore_{POLL}.json"
    dl5.value.save_as(restore_path)

    page6 = browser.new_context().new_page()  # "anderes Geraet" - keine Browserdaten von page5
    page6.goto(f"{BASE}/poll/{POLL}")
    page6.wait_for_load_state("networkidle")
    page6.set_input_files("#token-restore-input", restore_path)
    page6.wait_for_timeout(500)
    check("T-016: Stimm-Token nach Geraetewechsel aus Datei wiederhergestellt",
          "done" in (page6.get_attribute("#step-token", "class") or ""))
    page6.check("input[value='Teilweise']")
    page6.click("#vote-button")
    page6.wait_for_selector("#step-receipt:not(.hidden)", timeout=20000)
    check("T-016: nach Wiederherstellung erfolgreich abgestimmt", True)

    stored_after_vote = page6.evaluate(f"() => localStorage.getItem('eidpoll:{POLL}')")
    check(
        "T-016: Token nach Abgabe aus dem Speicher entfernt, Belegdaten bleiben",
        stored_after_vote is not None
        and '"token"' not in stored_after_vote
        and '"index"' in stored_after_vote,
        stored_after_vote,
    )

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

    page.goto(f"{BASE}/verify?poll={POLL}&token={token.group(1)}")
    page.wait_for_load_state("networkidle")
    check("Punkt 4b: Verifikationsseite findet die eigene Stimme",
          "Token gefunden" in page.content() and "Ja" in page.inner_text(".banner.ok"))
    page.screenshot(path=f"{SHOTS}/05_verify.png", full_page=True)

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
    page.screenshot(path=f"{SHOTS}/06_debug.png", full_page=True)

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
