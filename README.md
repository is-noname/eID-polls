# eID-Umfrage — erste teilnahmefähige Version

Umsetzung von `EIP-RFC-20260725-001` §6/§7/§9 als lauffähige Web-App: Blindsignatur-Token,
zwei getrennte Ledger, öffentliches Bulletin Board als einzige Auszählungsquelle.

Ausführliche Bedienung, Begriffe und Grenzen: **[DOKU.md](DOKU.md)**.
Öffentlich stellen (Anbieter, Gratis-Grenzen, Vorführablauf): **[DEPLOY.md](DEPLOY.md)**.

> **Diese App führt keine echte Abstimmung durch.** Sie prüft keine Identitäten — der eID-Flow ist
> nicht gebaut — und der Betreiber hält den Signaturschlüssel allein. Was sie zeigt, ist das
> Verfahren dahinter: Blindsignatur, zwei getrennte Ledger, nachprüfbares Board.

### Verweise auf `EIP-RFC-…` und `EIP-ADR-…`

Code und Doku begründen Entscheidungen mit Paragrafen aus den Konzeptdokumenten (`EIP-RFC-20260725-001`
§4/§6/§7/§9 und weiteren). **Diese Dokumente liegen nicht in diesem Repo** — hier steht nur die App.
Die Verweise sind trotzdem stehen geblieben, weil sie sagen, *woraus* eine Regel folgt, statt sie als
Geschmacksfrage erscheinen zu lassen. Was zum Verstehen des Codes nötig ist, steht vollständig in
[DOKU.md](DOKU.md).

## Starten

```bash
bash "00_Labs/eID-poll/app/start.sh"
```

Oder das Desktop-Icon **eID-Umfrage** (`~/Schreibtisch/eID-Umfrage.desktop`, Port 8731).
Beenden über den Knopf oben rechts in der App — kein Terminal bleibt hängen.

- URL: `http://127.0.0.1:8731/`
- Admin-Token: `admin` (überschreibbar mit `EIDPOLL_ADMIN_TOKEN`)
- Datenbanken: `app/data/eidpoll.sqlite3` (Board) und `app/data/eidpoll.berechtigung.sqlite3` (Eligibility-Ledger, Schlüssel) — Pfad überschreibbar mit `EIDPOLL_DB`, die zweite Datei liegt immer daneben

## Ablauf für Teilnehmende

Die Oberfläche nennt die Schritte in Alltagssprache; in Klammern steht, was im Konzept dahintersteht.

1. Umfrage auf der Startseite öffnen
2. **Schritt 1 „Ausweisen"** (Phase A, Teil 1): „Mit Online-Ausweis anmelden" — öffnet einen Dialog
   „Ausweis auslesen". Dahinter steckt derzeit kein echter eID-Flow, siehe unten.
3. **Schritt 2 „Abstimmen"**: ein Klick, hinter dem beides steckt. Erst der Rest von Phase A —
   Stimm-Token im Browser erzeugen, verblinden, vom Server blind signieren lassen, im Browser
   entblinden —, dann sofort Phase B, die Stimmabgabe. Das Token existiert damit nur für die
   Sekunden dazwischen und muss keine Sitzung überleben (EIP-ADR-20260725-002, EIP-T-021).
   Während die Umfrage läuft, zeigt die Seite nur den Teilnahmezähler; die Verteilung erscheint
   erst nach dem Schließen. Verborgen ist sie dadurch nicht — aus dem Board unter „Nachweise"
   lässt sich der Zwischenstand auszählen (EIP-T-056).
4. **Schritt 3 „Dein Beleg"** sichern (`.txt`) und unter `/verify` die eigene Stimme nachschlagen.

Die Kryptografie steht auf den Teilnehmerseiten in aufklappbaren Blöcken, nicht im Fließtext:
sichtbar ist nur, was zum Abstimmen nötig ist.

Ein zweiter Abstimmversuch mit demselben Token wird abgewiesen, ein zweites Token für dieselbe
Identität ebenfalls — die Abwehr greift auf beiden Ebenen (Pseudonym in Phase A, Token in Phase B).

## Module

