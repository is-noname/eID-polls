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

**Umfrage-Schlüssel.** Der Eintrag im Eligibility-Ledger ist nicht das Pseudonym, sondern
`HMAC(Umfrage-Schlüssel, Pseudonym)`. Dieser Schlüssel wird beim Anlegen der Umfrage zufällig
erzeugt und **beim Schließen vernichtet**.

Das hat eine Folge, die über das Übliche hinausgeht: Nach dem Schließen kann *niemand* die Einträge
noch einem Ausweis zuordnen — auch der Betreiber nicht, auch nicht mit vollem Datenbankzugriff, auch
nicht Jahre später. Ein Meinungsprofil über mehrere Umfragen hinweg ist damit nicht bloß unerwünscht,
sondern unmöglich, weil je Umfrage ein eigener Schlüssel gilt und keiner davon überlebt.

Die Grenze dazu, ehrlich: Die Zusage gilt für die Datenbankdatei. Wer Sicherungskopien anlegt, muss
sie in dieselbe Regel einbeziehen — sonst lebt der Schlüssel dort weiter. Genau das ist einmal
passiert (eine liegengebliebene Kopie mit einem längst vernichteten Schlüssel), deshalb gibt es
seither eine Regel dazu und einen Befehl, der sie befolgbar macht: `python3 app/backup.py <ziel>`
schreibt eine Kopie ohne jeden Schlüssel. Nicht abgedeckt bleiben Dateisystem-Snapshots und andere
Datenträger. Solange eine Umfrage
**läuft**, existiert ihr Schlüssel notwendigerweise; die Zuordnung ist in diesem Zeitraum für den
Betreiber möglich. Vernichtet wird beim Schließen, nicht vorher (`EIP-T-033`, Baustein D).

**Bulletin Board.** Eine öffentliche Sammlung von Einträgen, veröffentlicht in **Batches**
(EIP-ADR-20260728-001): Innerhalb eines Batches gibt es keine Reihenfolge — die Einträge bilden,
nach ihrem Blatt-Hash sortiert, einen Merkle-Baum. Die Wurzeln der Batches sind untereinander
verkettet, sodass Löschen und nachträgliches Ändern auffallen. Hier stehen die Stimmen, und
**nur hieraus** wird ausgezählt. Das ist wichtiger als es klingt: würde intern anders gezählt als
öffentlich einsehbar ist, wäre die öffentliche Prüfung wertlos. Genau dieser Fehler steckte im
Prototyp (`PROTOTYPE_two-ledger/NOTES.md`, Fund 1).

Veröffentlicht wird, sobald mindestens **k** neue Einträge warten (Voreinstellung 10, ein Wert und
seine Grenzen: `EIP-ADR-20260728-001` E3), spätestens nach dem **Zeitdeckel** (6 Stunden), in jedem
Fall beim Schließen der Umfrage. Der Sinn: Erschiene jeder Eintrag sofort, könnte jeder Beobachter
des Boards den Eintragszeitpunkt sehen — genau die Timing-Korrelation, die das Verfahren
verhindern will. Die Batch-Größe ist die Anonymitätsmenge, und bei niedriger Beteiligung ist sie
ehrlicherweise klein. Bis zur Veröffentlichung trägt der **signierte Beleg** (Ed25519, eigener
Schlüssel) die Zusage: Blatt-Hash und Batch-Nummer, offline prüfbar. Fehlt der Eintrag im
zugesagten Batch, ist der Beleg der Nachweis.

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
4. **Schritt 3 — Beleg.** Als `.txt` sichern. Er enthält das Stimm-Token, den Blatt-Hash des
   Eintrags, die zugesagte Batch-Nummer und die Ed25519-Signatur des Betreibers über diese
   Zusage. Die Stimme erscheint im Board erst mit ihrem Batch — der Beleg bindet sofort.

Während die Umfrage läuft, zeigt die Seite nur die Teilnahmezahl. Die Verteilung erscheint erst
nach dem Schließen (§7) — Zwischenstände beeinflussen laufende Abstimmungen und erlauben
Timing-Rückschlüsse.

