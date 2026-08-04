"""Durchgang der Buergerkette auf schmalem Schirm (EIP-T-108, 360px).

Kein zweiter Funktionstest - der Ablauf selbst ist schon durch browser_test.py
abgedeckt. Hier zaehlt nur die Geometrie: passt die Kette index -> poll ->
eid-sim -> Beleg -> verify -> board in einen 360x640-Viewport, ohne dass etwas
waagerecht scrollt oder ein Bedienelement unter 44px Hoehe faellt.

    EIDPOLL_DB=/tmp/mt.sqlite3 EIDPOLL_ADMIN_TOKEN=admin python3 -m uvicorn web:app --port 8899 &
    python3 mobile_test.py            # optional: EIDPOLL_URL=http://127.0.0.1:8899

Die Datenbank muss leer sein - der Test legt eine eigene Umfrage an.
"""

import os
import re
import sys
import tempfile

from playwright.sync_api import Page, sync_playwright

BASE = os.environ.get("EIDPOLL_URL", "http://127.0.0.1:8899")
SHOTS = tempfile.mkdtemp(prefix="eidpoll-mobile-")
POLL = "mobiltest"
BREITE, HOEHE = 360, 640
MINDESTMASS = 44  # px, Daumen-Bedienbarkeit
fails: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(f"[{'  ok  ' if cond else ' FEHL '}] {label}{(' - ' + detail) if detail else ''}")
    if not cond:
        fails.append(label)


def kein_waagerechtes_scrollen(page: Page, label: str) -> None:
    """scrollWidth > clientWidth heisst: irgendwo ragt Inhalt ueber den Rand."""
    breite = page.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth,"
        " client: document.documentElement.clientWidth})"
    )
    check(
        f"{label}: kein waagerechtes Scrollen ({breite['scroll']}px Inhalt in {breite['client']}px)",
        breite["scroll"] <= breite["client"],
        str(breite),
    )