| Datei | Rolle |
|---|---|
| `auth.py` | `Authenticator.authenticate() -> pseudonym`. `CodeAuthenticator` aktiv (Zugangscode statt geprüftem Ausweis), `SamlEidAuthenticator` ist die leere Hülle für den echten Flow (§5). |
| `blind.py` | RSA-Blindsignatur nach RFC 9474, Serverseite. Abweichung von §4 dokumentiert (siehe unten). |
| `rfc9474_a4.json` | Der Testvektor aus RFC 9474 Anhang A.4, wörtlich übernommen. Beide Krypto-Seiten rechnen gegen dieselbe Datei — sonst prüfte jede Seite nur sich selbst. |
| `static/blind.js` | Dieselbe Krypto im Browser. Muss dort liegen, sonst gibt es kein Wahlgeheimnis gegen den Betreiber. |
| `static/ballot.js` | Der Stimmzettel-Flow: Token erzeugen, verblinden, signieren lassen, entblinden, abgeben — samt Zwischenstand nach Abbruch (EIP-ADR-20260725-002). Zusammen mit `blind.js` die vollständige Client-Strecke. |
| `static/beleg.js` | Der Beleg: Kassenbon, QR-Code, Textdatei. Reine Darstellung, kein Krypto. |
| `store.py` | SQLite: Eligibility-Ledger, Vote-Ledger, Board mit Batch-Kette (EIP-ADR-20260728-001). Board-Payloads als kanonisches JSON. |
| `poll_service.py` | Kern aus `PROTOTYPE_two-ledger/poll_logic.py`, Board als einzige Auszählungsquelle. |
| `auditor.py` | Unabhängige Nachrechnung des Boards — eine Datei, ohne Import aus dieser App. Wer der App misstraut, prüft mit ihr, nicht mit `verifikation.py` (EIP-T-071). |
| `demo.py` | Angriffsdemos (§9): Stimme einschleusen, Board-Eintrag umschreiben, Testzugang zurücksetzen. Liegt außerhalb des Kerns und wird nur eingehängt, wenn `Settings.demos` gesetzt ist — lokal an, öffentlich nur mit `EIDPOLL_DEMOS=1`. |
| `debug.py` + `/debug` | Fehler, Abweisungen, Inkonsistenzen in Echtzeit. Nur mit Admin-Anmeldung. |
| `web.py` | Seiten und JSON-API. `create_app(store_path, authenticator, settings)` baut eine Instanz; der Authenticator-Tausch ist damit ein Argument, kein Eingriff. `web:app` bleibt der uvicorn-Einstieg. |
| `static/app.css` | Ein Stylesheet, zwei Dichten: Teilnehmerseiten luftig (16 px, große Klickflächen), Admin und Debug kompakt über `body.dense`. Hell ist die Voreinstellung; `html[data-theme="dark"]` trägt die dunkle Umschaltung. |

## Was geprüft ist

```bash
python3 app/blind.py         # RFC-9474-Testvektor A.4 und Roundtrip, Serverseite
node app/blind_vektor.mjs    # derselbe Vektor gegen static/blind.js, Browserseite
python3 app/smoke_test.py    # sieben Abnahmepunkte, beide Angriffe, Zugangsschutz,
                             # zehn gleichzeitige Teilnahmen — ruft beide Vektorprüfungen mit auf
node app/ballot_test.mjs     # Stimmzettel-Flow gegen einen gestellten Server,
                             # ohne Browser: Zwischenstand nach Abbruch (ADR-002)

# Board unabhängig nachrechnen (nichts aus dieser App importiert):
python3 app/auditor.py https://<instanz>/api/board/<poll-id>

# im echten Browser (braucht Playwright und eine leere Datenbank):
cd app && EIDPOLL_DB=/tmp/bt.sqlite3 python3 -m uvicorn web:app --port 8899 &
python3 app/browser_test.py
```

`browser_test.py` ist der wichtigste der drei: nur dort zeigt sich, ob `static/blind.js`
bitgleich zu `blind.py` rechnet. Weicht es ab, weist der Server die Stimme als „Token-Signatur
ungültig" ab. `ballot_test.mjs` deckt das ausdrücklich **nicht** ab — dort ist die Signatur eine
Attrappe, geprüft wird der Zustandsverlauf. Alle drei laufen grün.

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

**2. Blindsignatur ist selbst implementiert.** RFC 9474, Variante
`RSABSSA-SHA384-PSSZERO-Deterministic`, 3072 Bit. Für Python existiert keine geprüfte Bibliothek
dafür (PyPI-Suche **2026-08-01** unter `blind-rsa-signatures`, `blind_signatures`, `blindsig`,
`rsa-blind-signatures`, `pyblindsig`, `rsabssa`, `blind-signature`, `pyblind-rsa`, `blindrsa`,
`py-blind-rsa`, `rfc9474`: jeweils keine Distribution). Geprüft zugekauft sind SHA-384 und die
PSS-Verifikation aus `cryptography`; selbst geschrieben sind EMSA-PSS-ENCODE, MGF1 und die
Blinding-Arithmetik — auf beiden Seiten, Python und JavaScript. Ungleich verteilt ist das
allerdings: Im serverseitigen Stimmweg läuft davon nur die rohe RSA-Operation in `blind_sign()`,
alles andere gehört dem Browser. Im Browser prüft seit EIP-T-080
**WebCrypto** die entblindete Signatur (RFC 9474 §4.4 Schritt 5) — bewusst nicht die eigene
PSS-Implementierung, sonst bestätigte handgeschriebener Code handgeschriebenen Code.