> **Warum nur noch ein Schritt:** Früher war das Token-Holen ein eigener Schritt, und das Token
> musste zwischen zwei Klicks im Browserspeicher überleben. Wer den Tab dazwischen schloss,
> verlor es — und bekam in Phase A kein zweites. Heute existiert es nur für die Sekunden zwischen
> Signatur und Stimmabgabe (EIP-ADR-20260725-002). Bricht ausgerechnet dieser Moment ab, liegt es
> für den nächsten Versuch bereit; ein zweites wird weiterhin nicht ausgegeben, denn das ist die
> Doppelabstimmungs-Abwehr.

> **Wenn die Antwort auf dem Weg verlorengeht.** Ein zweiter Abbruchpunkt liegt eine Stufe früher:
> Der Server hat die verblindete Anfrage signiert und den Ausweis als versorgt vermerkt — und dann
> erreicht die Antwort den Browser nicht (Netz weg, Tab zu). Ohne Gegenmaßnahme wäre die
> Berechtigung verbraucht und niemand hätte ein Token; ein legitim Berechtigter wäre dauerhaft
> ausgeschlossen. Deshalb merkt sich der Server für **24 Stunden**, welche Blindsignatur er auf
> welche verblindete Anfrage ausgegeben hat. Kommt *dieselbe* Anfrage noch einmal, wiederholt er
> dieselbe Antwort. Der Browser hält die Anfrage dafür lokal fest, bevor er sie abschickt.
>
> Das ist keine zweite Ausgabe: Eine *abweichende* Anfrage desselben Ausweises wird weiterhin
> abgewiesen, Ledger und Board bekommen keinen zweiten Eintrag, und eine zweite Signatur derselben
> verblindeten Anfrage wäre ohnehin Bit für Bit die erste.
>
> **Warum das die Anonymität nicht bricht.** Der Merkposten verbindet den
> Wahlberechtigungs-Schlüssel mit der *verblindeten* Anfrage und ihrer *verblindeten* Signatur —
> genau die beiden Werte, die der Server im regulären Ablauf ohnehin sieht und selbst berechnet.
> Das entblindete Stimm-Token kommt darin nicht vor; es entsteht im Browser und wird dort
> entblindet. Wer den Merkposten liest, kann daraus so wenig auf eine Stimme schließen wie aus dem
> Mitschnitt der ursprünglichen Anfrage. Was er zusätzlich trägt, ist eine Zeitangabe — auf die
> Stunde gerundet, aus demselben Grund wie beim Puffer-Zeitpunkt (EIP-T-033, Baustein E) — und die
> verschwindet mit dem Eintrag: nach Ablauf, spätestens beim Schließen der Umfrage. Aus
> Sicherungskopien fällt er heraus, sonst überlebte er seinen eigenen Ablauf (EIP-T-070,
> EIP-T-067).

### Eigene Stimme prüfen

**Verifikation** → Umfrage wählen, Token aus dem Beleg einfügen. Die App zeigt die Auswahl, die
unter diesem Token im Board steht. Gefunden wird nur Veröffentlichtes: Zwischen Abgabe und dem
nächsten Batch meldet die Suche „kein Eintrag" — in diesem Zeitraum ist der signierte Beleg der
Nachweis, nicht das Board.

Dieser Beleg ist zugleich eine **Quittung** — wer ihn vorzeigt, beweist, wie er gestimmt hat. Das
ist eine bewusste Entscheidung: individuelle Verifizierbarkeit und Quittungsfreiheit schließen
einander aus (`EIP-ADR-20260725-001`). Konsequenz: Stimmenkauf und Nötigung sind technisch nicht
verhindert.

### Ergebnis und öffentliche Prüfung

**Board** (`/board/{id}`) zeigt fünf Kennzahlen und darunter die veröffentlichten Batches:

| Kennzahl | Bedeutung | Wenn sie ausschlägt |
|---|---|---|
| Batch-Kette | Einträge passen zu den Merkle-Wurzeln, Wurzeln zur Kette | Ein Eintrag wurde nachträglich verändert oder gelöscht → **kein Ergebnis** |
| Token-Signaturen | jede Stimme trägt eine gültige Signatur | Eine Stimme wurde eingefügt, ohne signiert zu sein → **kein Ergebnis** |
| Berechtigte | wie viele Token ausgegeben wurden | — |
| Stimmen im Board | wie viele Stimmen veröffentlicht sind | — |
| Ledger-Abrechnung | Stimmen ≤ Berechtigte? | Mehr Stimmen als Berechtigte = sichtbarer Manipulationsbeweis |

Beide Zahlen der Abrechnung stammen aus dem Board — also aus dem, was jeder Dritte sieht.

Unten stehen der **öffentliche Token-Schlüssel** und der **Beleg-Schlüssel**. Damit lässt sich
jede Stimme unabhängig prüfen (RSASSA-PSS über SHA-384, Salt-Länge 0) und jeder Beleg verifizieren.
Das Board rechnet sich nach über `leaf = sha256(0x00‖payload)`, je Batch einen Merkle-Baum über
die sortierten Blätter (`sha256(0x01‖links‖rechts)`, ungerade Knoten durchgereicht) und
`batch_root = sha256(0x02‖merkle_root‖vorherige_root)`.

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

Den Token-Schlüssel bringt das Board selbst mit: Er steht im Eröffnungseintrag (`POLL_OPEN`) und
liegt damit unter der Merkle-Wurzel und in der Batch-Kette. Nachträglich austauschen ließe er sich
nur, indem die Kette bricht — anders als ein Schlüssel, der bloß neben dem Board in der Datenbank
läge. Wer ihn aus einer unabhängigen Quelle hat, übergibt ihn mit `--pubkey key.pem`: Er **ersetzt**
den Schlüssel aus dem Board dann nicht, sondern wird dagegen gehalten, und eine Abweichung ist ein
Befund. Weil jede Umfrage ihren eigenen Schlüssel hat, ist auch der Schlüssel einer *anderen*
Umfrage eine Abweichung.

**Was das nicht leistet:** Der Export kommt weiterhin von diesem Server. Zwei Betrachter können
zwei verschiedene, jeweils in sich stimmige Boards bekommen, und ein Betreiber mit Schreibzugriff
rechnet die Kette nach einer Änderung neu durch. Dagegen hilft nur ein extern verankerter
Merkle-Root und Gegenzeichner (§12).

### Ohne unseren Code nachrechnen: `auditor.py`

`verifikation.py` ist ein Modul dieser App. Wer ihr misstraut, prüft mit ihr nichts nach — er
führt dieselbe Behauptung ein zweites Mal aus. `auditor.py` ist deshalb bewusst eine **zweite,
unabhängige Implementierung**: eine einzelne Datei, die nichts aus dem Projekt importiert und das
Board allein aus seiner öffentlichen Beschreibung nachrechnet (EIP-T-071). Sie ist klein genug,
um selbst gelesen zu werden — das ist ihr eigentlicher Zweck.

```bash
python3 app/auditor.py https://<instanz>/api/board/<poll-id>
python3 app/auditor.py board.json --pubkey key.pem --token <mein-token-hex>
python3 app/auditor.py board.json --beleg beleg.json --belegkey beleg.pem
```

Geprüft wird: Blatt-Hashes, Merkle-Wurzeln und Batch-Kette (aus den Einträgen neu gerechnet, die
im Export genannten Wurzeln gelten als Behauptung), die RSASSA-PSS-Signatur jeder Stimme gegen den
Schlüssel aus dem `POLL_OPEN`-Eintrag, **Token-Eindeutigkeit**, die Ledger-Abrechnung (§9) und die
eigene Auszählung gegen das, was die Instanz unter `/api/status/{poll_id}` veröffentlicht. Wird das
Board über eine URL geladen, holt der Auditor diesen Status von selbst; sonst nimmt er ihn über
`--status`. Exit-Code 0 heißt: kein Befund, 1 heißt: mindestens einer, und die Zahlen darüber sind
nicht belastbar.

