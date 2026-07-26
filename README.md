# eID-Umfrage — erste teilnahmefähige Version

Umsetzung von `EIP-RFC-20260725-001` §6/§7/§9 als lauffähige Web-App: Blindsignatur-Token,
zwei getrennte Ledger, öffentliches Bulletin Board als einzige Auszählungsquelle.

Ausführliche Bedienung, Begriffe und Grenzen: **[DOKU.md](DOKU.md)**.

## Starten

```bash
bash "00_Labs/eID-poll/app/start.sh"
```

Oder das Desktop-Icon **eID-Umfrage** (`~/Schreibtisch/eID-Umfrage.desktop`, Port 8731).
Beenden über den Knopf oben rechts in der App — kein Terminal bleibt hängen.

- URL: `http://127.0.0.1:8731/`
- Admin-Token: `admin` (überschreibbar mit `EIDPOLL_ADMIN_TOKEN`)
- Datenbank: `app/data/eidpoll.sqlite3` (überschreibbar mit `EIDPOLL_DB`)

## Ablauf für Teilnehmende

Die Oberfläche nennt die Schritte in Alltagssprache; in Klammern steht, was im Konzept dahintersteht.

1. Umfrage auf der Startseite öffnen
2. **Schritt 1 „Ausweisen"** (Phase A, Teil 1): „Mit Online-Ausweis anmelden" — öffnet einen Dialog
   „Ausweis auslesen". Dahinter steckt derzeit kein echter eID-Flow, siehe unten.
3. **Schritt 2 „Stimmrecht abholen"** (Phase A, Teil 2): Stimm-Token wird im Browser erzeugt,
   verblindet, vom Server blind signiert und im Browser wieder entblindet. Es liegt danach nur im
   `localStorage`; die Sicherungsdatei ist der Weg über einen Gerätewechsel (EIP-T-016).
4. **Schritt 3 „Abstimmen"** (Phase B): Während die Umfrage läuft, ist nur der Teilnahmezähler
   sichtbar (§7).
5. **Schritt 4 „Dein Beleg"** sichern (`.txt`) und unter `/verify` die eigene Stimme nachschlagen.

Die Kryptografie steht auf den Teilnehmerseiten in aufklappbaren Blöcken, nicht im Fließtext:
sichtbar ist nur, was zum Abstimmen nötig ist.

Ein zweiter Abstimmversuch mit demselben Token wird abgewiesen, ein zweites Token für dieselbe
Identität ebenfalls — die Abwehr greift auf beiden Ebenen (Pseudonym in Phase A, Token in Phase B).

## Module

| Datei | Rolle |
|---|---|
| `auth.py` | `Authenticator.authenticate() -> pseudonym`. `CodeAuthenticator` aktiv (Zugangscode statt geprüftem Ausweis), `SamlEidAuthenticator` ist die leere Hülle für den echten Flow (§5). |
| `blind.py` | RSA-Blindsignatur nach RFC 9474, Serverseite. Abweichung von §4 dokumentiert (siehe unten). |
| `static/blind.js` | Dieselbe Krypto im Browser. Muss dort liegen, sonst gibt es kein Wahlgeheimnis gegen den Betreiber. |
| `store.py` | SQLite: Eligibility-Ledger, Vote-Ledger, Board-Hash-Kette. Board-Payloads als kanonisches JSON. |
| `poll_service.py` | Kern aus `PROTOTYPE_two-ledger/poll_logic.py`, Board als einzige Auszählungsquelle. |
| `debug.py` + `/debug` | Fehler, Abweisungen, Inkonsistenzen in Echtzeit. Nur mit Admin-Anmeldung. |
| `web.py` | Seiten und JSON-API. |
| `static/app.css` | Ein Stylesheet, zwei Dichten: Teilnehmerseiten luftig (16 px, große Klickflächen), Admin und Debug kompakt über `body.dense`. Hell ist die Voreinstellung; `html[data-theme="dark"]` trägt die dunkle Umschaltung. |

## Was geprüft ist

```bash
python3 app/blind.py         # Krypto-Roundtrip (RFC 9474)
python3 app/smoke_test.py    # sieben Abnahmepunkte, beide Angriffe, Zugangsschutz,
                             # zehn gleichzeitige Teilnahmen

# im echten Browser (braucht Playwright und eine leere Datenbank):
cd app && EIDPOLL_DB=/tmp/bt.sqlite3 python3 -m uvicorn web:app --port 8899 &
python3 app/browser_test.py
```

`browser_test.py` ist der wichtigere der beiden: nur dort zeigt sich, ob `static/blind.js`
bitgleich zu `blind.py` rechnet. Weicht es ab, weist der Server die Stimme als „Token-Signatur
ungültig" ab. Beide Tests laufen grün.