def erreichbare_ziele(page: Page, selectors: list[str], label: str) -> None:
    """Sichtbare Treffer jedes Selektors muessen >=44px hoch sein (Daumenmass).

    Ein Selektor ohne jeden sichtbaren Treffer ist kein bestandener Test,
    sondern ein Zeichen, dass die Seite nicht wie erwartet geladen hat.
    """
    zu_klein = []
    gefunden = 0
    for sel in selectors:
        for el in page.query_selector_all(sel):
            if not el.is_visible():
                continue
            gefunden += 1
            box = el.bounding_box()
            if box and box["height"] < MINDESTMASS - 0.5:
                zu_klein.append(f"{sel} ({box['height']:.0f}px)")
    check(f"{label}: erwartete Bedienelemente vorhanden", gefunden > 0, str(selectors))
    check(f"{label}: Bedienelemente mindestens {MINDESTMASS}px hoch", not zu_klein,
          ", ".join(zu_klein))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": BREITE, "height": HOEHE},
        device_scale_factor=2,
        has_touch=True,
        is_mobile=True,
        accept_downloads=True,
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    # --- Umfrage anlegen (eigener Poll, damit der Lauf unabhaengig von
    # browser_test.py auf einer leeren Datenbank steht)
    page.goto(f"{BASE}/admin")
    page.wait_for_load_state("networkidle")
    page.fill("#admin-token", os.environ.get("EIDPOLL_ADMIN_TOKEN", "admin"))
    page.click("#login-button")
    page.wait_for_timeout(1200)
    page.goto(f"{BASE}/admin")
    page.wait_for_load_state("networkidle")
    page.fill("#poll-id", POLL)
    page.fill("#question", "Passt die Kette auf ein schmales Telefon?")
    page.fill("#options", "Ja\nEher nicht\nEnthaltung")
    page.click("#create-button")
    page.wait_for_timeout(1500)

    # --- index
    page.goto(f"{BASE}/")
    page.wait_for_load_state("networkidle")
    check("index: Umfrage sichtbar", POLL in page.content())
    kein_waagerechtes_scrollen(page, "index")
    erreichbare_ziele(page, ["a.row-title a", ".topbar a"], "index")
    page.screenshot(path=f"{SHOTS}/01_index.png", full_page=True)

    # --- poll
    page.goto(f"{BASE}/poll/{POLL}")
    page.wait_for_load_state("networkidle")
    kein_waagerechtes_scrollen(page, "poll (vor Anmeldung)")
    erreichbare_ziele(page, ["#auth-open-button", "#vote-button"], "poll (vor Anmeldung)")
    page.screenshot(path=f"{SHOTS}/02_poll.png", full_page=True)

    # --- eid-sim: derselbe Weg wie in browser_test.py, aber mit Geometrie-Checks
    page.click("#auth-open-button")
    page.wait_for_selector("#dienst-weiter")
    kein_waagerechtes_scrollen(page, "eid-sim: Dienst")
    erreichbare_ziele(page, ["#dienst-weiter"], "eid-sim: Dienst")
    page.click("#dienst-weiter")

    page.wait_for_selector("#ausweisnummer")
    kein_waagerechtes_scrollen(page, "eid-sim: Kartenschritt")
    erreichbare_ziele(page, ["#karte-lesen", "#ausweisnummer"], "eid-sim: Kartenschritt")
    page.fill("#ausweisnummer", "testperson1")
    page.click("#karte-lesen")

    page.wait_for_selector("#auskunft-ok")
    kein_waagerechtes_scrollen(page, "eid-sim: Datenauskunft")
    erreichbare_ziele(page, ["#auskunft-ok"], "eid-sim: Datenauskunft")
    page.screenshot(path=f"{SHOTS}/03_eidsim_auskunft.png", full_page=True)
    page.click("#auskunft-ok")

    page.wait_for_selector("#pin")
    kein_waagerechtes_scrollen(page, "eid-sim: PIN")
    erreichbare_ziele(page, ["#pin-ok", "#pin"], "eid-sim: PIN")
    page.screenshot(path=f"{SHOTS}/04_eidsim_pin.png", full_page=True)
    page.fill("#pin", "123456")
    page.click("#pin-ok")
    page.wait_for_load_state("networkidle")

    # --- poll nach Anmeldung, abstimmen
    page.goto(f"{BASE}/poll/{POLL}")
    page.wait_for_load_state("networkidle")
    check("poll: nach Anmeldung Schritt 1 erledigt", "Ausweis erfolgreich ausgelesen" in page.content())
    kein_waagerechtes_scrollen(page, "poll (nach Anmeldung)")
    erreichbare_ziele(page, ["label.choice", "#vote-button"], "poll (nach Anmeldung)")
    page.screenshot(path=f"{SHOTS}/05_poll_angemeldet.png", full_page=True)

    page.check("input[value='Ja']")
    page.click("#vote-button")
    page.wait_for_selector("#step-receipt:not(.hidden)", timeout=20000)
    check("poll: Stimme angenommen", True)

    # --- Beleg
    page.wait_for_timeout(500)
    kein_waagerechtes_scrollen(page, "Beleg")
    erreichbare_ziele(page, ["#receipt-download", "#receipt-copy"], "Beleg")
    token_node = page.query_selector("#receipt-token")
    receipt = (token_node.text_content() or "") if token_node else ""
    token = re.search(r"^([0-9a-f]{64})$", receipt.strip())
    check("Beleg: 64-Zeichen-Token angezeigt, ohne Scrollen im eigenen Container", token is not None)
    if token is None:
        browser.close()
        sys.exit(1)
    hex_box = page.query_selector("#receipt-token").bounding_box()
    viewport_box = page.evaluate("() => ({w: window.innerWidth})")
    check(
        "Beleg: 64-Zeichen-Hexwert bricht im eigenen Container statt zu ueberlaufen",
        hex_box is not None and hex_box["width"] <= viewport_box["w"],
        f"hex-box {hex_box}, viewport {viewport_box}",
    )
    page.screenshot(path=f"{SHOTS}/06_beleg.png", full_page=True)

    beleg_pfad = os.path.join(SHOTS, "beleg.txt")
    with page.expect_download() as dl:
        page.click("#receipt-download")
    dl.value.save_as(beleg_pfad)

    # --- schliessen, damit der Eintrag veroeffentlicht wird (Board ist die
    # einzige Auszaehlungsquelle - ohne Schliessen findet /verify nichts)
    page.goto(f"{BASE}/admin")
    page.wait_for_load_state("networkidle")
    page.once("dialog", lambda d: d.accept())
    page.click(f".close-button[data-poll='{POLL}']")
    page.wait_for_timeout(1500)

    # --- verify: Beleg-Datei einlesen (Alltagsweg ohne zweites Geraet)
    page.goto(f"{BASE}/verify")
    page.wait_for_load_state("networkidle")
    kein_waagerechtes_scrollen(page, "verify (leer)")
    erreichbare_ziele(page, ["#beleg-pick", "button[type=submit]"], "verify (leer)")
    page.set_input_files("#beleg-file", beleg_pfad)
    page.wait_for_selector("#verify-result.ok", timeout=10_000)
    check("verify: Token aus Beleg-Datei gefunden", "Token gefunden" in page.content())
    kein_waagerechtes_scrollen(page, "verify (Ergebnis)")
    page.screenshot(path=f"{SHOTS}/07_verify.png", full_page=True)

    # --- board: Tabellen, Ledger-Abrechnung, Kettenpruefung
    page.goto(f"{BASE}/board/{POLL}")
    page.wait_for_load_state("networkidle")
    check("board: Ergebnis sichtbar", "Ergebnis" in page.content())
    check("board: eigenes Token wiederfindbar", token.group(1) in page.content())
    kein_waagerechtes_scrollen(page, "board")
    page.screenshot(path=f"{SHOTS}/08_board.png", full_page=True)

    real_errors = [e for e in errors if "Failed to load resource" not in e]
    check("Keine JS-Fehler im Browser (360px)", not real_errors, "; ".join(real_errors[:3]))

    browser.close()

print(f"\nScreenshots: {SHOTS}")
if fails:
    print(f"\n{len(fails)} Befund(e):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("\nAlle Pruefungen bestanden.")