Die Token-Eindeutigkeit prüft nur der Auditor, nicht `verifikation.py`: Im Betrieb verhindert der
Vote-Ledger die zweite Abgabe desselben Tokens — von außen ist der Ledger aber nicht einsehbar,
und im Board ist die Wiederholung die einzige sichtbare Spur.

Mit `--beleg` prüft er zusätzlich einen Abgabebeleg: die Ed25519-Signatur und den
**Inklusionspfad** des Blattes zur Merkle-Wurzel seines Batches — also den logarithmischen
Nachweis, dass genau diese Stimme im veröffentlichten Board steht. Fehlt das Blatt im zugesagten
Batch, ist der Beleg der Nachweis dafür. Der zugehörige Schlüssel gehört aus einer unabhängigen
Quelle (`--belegkey`): Anders als der Token-Schlüssel steht der Beleg-Schlüssel **nicht** unter der
Merkle-Wurzel, ein Beleg gegen den vom Server mitgelieferten Schlüssel prüft also wenig. Der
Auditor sagt das in seiner Ausgabe.

Was auch der Auditor nicht leisten kann: Er zeigt, dass die veröffentlichten Einträge zueinander
passen — nicht, dass *alle* abgegebenen Stimmen darin stehen (dafür braucht es die Belege der
Abstimmenden) und nicht, dass die ausgegebenen Token an Berechtigte gingen (das ist Phase A und im
Board grundsätzlich nicht sichtbar).

### Debug-Modul

`/debug`, Auto-Refresh alle 3 Sekunden. Erreichbar **nur mit Admin-Anmeldung**. Im Phase-A-Eintrag
steht kein Hinweis darauf, *wer* ein Token abgeholt hat (EIP-T-018). Vier Ereignisarten:

- `info` — normale Vorgänge
- `reject` — regelkonforme Abweisungen (verbrauchtes Token, zweites Token, ungültige Signatur …)
- `error` — unerwartete Fehler samt Traceback
- `inconsistency` — **die wichtigste Kategorie**: gebrochene Batch-Kette, ungültige Signatur im
  Board, schiefe Ledger-Abrechnung (auch inklusive Puffer), Board gegen Vote-Ledger
  auseinandergelaufen, hängender Batch-Puffer (Zeitdeckel überschritten oder Puffer trotz
  geschlossener Umfrage nicht leer)

Darüber läuft bei jedem Aufruf eine frisch gerechnete Konsistenzprüfung über alle Umfragen. Bei
diesem Projekt ist das kein Komfort-Feature, sondern die Stelle, an der Manipulation auffällt.

**Teilnahmevorgänge stehen nicht im Ereignisstrom.** Bis EIP-T-041 lagen „Token ausgegeben" und
„Stimme gepuffert" sekundengenau und in Eingangsreihenfolge untereinander — bei dünnem Verkehr
genügt das Nebeneinander zweier Uhrzeiten für die Zuordnung Berechtigung → Stimme, ganz ohne
Pseudonym im Log. Was an einer einzelnen Teilnahmehandlung hängt (`auth`, `phase-a`, `phase-b` auf
`info` und `reject`, inklusive der Abweisungen aus beiden Phasen), wird deshalb **je Stunde
gezählt** und in einer eigenen Tabelle angezeigt: keine Sekunde, keine Reihenfolge. `error` und
`inconsistency` bleiben im Strom — ein Fehler ist ein nicht zustande gekommener Vorgang, und eine
gemeldete Verkettung muss genau auffindbar sein. Die Grenze steht auf der Seite selbst: Wer in
seiner Stunde allein teilnimmt, bleibt über die Stunde zuzuordnen.