## Bewusste Abweichungen und Grenzen

**1. Authentifizierung prüft keinen echten Ausweis.** Statt eines Ausweises verlangt
`CodeAuthenticator` einen Zugangscode aus einer konfigurierten Liste (Voreinstellung
`testperson1`–`testperson100`, austauschbar über `EIDPOLL_ACCESS_CODES` /
`EIDPOLL_ACCESS_CODES_FILE`, ohne Codeänderung). Ein Code steht für einen bereits gültig
geprüften Ausweis und wird zu einem stabilen Pseudonym gehasht. Damit gilt „ein Mensch, eine
Stimme" nur innerhalb der aktuellen Testrunde, nicht als offene Registrierung. Für Teilnehmende
ist das bewusst **nicht sichtbar** (EIP-T-014) — der Dialog „Ausweis auslesen" nennt weder Code
noch Test noch Simulation, und der Pseudonym-Präfix `STUB-NO-REAL-IDENTITY:` bleibt nur im
gespeicherten Datensatz. Sichtbar ist der aktive Modus stattdessen unübersehbar in **Admin** und
**Debug**. Auf dieser Maschine fehlen AusweisApp, ein eID-Server gegen Test-PKI und
Test-Ausweise; der echte SAML-SP bedient später dieselbe Schnittstelle, ohne dass Krypto oder
Ledger sich ändern.

**2. Blindsignatur ist selbst implementiert.** RFC 9474 (RSABSSA-SHA384-PSS-Deterministic), 2048
Bit. Für Python existiert keine geprüfte Bibliothek dafür (PyPI-Suche 2026-07-25 unter
`blind-rsa-signatures`, `blind_signatures`, `blindsig`, `rsa-blind-signatures`, `pyblindsig`:
jeweils keine Distribution). Geprüft zugekauft sind SHA-384 und die PSS-Verifikation aus
`cryptography`; selbst geschrieben sind EMSA-PSS-ENCODE, MGF1 und die Blinding-Arithmetik — auf
beiden Seiten, Python und JavaScript. Das ist besser als der textbook-Chaum des Prototyps und
ersetzt trotzdem keinen Audit. §4 bleibt für einen echten Betrieb offen.

**3. Der Betreiber-Schutz ist unvollständig — wie im RFC beschrieben:**
- Die Hash-Kette entlarvt nur den Angreifer, der die Hashes stehen lässt. Wer Schreibzugriff hat,
  rechnet sie neu. Dagegen hilft erst ein extern verankerter Merkle-Root (§12).
- Die Ledger-Abrechnung macht Ballot-Stuffing sichtbar, aber ein Alleinbetreiber könnte die
  Berechtigten-Zahl mitfälschen. Echter Fix erst mit verteilter Schwellensignatur (§12).
- Netzwerk-Metadaten (IP, Timing) sind unangetastet — Risiko-Knoten 1, andere Schicht.
- Der Client-Krypto-Code wird vom Betreiber ausgeliefert (§10, Helios-Problem). Reproduzierbarer
  Build-Hash ist nicht eingerichtet.

Beide Angriffe lassen sich unter `/admin` vorführen und danach auf dem Board und im Debug-Modul
ansehen.

**4. Nicht gebaut** (§12, unverändert): verteilte Schwellensignatur, externer Merkle-Anker,
Netzwerk-Anonymisierung, Produktiv-Berechtigungszertifikat, eIDAS-Ausland, Multi-Tenant.
Die UI verspricht nichts davon.

## Nächste Schritte

Plan: `EIP-RFC-20260725-002_eID-Flow-Umsetzungsplan.md`. Nachverfolgung in `tickets/`:

| Ticket | | |
|---|---|---|
| `EIP-T-001` | Test-eID-Server-Zugang beantragen | einzige externe Abhängigkeit |
| `EIP-T-002` | AusweisApp mit Karten-Simulator lokal verifizieren | ohne Hardware machbar |
| `EIP-T-003` | ADR: SAML-SP in Python oder als Java-Sidecar | vor T-004 zu entscheiden |
| `EIP-T-004` | `SamlEidAuthenticator` füllen | blockiert durch T-001 |
| `EIP-T-005` | Stub ablösen, Modusanzeige | blockiert durch T-004 |
| `EIP-T-006/7/8` | Merkle-Anker, Build-Hash, auditierte Krypto | Gruppe `haertung` |

Ein physischer NFC-Leser und Testkarten werden **nicht** gebraucht: die AusweisApp bringt seit
V1.24 einen Karten-Simulator für die Test-PKI mit.
