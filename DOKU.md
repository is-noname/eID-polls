# eID-Umfrage — Dokumentation

Bedienung, Aufbau und Grenzen der App. Technische Kurzfassung: [README.md](README.md).
Konzept und Begründungen: `EIP-RFC-20260725-001`, `EIP-ADR-20260725-001`, `CONTEXT.md`.

---

## 1. Was die App tut

Eine Umfrage mit dem Anspruch **„ein Ausweis, eine Stimme, anonym"**. Der Betreiber soll erfahren,
*wie viele* wie gestimmt haben, aber nicht *wer* wie gestimmt hat — und trotzdem soll jeder das
Ergebnis nachrechnen und die eigene Stimme wiederfinden können.

Das geht nicht mit einer einfachen Stimmentabelle, denn wer die Berechtigung prüft, kennt die
Person. Deshalb sind Berechtigung und Stimmabgabe in zwei getrennte Phasen zerlegt, die
kryptografisch nicht verkettbar sind:

| | Phase A — Berechtigung | Phase B — Stimmabgabe |
|---|---|---|
| Wer spricht mit dem Server? | die identifizierte Person | ein anonymer Browser |
| Was bekommt der Server? | ein Pseudonym und eine **verblindete** Zahl | ein Token, eine Signatur, eine Stimme |
| Was merkt er sich? | „dieses Pseudonym hat sein Token abgeholt" | „dieses Token ist verbraucht" |
| Kann er beides verbinden? | **nein** — er hat das Token nie unverblindet gesehen | |

---

## 2. Die vier Grundbegriffe

**Stimm-Token.** 32 Zufallsbytes, die im Browser entstehen. Sie sind der einzige Bezug zwischen
einer Person und ihrer Stimme — und sie verlassen den Browser nie unverblindet.

**Blindsignatur.** Der Server unterschreibt das Token, ohne es zu sehen. Das Bild dazu: das Token
steckt in einem Umschlag mit Blaupapier; der Server unterschreibt außen, die Unterschrift schlägt
innen durch. Danach nimmt der Browser das Token aus dem Umschlag — die Unterschrift ist gültig,
aber der Server hat den Inhalt nie gesehen und erkennt ihn später nicht wieder.

**Die zwei Ledger.**
- *Eligibility-Ledger*: gehashte Pseudonyme. Weiß „hat abgeholt", nicht „wie gestimmt".
- *Vote-Ledger*: verbrauchte Tokens. Reiner Doppelabstimmungs-Index — **keine Stimmen**.

**Bulletin Board.** Eine öffentliche, fortlaufende Kette von Einträgen; jeder trägt den Hash des
vorherigen. Hier stehen die Stimmen, und **nur hieraus** wird ausgezählt. Das ist wichtiger als es
klingt: würde intern anders gezählt als öffentlich einsehbar ist, wäre die öffentliche Prüfung
wertlos. Genau dieser Fehler steckte im Prototyp (`PROTOTYPE_two-ledger/NOTES.md`, Fund 1).

---

## 3. Bedienung

### Starten und beenden

Desktop-Icon **eID-Umfrage** oder `bash app/start.sh`. Danach `http://127.0.0.1:8731/`.
Beenden über den Knopf **oben rechts** in der App — er stoppt den Server, nicht nur den Tab.

### Als Admin: Umfrage anlegen

**Admin** → Token eingeben (Voreinstellung `admin`) → Formular:

- **Umfrage-ID** — kurz, nur Buchstaben/Ziffern/`-`/`_`; steht später in jeder Board-Zeile
- **Frage** — eine Frage pro Umfrage
- **Optionen** — eine pro Zeile, mindestens zwei, fest vorgegeben; kein Freitext (§8)

Freitext ist ausgeschlossen, weil er die maschinelle Auszählung bricht und deanonymisieren kann.

### Als Teilnehmer: abstimmen

1. **Umfragen** → Umfrage öffnen
2. **Schritt 1 — Identität.** Knopf „Mit Online-Ausweis anmelden" öffnet den Dialog „Ausweis
   auslesen". Dahinter steckt derzeit `CodeAuthenticator`: ein Zugangscode aus einer
   konfigurierten Liste ersetzt den geprüften Ausweis, siehe Abschnitt 5. Derselbe Code ergibt
   immer dasselbe Pseudonym.