Seit EIP-T-008 rechnen **beide** Seiten gegen den Testvektor aus RFC 9474 Anhang A.4 nach
(`app/rfc9474_a4.json`, wörtlich aus dem RFC): Python in `blind.testvektor()`, JavaScript in
`node app/blind_vektor.mjs`, beides läuft in `smoke_test.py` mit. Jeder selbst geschriebene
Schritt wird einzeln geprüft, nicht nur der Roundtrip — ein Roundtrip wäre auch dann grün, wenn
Verblinden und Entblinden denselben Fehler machen. Das ist der stärkste Korrektheitsnachweis ohne
Audit, aber es ist einer über Korrektheit, nicht über Seitenkanäle. §4 bleibt für einen echten
Betrieb offen.

**3. Der Betreiber-Schutz ist unvollständig — wie im RFC beschrieben:**
- Die Batch-Kette entlarvt nur den Angreifer, der die Wurzeln stehen lässt. Wer Schreibzugriff hat,
  rechnet sie neu. Dagegen hilft erst ein extern verankerter Merkle-Root (§12).
- Die Ledger-Abrechnung macht Ballot-Stuffing sichtbar, aber ein Alleinbetreiber könnte die
  Berechtigten-Zahl mitfälschen. Echter Fix erst mit verteilter Schwellensignatur (§12).
- Netzwerk-Metadaten (IP, Timing) sind unangetastet — Risiko-Knoten 1, andere Schicht.
- Der Client-Krypto-Code wird vom Betreiber ausgeliefert (§10, Helios-Problem). Reproduzierbarer
  Build-Hash ist nicht eingerichtet.

Beide Angriffe lassen sich unter `/admin` vorführen und danach auf dem Board und im Debug-Modul
ansehen.

**4. Nicht gebaut** (§12): verteilte Schwellensignatur, Gegenzeichner gegen Split-View,
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
| `EIP-T-036` | Gegenzeichner der Batch-Wurzel gegen Split-View | Gruppe `unverkettbarkeit` |
| `EIP-T-007/8` | Build-Hash, auditierte Krypto | Gruppe `haertung` |

Ein physischer NFC-Leser und Testkarten werden **nicht** gebraucht: die AusweisApp bringt seit
V1.24 einen Karten-Simulator für die Test-PKI mit.

## Lizenz

**GNU Affero General Public License v3.0 or later** (AGPL-3.0-or-later) — voller Text in
[LICENSE](LICENSE).

Die Wahl folgt aus KODEX § 20: *„Der Quellcode ist öffentlich, unter einer Lizenz, die Prüfung und
Weiterbetrieb erlaubt."* Beides ist damit eingeräumt — lesen, prüfen, ändern, selbst betreiben.

Die Netzwerk-Klausel (§ 13 der Lizenz) ist der Grund für gerade diese Lizenz und keine permissive:
Die Unverkettbarkeit dieses Verfahrens entsteht im Browser, im ausgelieferten Client. Wer eine
**veränderte** Fassung öffentlich betreibt, muss deren Quellcode den Nutzern dieser Instanz
anbieten. Unter MIT oder Apache dürfte jemand eine still abgeänderte Fassung als „das Verfahren"
betreiben, ohne dass der Unterschied prüfbar wäre — das ist genau der Angriff, gegen den § 20
geschrieben ist. Unter der gewöhnlichen GPL griffe die Pflicht nicht, weil Serverbetrieb keine
Weitergabe ist.

Was das **nicht** heißt: Die Lizenz gilt für den Code, nicht für dieses Projekt als Betreiber. Sie
verpflichtet niemanden auf `KODEX.md`; wer eine eigene Instanz betreibt, betreibt sie unter eigenem
Namen und eigener Verantwortung (siehe § 14 zur Nachfolge).

### Fremdcode

`static/vendor-qrcode.js` — qrcode-generator von Kazuhiko Arase, **MIT**, Lizenzkopf unverändert in
der Datei. MIT-Code darf in ein AGPL-Werk aufgenommen werden; sein Lizenztext bleibt dabei stehen
und gilt für diese Datei fort.

Die Laufzeit-Abhängigkeiten aus `requirements.txt` (FastAPI, uvicorn, Jinja2, cryptography,
markdown, rfc3161-client, opentimestamps-client) werden installiert, nicht mitausgeliefert; sie
stehen sämtlich unter permissiven oder mit der AGPL verträglichen Lizenzen.