**Vollprüfung und laufende Prüfung** — die Board-Seite, das Ergebnis, der Export, `/debug` und das
mitgelieferte Prüfwerkzeug prüfen jedes Mal *alles*: jede Merkle-Wurzel, die Batch-Kette und jede
Token-Signatur, ohne Vorbedingung. Während des Abstimmens läuft eine verkürzte Variante: Wurzeln
und Kette weiterhin ganz, die Signaturen nur für das, was seit der letzten Prüfung dazugekommen
ist (EIP-T-051). Sonst
prüft der Server bei der n-ten Stimme n Signaturen und wird genau dann langsam, wenn Beteiligung da
ist. Was die Verkürzung kostet: wer eine alte Stimme fälscht **und** die Hashes dahinter neu rechnet,
fällt nicht mehr beim nächsten Abstimmen auf, sondern erst beim nächsten vollen Durchlauf — also
spätestens, sobald jemand die Board-Seite öffnet oder das Board selbst nachrechnet. Gegen einen
Betreiber mit Schreibzugriff hilft ohnehin nur die externe Verankerung aus §12.

### Angriffsdemos (Admin)

**Ballot-Stuffing** — der Betreiber signiert sich selbst ein Token und stimmt ab. Die Stimme läuft
durch denselben Pfad wie eine echte und ist kryptografisch nicht von ihr zu unterscheiden. Was sie
verrät: die Abrechnung zeigt mehr Stimmen als Berechtigte. Nach dem Schließen der Umfrage
scheitert die Demo — der Signaturschlüssel ist dann vernichtet und auch der Betreiber kann kein
gültiges Token mehr herstellen (siehe unten). Während die Umfrage läuft, kann er es.

**Board umschreiben** — ein veröffentlichter Stimmeintrag wird verändert (adressiert über seinen
Blatt-Hash), die Wurzeln bleiben stehen. Die Batch-Kette bricht sichtbar, das Ergebnis wird
verweigert.

Der zweite Angriff zeigt zugleich die Grenze: ein Betreiber mit Schreibzugriff würde Wurzeln und
Kette dahinter **neu rechnen**, und danach ist das Board wieder in sich stimmig und lokal nicht
mehr von der Wahrheit zu unterscheiden. Die Kette schützt gegen unbemerkte nachträgliche Änderung
durch Dritte — nicht gegen den Betreiber. Dafür bräuchte es einen extern verankerten Merkle-Root
(§12, EIP-T-006 — die Batch-Kette liefert dafür bereits die zu verankernde `batch_root`).

### Selbstbindung nachlesen

Vier Seiten, alle ohne Anmeldung erreichbar:

| Seite | Inhalt |
|---|---|
| `/manifest` | Wofür das Projekt da ist und was es behauptet |
| `/kodex` | Was es sich selbst verbietet — inklusive **Schuldenübersicht**: welche Zusagen heute nur durch Verhalten gedeckt sind und nicht durch Technik |
| `/kodex/protokoll` | Änderungen am Kodex und das **Verstoßprotokoll**: was schiefgegangen ist, seit wann bis wann, was daraus folgte |
| `/transparenz` | Behördenanfragen, beginnend beim Nullfall |

Dass diese Seiten existieren, ist keine Zugabe: § 10 des Kodex verlangt, dass Selbstbindung und
Verstöße von außen erreichbar sind (EIP-T-063). Ein Verstoßprotokoll, das nur der Betreiber lesen
kann, dokumentiert nichts, es beruhigt nur.