3. **Schritt 2 — Abstimmen.** Ein Klick, hinter dem zwei Dinge stecken: Der Browser erzeugt das
   Stimm-Token, verblindet es, lässt es signieren, entblindet es wieder — und gibt damit sofort
   die Stimme ab. Mehrfachauswahl ist möglich; die *Kombination* steht so im Board.
4. **Schritt 3 — Beleg.** Als `.txt` sichern. Er enthält das Stimm-Token.

Während die Umfrage läuft, zeigt die Seite nur die Teilnahmezahl. Die Verteilung erscheint erst
nach dem Schließen (§7) — Zwischenstände beeinflussen laufende Abstimmungen und erlauben
Timing-Rückschlüsse.

> **Warum nur noch ein Schritt:** Früher war das Token-Holen ein eigener Schritt, und das Token
> musste zwischen zwei Klicks im Browserspeicher überleben. Wer den Tab dazwischen schloss,
> verlor es — und bekam in Phase A kein zweites. Heute existiert es nur für die Sekunden zwischen
> Signatur und Stimmabgabe (EIP-ADR-20260725-002). Bricht ausgerechnet dieser Moment ab, liegt es
> für den nächsten Versuch bereit; ein zweites wird weiterhin nicht ausgegeben, denn das ist die
> Doppelabstimmungs-Abwehr.

### Eigene Stimme prüfen

**Verifikation** → Umfrage wählen, Token aus dem Beleg einfügen. Die App zeigt die Auswahl, die
unter diesem Token im Board steht.

Dieser Beleg ist zugleich eine **Quittung** — wer ihn vorzeigt, beweist, wie er gestimmt hat. Das
ist eine bewusste Entscheidung: individuelle Verifizierbarkeit und Quittungsfreiheit schließen
einander aus (`EIP-ADR-20260725-001`). Konsequenz: Stimmenkauf und Nötigung sind technisch nicht
verhindert.

### Ergebnis und öffentliche Prüfung

**Board** (`/board/{id}`) zeigt fünf Kennzahlen und darunter die vollständige Kette:

| Kennzahl | Bedeutung | Wenn sie ausschlägt |
|---|---|---|
| Kette | jeder Eintrag passt zum Hash des vorherigen | Ein Eintrag wurde nachträglich verändert → **kein Ergebnis** |
| Token-Signaturen | jede Stimme trägt eine gültige Signatur | Eine Stimme wurde eingefügt, ohne signiert zu sein → **kein Ergebnis** |
| Berechtigte | wie viele Token ausgegeben wurden | — |
| Stimmen im Board | wie viele Stimmen eingegangen sind | — |
| Ledger-Abrechnung | Stimmen ≤ Berechtigte? | Mehr Stimmen als Berechtigte = sichtbarer Manipulationsbeweis |

Beide Zahlen der Abrechnung stammen aus dem Board — also aus dem, was jeder Dritte sieht.

Unten steht der **öffentliche Token-Schlüssel**. Damit lässt sich jede Stimme unabhängig prüfen
(RSASSA-PSS über SHA-384, Salt-Länge 0), und die Kette mit
`sha256("index|prev_hash|payload")` nachrechnen.

### Selbst nachrechnen, ohne diesem Server zu glauben

Die Board-Seite zeigt einen Prüfbericht, den der Server rechnet. Genau denselben Bericht rechnet
`verifikation.py` aus dem exportierten Board — ohne Datenbank und ohne den privaten
Signaturschlüssel:

```bash
curl -o board.json http://127.0.0.1:8731/api/board/{poll_id}
python3 app/verifikation.py board.json
python3 app/verifikation.py board.json --token <mein-token-hex>   # eigene Stimme suchen
```

Ausgegeben werden Kettenstatus, Signaturstatus, Ledger-Abrechnung und Auszählung. Exit-Code 0
heißt: nichts gefunden. Exit-Code 1 heißt: mindestens ein Befund — die Zahlen darüber sind dann
nicht belastbar.

Der Export enthält den öffentlichen Schlüssel mit, aus Bequemlichkeit. Wer dem Betreiber nicht
glaubt, nimmt ihn aus einer unabhängigen Quelle und übergibt ihn mit `--pubkey key.pem`; sonst
prüft man das Board nur gegen sich selbst.

**Was das nicht leistet:** Der Export kommt weiterhin von diesem Server. Zwei Betrachter können
zwei verschiedene, jeweils in sich stimmige Boards bekommen, und ein Betreiber mit Schreibzugriff
rechnet die Kette nach einer Änderung neu durch. Dagegen hilft nur ein extern verankerter
Merkle-Root und Gegenzeichner (§12).

### Debug-Modul

`/debug`, Auto-Refresh alle 3 Sekunden. Erreichbar **nur mit Admin-Anmeldung** — das Log stellt
Phase-A- und Phase-B-Ereignisse mit Zeitstempel nebeneinander, offen abrufbar wäre es ein Weg zur
Zuordnung Person → Stimme. Aus demselben Grund steht im Phase-A-Eintrag kein Hinweis mehr darauf,
*wer* ein Token abgeholt hat (EIP-T-018). Vier Ereignisarten:

- `info` — normale Vorgänge
- `reject` — regelkonforme Abweisungen (verbrauchtes Token, zweites Token, ungültige Signatur …)
- `error` — unerwartete Fehler samt Traceback
- `inconsistency` — **die wichtigste Kategorie**: gebrochene Kette, ungültige Signatur im Board,
  schiefe Ledger-Abrechnung, Board gegen Vote-Ledger auseinandergelaufen

Darüber läuft bei jedem Aufruf eine frisch gerechnete Konsistenzprüfung über alle Umfragen. Bei
diesem Projekt ist das kein Komfort-Feature, sondern die Stelle, an der Manipulation auffällt.

**Vollprüfung und laufende Prüfung** — die Board-Seite, das Ergebnis, der Export, `/debug` und das
mitgelieferte Prüfwerkzeug prüfen jedes Mal *alles*: jede Hash-Verkettung und jede Token-Signatur,
ohne Vorbedingung. Während des Abstimmens läuft eine verkürzte Variante: die Hash-Kette weiterhin
ganz, die Signaturen nur für das, was seit der letzten Prüfung dazugekommen ist (EIP-T-051). Sonst
prüft der Server bei der n-ten Stimme n Signaturen und wird genau dann langsam, wenn Beteiligung da
ist. Was die Verkürzung kostet: wer eine alte Stimme fälscht **und** die Hashes dahinter neu rechnet,
fällt nicht mehr beim nächsten Abstimmen auf, sondern erst beim nächsten vollen Durchlauf — also
spätestens, sobald jemand die Board-Seite öffnet oder das Board selbst nachrechnet. Gegen einen
Betreiber mit Schreibzugriff hilft ohnehin nur die externe Verankerung aus §12.

### Angriffsdemos (Admin)

**Ballot-Stuffing** — der Betreiber signiert sich selbst ein Token und stimmt ab. Die Stimme läuft
durch denselben Pfad wie eine echte und ist kryptografisch nicht von ihr zu unterscheiden. Was sie
verrät: die Abrechnung zeigt mehr Stimmen als Berechtigte.

**Board umschreiben** — ein Stimmeintrag wird verändert, die Hashes bleiben stehen. Die Kette
bricht sichtbar, das Ergebnis wird verweigert.

Der zweite Angriff zeigt zugleich die Grenze: ein Betreiber mit Schreibzugriff würde die Hashes
dahinter **neu rechnen**, und danach ist die Kette wieder intakt und lokal nicht mehr von der
Wahrheit zu unterscheiden. Die Kette schützt gegen unbemerkte nachträgliche Änderung durch Dritte —
nicht gegen den Betreiber. Dafür bräuchte es einen extern verankerten Merkle-Root (§12).

---

## 4. Aufbau

```
Browser                                  Server
────────────────────────────────────────────────────────────────────
static/ballot.js (+ blind.js)            web.py          HTTP, Cookies
  Token erzeugen                         auth.py         Pseudonym
  verblinden        ──── blinded ──────> poll_service.py Regeln
  entblinden        <─── blind_sig ────  blind.py        RFC 9474
  Token speichern                        store.py        SQLite
                                         debug.py        Beobachtung
  abstimmen         ── token+sig+wahl ─>
```