Der Inhalt kommt aus Markdown-Dateien im App-Ordner, die außerhalb erzeugt werden
(`scripts/sync_public_docs.py`). Eine handgepflegte Zweitfassung im Template wäre nach § 20 selbst
ein Verstoß — und ist mit dem Manifest schon einmal auseinandergelaufen (EIP-T-044).

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
| `store.py` | SQLite: `polls`, `eligibility`, `spent`, `board`, `batches` und der kurzlebige `issue_retry` (EIP-T-070) — ohne Eingangsreihenfolge (`WITHOUT ROWID`, EIP-T-033 E). Puffert Einträge und veröffentlicht sie als Batch. Alle Zugriffe — auch lesende — laufen über ein `RLock`, weil sich alle Threads eine Verbindung teilen (EIP-T-019). |
| `board_eintrag.py` | Das Eintragsformat: kanonisches JSON, Blatt-Hash, Merkle-Baum, Batch-Kette, Konstruktoren (`vote`, `token_issued`, `poll_open` — trägt den öffentlichen Token-Schlüssel der Umfrage —, `poll_closed`) und `parse(entry) -> Vote \| TokenIssued \| PollOpen \| PollClosed \| Unlesbar`. Rohe Dicts baut und liest niemand mehr selbst. Ein Eintrag, den `parse` nicht deuten kann, wird zu `Unlesbar` — er zählt nirgends mit und macht das Ergebnis unbelastbar, statt still zu verschwinden. |
| `verifikation.py` | Die gesamte Prüfung über das veröffentlichte Board: `pruefe(batches, options) -> Pruefbericht` — Merkle-Wurzeln, Batch-Kette, Signaturen, Abrechnung, Auszählung. Den öffentlichen Schlüssel holt sie sich aus dem Board selbst (`schluessel_aus_board`); ein unabhängig mitgegebener wird dagegen gehalten. Ohne Datenbank, ohne privaten Schlüssel, auch als Kommandozeilen-Werkzeug für Dritte lauffähig. |
| `auditor.py` | Die unabhängige Gegenprobe (EIP-T-071): eine Datei, kein Import aus dem Projekt, rechnet Struktur, Signaturen, Token-Eindeutigkeit, Abrechnung und Auszählung allein aus dem Board-Export nach und hält sie gegen `/api/status`. Prüft mit `--beleg` auch Beleg-Signatur und Inklusionspfad. Gehört bewusst **nicht** zum Kern — sie darf nichts von ihm wissen. |
| `poll_service.py` | Phasenlogik, Regeln, Konsistenzprüfung. Die Auszählung selbst delegiert es an `verifikation.py` und übersetzt Befunde in Abweisungen. Hält den Lebenszyklus beider Umfrage-Schlüssel: erzeugen beim Anlegen, `vernichte_poll_secret()` und `vernichte_poll_key()` beim Schließen. Den privaten Signaturschlüssel liest es bewusst **ohne Zwischenspeicher** aus der Datenbank — ein Cache im Prozess hielte ihn über seine Vernichtung hinaus am Leben. |
| `demo.py` | Die Angriffsdemos aus §9 — außerhalb des Kerns (EIP-T-050). Sie benutzen `PollService` von außen und schreiben an der Anwendung vorbei direkt in die Datenbank, weil genau das das Angreifermodell ist: Wer die Platte hat, braucht keine API. Verdrahtet nur bei `Settings.demos` (`EIDPOLL_DEMOS`, lokal an, öffentlich aus). |
| `debug.py` | Ringpuffer im Prozessspeicher (500 Ereignisse), bewusst keine zweite Wahrheit. |
| `web.py` | Seiten und JSON-API. Gebaut wird eine Instanz von `create_app(store_path, authenticator, settings)`: Datenbankpfad, Authentifizierung und Betriebsmodus stehen in der Signatur, nicht im Modul. Den echten eID-Flow einzusetzen heißt deshalb, `SamlEidAuthenticator` zu übergeben — ohne Änderung an `web.py`. Für uvicorn bleibt `web:app` der Einstieg (aus der Umgebung, erst beim Zugriff gebaut). |

**Warum das Blinding im Browser liegt und nicht auf dem Server:** Verblindet der Server selbst,
sieht er das Token unverblindet — dann gibt es kein Wahlgeheimnis gegen den Betreiber, sondern nur
dessen Behauptung. Das ist der eine Teil der App, der sich nicht vereinfachen lässt, ohne die
zentrale Zusage zu verlieren.

**Ein Signaturschlüssel je Umfrage (EIP-T-069):** Die Blindsignatur, die eine Stimmberechtigung
ausweist, entsteht unter einem Schlüssel, der genau zu dieser Umfrage gehört. Das hat zwei
Wirkungen. Ein Token aus Umfrage A ist in Umfrage B **strukturell** wertlos — nicht weil eine Regel
es verbietet, sondern weil die Signatur dort nicht gilt; Hamstern und Wiedereinreichen über
Umfragen hinweg fallen damit weg. Und beim Schließen wird der private Teil vernichtet
(überschreiben, löschen, `VACUUM` — derselbe Weg wie beim Umfrage-Schlüssel): Ab dann kann niemand
mehr gültige Stimm-Token für diese Umfrage herstellen, auch kein kompromittierter oder böswilliger
Betreiber mit der Datenbank in der Hand. Die Auszählung ist eingefroren.