| Datei | Rolle |
|---|---|
| `auth.py` | `authenticate() -> pseudonym`. `CodeAuthenticator` aktiv (Zugangscode statt geprüftem Ausweis); `SamlEidAuthenticator` ist die Hülle für den echten eID-Flow. |
| `blind.py` | Blindsignatur, Serverseite (RFC 9474, RSABSSA-SHA384-PSS-Deterministic, 2048 Bit). |
| `static/blind.js` | Dieselbe Krypto im Browser. Beide Seiten müssen bitgenau gleich rechnen. |
| `static/ballot.js` | Der Weg einer Stimme im Browser: Token erzeugen, verblinden, signieren lassen, entblinden, abgeben — plus der Zwischenstand, wenn die Abgabe danach abbricht (EIP-ADR-20260725-002). `blind.js` rechnet, `ballot.js` führt. `templates/poll.html` enthält nur noch die DOM-Verdrahtung. |
| `static/beleg.js` | Der Beleg: Kassenbon, QR-Code, Textdatei. Reine Darstellung — kein Krypto, kein Netz, kein Speicher. |
| `store.py` | SQLite: `polls`, `eligibility`, `spent`, `board`. Alle Zugriffe — auch lesende — laufen über ein `RLock`, weil sich alle Threads eine Verbindung teilen (EIP-T-019). |
| `board_eintrag.py` | Das Eintragsformat: kanonisches JSON, Eintrags-Hash, Konstruktoren (`vote`, `token_issued`, `poll_open`, `poll_closed`) und `parse(entry) -> Vote \| TokenIssued \| PollOpen \| PollClosed \| Unlesbar`. Rohe Dicts baut und liest niemand mehr selbst. Ein Eintrag, den `parse` nicht deuten kann, wird zu `Unlesbar` — er zählt nirgends mit und macht das Ergebnis unbelastbar, statt still zu verschwinden. |
| `verifikation.py` | Die gesamte Prüfung über das gelesene Board: `pruefe(entries, public_key, options) -> Pruefbericht` plus Kettenprüfung. Ohne Datenbank, ohne privaten Schlüssel, auch als Kommandozeilen-Werkzeug für Dritte lauffähig. |
| `poll_service.py` | Phasenlogik, Regeln, Konsistenzprüfung. Die Auszählung selbst delegiert es an `verifikation.py` und übersetzt Befunde in Abweisungen. |
| `demo.py` | Die Angriffsdemos aus §9 — außerhalb des Kerns (EIP-T-050). Sie benutzen `PollService` von außen und schreiben an der Anwendung vorbei direkt in die Datenbank, weil genau das das Angreifermodell ist: Wer die Platte hat, braucht keine API. Verdrahtet nur bei `Settings.demos` (`EIDPOLL_DEMOS`, lokal an, öffentlich aus). |
| `debug.py` | Ringpuffer im Prozessspeicher (500 Ereignisse), bewusst keine zweite Wahrheit. |
| `web.py` | Seiten und JSON-API. Gebaut wird eine Instanz von `create_app(store_path, authenticator, settings)`: Datenbankpfad, Authentifizierung und Betriebsmodus stehen in der Signatur, nicht im Modul. Den echten eID-Flow einzusetzen heißt deshalb, `SamlEidAuthenticator` zu übergeben — ohne Änderung an `web.py`. Für uvicorn bleibt `web:app` der Einstieg (aus der Umgebung, erst beim Zugriff gebaut). |

**Warum das Blinding im Browser liegt und nicht auf dem Server:** Verblindet der Server selbst,
sieht er das Token unverblindet — dann gibt es kein Wahlgeheimnis gegen den Betreiber, sondern nur
dessen Behauptung. Das ist der eine Teil der App, der sich nicht vereinfachen lässt, ohne die
zentrale Zusage zu verlieren.

### Einstellungen

| Variable | Voreinstellung | Zweck |
|---|---|---|
| `EIDPOLL_PORT` | `8731` | Port (nur `start.sh`) |
| `EIDPOLL_DB` | `app/data/eidpoll.sqlite3` | Datenbankdatei |
| `EIDPOLL_ADMIN_TOKEN` | `admin` | Admin-Zugang |

Token-Signaturschlüssel und Server-Secret liegen in der Datenbank und überleben Neustarts. **Wird
die Datei gelöscht, werden alle ausgegebenen Tokens ungültig.**

### Tests

```bash
python3 app/blind.py         # Krypto-Roundtrip
python3 app/smoke_test.py    # sieben Abnahmepunkte serverseitig, plus beide Angriffe
                             # darin: Board-Prüfung ohne SQLite und ohne TestClient
node app/ballot_test.mjs     # Stimmzettel-Flow ohne Browser: Abbruch zwischen Signatur
                             # und Abgabe, Wiederverwendung derselben Berechtigung

cd app && EIDPOLL_DB=/tmp/bt.sqlite3 python3 -m uvicorn web:app --port 8899 &
python3 app/browser_test.py  # derselbe Durchlauf im echten Browser
```

`browser_test.py` ist der wichtigste: nur dort zeigt sich, ob `blind.js` bitgleich zu `blind.py`
rechnet. Weicht es ab, weist der Server die Stimme als „Token-Signatur ungültig" ab.
`ballot_test.mjs` prüft das ausdrücklich nicht — dort ist der Server gestellt und die Signatur
eine Attrappe; geprüft wird allein der Zustandsverlauf um EIP-ADR-20260725-002.

---

## 5. Was diese Version **nicht** leistet

**Keine echte Identitätsprüfung.** Statt eines Ausweises verlangt `CodeAuthenticator` einen
Zugangscode aus einer konfigurierten Liste (Voreinstellung `testperson1`–`testperson100`). Ein
Code steht für einen bereits gültig geprüften Ausweis, prüft aber selbst keine Identität — „ein
Ausweis, eine Stimme" gilt nur innerhalb der ausgegebenen Codeliste, nicht als offene
Registrierung. Für Teilnehmende zeigt die Oberfläche das **absichtlich nicht** (EIP-T-014): der
Dialog „Ausweis auslesen" nennt weder Code noch Test noch Simulation, sichtbar ist der aktive
Modus stattdessen unübersehbar in **Admin** und **Debug**. Der Pseudonym-Präfix
`STUB-NO-REAL-IDENTITY:` bleibt im gespeicherten Datensatz erhalten, auch wenn er in der
Oberfläche nirgends mehr auftaucht. Der echte eID-Flow (TR-03124/TR-03130: TC-Token → AusweisApp
→ eID-Server → SAML-Assertion) braucht AusweisApp, einen eID-Server gegen Test-PKI und
Test-Ausweise; nichts davon liegt derzeit vor. Auszutauschen ist dann genau eine Klasse — Krypto
und Ledger bleiben unberührt.

**Keine auditierte Krypto-Bibliothek.** RFC 9474 ist hier selbst implementiert, weil es für Python
keine geprüfte Umsetzung gibt (PyPI-Suche 2026-07-25: keine Distribution unter
`blind-rsa-signatures`, `blind_signatures`, `blindsig`, `rsa-blind-signatures`, `pyblindsig`).
Geprüft zugekauft sind SHA-384 und die PSS-Verifikation aus `cryptography`; selbst geschrieben sind
EMSA-PSS-ENCODE, MGF1 und die Blinding-Arithmetik — in Python und in JavaScript. Deutlich besser
als der textbook-Chaum des Prototyps, aber kein Ersatz für einen Audit.

**Keine Nötigungsresistenz.** Der Beleg ist eine Quittung. Bewusst so entschieden.

**Kein Schutz gegen den Betreiber auf Netzwerk-Ebene.** IP-Adressen und Zeitpunkte können die
kryptografisch getrennte Verbindung wiederherstellen. Das ist eine andere Schicht, gegen die die
Krypto hier wirkungslos ist (§13, Risiko-Knoten 1) — und eine vom Betreiber selbst betriebene
Anonymisierung schützt nicht gegen ihn.

**Kein geprüfter Client-Code.** Der Browser-Krypto-Code kommt vom Betreiber (§10, Helios-Problem).
Ein reproduzierbarer Build-Hash zum Abgleich ist nicht eingerichtet.

**Nicht gebaut** (§12): verteilte Schwellensignatur, externer Merkle-Anker, Produktiv-Berechtigungs-
zertifikat, eIDAS-Ausland, Multi-Tenant, mehrere Fragen oder Ranking. Die Oberfläche verspricht
nichts davon.