Ehrlich dazu, in beide Richtungen: Die Vernichtung wirkt **ab dem Schließen, nicht davor**. Solange
eine Umfrage läuft, hält der Betreiber ihren Signaturschlüssel allein und könnte sich Token
ausstellen — dagegen hilft nur, dass mehrere Stellen unabhängig signieren (§12, nicht gebaut); was
bleibt, ist die Ledger-Abrechnung, die den Überschuss sichtbar macht. Und die Löschzusage gilt für
die Datenbankdatei; für Sicherungskopien gilt die Regel oben (`app/backup.py`), für Snapshots und
die Blockverwaltung einer SSD gilt sie weiterhin nicht.

**Sitzungstrennung der Abstimm-Route (EIP-T-033, Baustein F):** Phase B braucht keine Identität —
das Token ist die ganze Berechtigung. Damit der Server Identität und Stimme nie im selben Request
empfängt, sendet `ballot.js` die Stimme ohne Cookies und ohne Referrer (`credentials: "omit"`,
`referrerPolicy: "no-referrer"`). Kommt trotzdem Sitzungskontext an (etwa von einem alten, noch
gecachten Client), zählt die Stimme — die Verkettung ist mit dem Empfang bereits passiert, eine
Abweisung schützte nichts mehr —, aber der Vorfall steht als Befund im Debug-Modul
(`unverkettbarkeit`). Zusätzlich antworten beide Phasen-Routen (`/api/token`, `/api/vote`)
frühestens nach `EIDPOLL_ANTWORT_FLOOR_S` Sekunden, damit die Bearbeitungsdauer nicht verrät, was
der Server gerade tat (schnelle Abweisung vs. langsame Signatur). Ehrlich dazu: Das ist ein Floor,
keine Konstante — dauert die Bearbeitung länger als der Floor, ist die Dauer wieder sichtbar. Und
gegen Korrelation über IP-Adresse und Uhrzeit auf Netzwerkebene hilft beides nicht (Abschnitt 5;
der anonyme Zustellkanal ist EIP-T-034).

### Einstellungen

| Variable | Voreinstellung | Zweck |
|---|---|---|
| `EIDPOLL_PORT` | `8731` | Port (nur `start.sh`) |
| `EIDPOLL_DB` | `app/data/eidpoll.sqlite3` | Datenbankdatei |
| `EIDPOLL_ADMIN_TOKEN` | `admin` | Admin-Zugang |
| `EIDPOLL_ANTWORT_FLOOR_S` | `0.3` | Mindest-Antwortzeit der Phasen-Routen in Sekunden, `0` schaltet ab (EIP-T-033 F) |
| `EIDPOLL_RETRY_CACHE_H` | `24` | Lebensdauer des Wiederhol-Puffers der Token-Ausgabe in Stunden, `0` schaltet ab (EIP-T-070) |

**Schlüssel und ihre Lebensdauer.** Es gibt keinen globalen Token-Signaturschlüssel mehr
(EIP-T-069). Jede Umfrage bekommt beim Anlegen zwei eigene, beide in der Datenbank, beide beim
Schließen vernichtet:

| Schlüssel | Wozu | Wann weg |
|---|---|---|
| `poll_key:{id}` | signiert die Stimm-Token dieser Umfrage (RSA 2048, RFC 9474) | beim Schließen |
| `poll_secret:{id}` | leitet den Wahlberechtigungs-Schlüssel aus dem Pseudonym ab | beim Schließen |

Der *öffentliche* Teil des Token-Schlüssels steht im Board (`POLL_OPEN`) und überlebt dort — sonst
wäre die Auszählung nach dem Schließen nicht mehr nachprüfbar. Dauerhaft bleiben nur der
Beleg-Schlüssel (Ed25519) und der Cookie-Schlüssel; beide signieren nichts, was gezählt wird.

**Wird die Datenbankdatei gelöscht, werden alle ausgegebenen Tokens ungültig.**

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
