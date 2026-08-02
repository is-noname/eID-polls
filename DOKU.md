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
seither eine Regel dazu und einen Befehl, der sie befolgbar macht: `python3 app/backup.py
<zielverzeichnis>` schreibt Kopien beider Datenbankdateien ohne jeden Schlüssel. Nicht abgedeckt bleiben Dateisystem-Snapshots und andere
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

Veröffentlicht wird, sobald mindestens **k Stimmen** im Puffer warten (Voreinstellung 10, ein Wert
und seine Grenzen: `EIP-ADR-20260728-001` E3), spätestens nach dem **Zeitdeckel** (6 Stunden), in
jedem Fall beim Schließen der Umfrage. Der Sinn: Erschiene jeder Eintrag sofort, könnte jeder
Beobachter des Boards den Eintragszeitpunkt sehen — genau die Timing-Korrelation, die das Verfahren
verhindern will.

**Gezählt werden Stimmen, nicht Einträge** (`EIP-T-076`). Bis dahin zählte k alle Einträge, und weil
jede Teilnahme zwei erzeugt (Ausgabe + Stimme), war die zugesagte Menge in Wahrheit rund die Hälfte;
unter Andrang lag fast jede vierte Stimme in einem Batch mit weniger als 5 anderen
(`EIP-RPT-20260731-001`, gemessen). An Stimmen gebunden fällt dieser Anteil auf 0, bei gleicher
Batchgröße und gleicher Wartezeit.

Die Zahl der Stimmen in einem Batch ist die Anonymitätsmenge, und bei niedriger Beteiligung ist sie
ehrlicherweise klein: Löst der Zeitdeckel aus oder endet die Umfrage, kann ein Batch k
unterschreiten — die Board-Seite nennt für jeden Batch die **tatsächliche** Zahl (Messwert, keine
Zusage), und der Betreiber bekommt jeden solchen Batch als Befund ins Debug-Modul. Bis zur
Veröffentlichung trägt der **signierte Beleg** (Ed25519, eigener Schlüssel) die Zusage: Blatt-Hash
und Batch-Nummer, offline prüfbar. Fehlt der Eintrag im zugesagten Batch, ist der Beleg der
Nachweis.

---

## 3. Bedienung

### Starten und beenden

Desktop-Icon **eID-Umfrage** oder `bash app/start.sh`. Danach `http://127.0.0.1:8731/`.
Beenden über den Knopf **oben rechts** in der App — er stoppt den Server, nicht nur den Tab.

### Als Admin: Umfrage anlegen

**Admin** → Token eingeben (Voreinstellung `admin`) → Formular:

- **Umfrage-ID** — kurz, nur Buchstaben/Ziffern/`-`/`_`; steht später in jeder Board-Zeile
- **Frage** — eine Frage pro Umfrage
- **Optionen** — eine pro Zeile, mindestens zwei, fest vorgegeben; kein Freitext (§8). Eine Zeile
  muss genau `Enthaltung`, `Weiß nicht` oder `Weiss nicht` lauten (Groß-/Kleinschreibung egal)

Freitext ist ausgeschlossen, weil er die maschinelle Auszählung bricht und deanonymisieren kann.

Die Enthaltungspflicht kommt aus § 12 des Kodex: Eine Antwortliste ohne Enthaltung zwingt zu einer
Meinung, und die Verschiebung, die daraus entsteht, kann am Board niemand nachrechnen. Geprüft wird
auf **genau** diese Texte, nicht darauf, ob das Wort irgendwo vorkommt — sonst hätte jede
Umbenennung („Weiß nicht so recht") die Regel ausgehebelt. Der feste Text ist zugleich die einzige
Form, die ein Dritter am veröffentlichten `POLL_OPEN`-Eintrag selbst nachprüfen kann; eine
Kennzeichnung im Datenmodell stünde dort nicht. Was § 12 sonst noch zusagt — neutrale Formulierung,
Veröffentlichung abgelehnter Fragevorschläge — ist nicht erzwungen und auch nicht erzwingbar.

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
nach dem Schließen — der Gedanke dahinter: Zwischenstände beeinflussen laufende Abstimmungen.

**Das ist eine Anzeigeentscheidung, kein Schutz.** Das Board unter „Nachweise" gibt jeden
veröffentlichten Eintrag samt gewählter Option heraus, auf der Seite wie über `/api/board/{id}`.
Wer die Datei lädt, zählt den Zwischenstand selbst aus, und die Startseite sagt das auch so. Die
Batch-Veröffentlichung verzögert ihn um bis zu sechs Stunden (k = 10, Zeitdeckel), verbirgt ihn
aber nicht — sie ist gegen Verkettung gebaut, nicht gegen Mitzählen, und darf nicht als das
zweite ausgegeben werden. Ob der Zwischenstand überhaupt verborgen sein *soll*, ist offen und
wird in EIP-T-056 entschieden.

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

**Die Suche selbst läuft im Browser**, nicht auf dem Server: Er liefert das Board als Datei aus, das
Token steht im `#`-Teil der Adresse, den der Browser nie mitsendet, und der Abruf fährt ohne Cookie.
Eine Abfrage „gib mir den Eintrag zu Token X" gibt es nicht und soll es nicht geben — sonst wüsste
der Betreiber, welcher Eintrag wem gehört, und die Blindsignatur wäre an der Stelle wertlos, an der
sie wirkt (`EIP-ADR-20260802-002`). Was der Abruf trotzdem zeigt: die Absender-IP und **welche
Umfrage** jemanden interessiert.

**Das hat eine Grenze**, und sie ist ausgerechnet (`scripts/mess_boardgroesse.py`): Eine Teilnahme
kostet 1.046 Bytes im Export, der Download wird also bei rund **100.000 Teilnehmenden** unzumutbar —
100 MiB je Prüfung, und der Speicherbedarf im Browser läuft dem noch voraus. Bis dahin trägt der
Weg; darüber greift die Reihenfolge im ADR (gzip, kompaktere Kodierung, Präfix-Bereiche, PIR). Die
öffentliche Instanz liegt Größenordnungen darunter.

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

Jeder Batch nennt außerdem, wie viele **Stimmen** er enthält, und die Seite hebt die kleinste dieser
Zahlen hervor: Sie ist die Anonymitätsmenge, die für die dort liegenden Stimmen tatsächlich gilt.
Liegt sie unter k, sagt die Seite das (`EIP-T-076`). Auch das ist nachrechenbar — das Prüfwerkzeug
gibt dieselben Zahlen aus dem Export aus.

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
zwei verschiedene, jeweils in sich stimmige Boards bekommen. Gegen die zweite Hälfte dieses Problems
— ein Betreiber mit Schreibzugriff, der die Kette nach einer Änderung neu durchrechnet — helfen seit
2026-08-01 die externen Zeitstempel (nächster Abschnitt). Gegen die erste hilft weiter nichts, was
auf dieser Seite steht.

### Externe Zeitstempel auf die Batch-Wurzel

Die Batch-Kette entlarvt nur einen Angreifer, der die Prüfsummen stehen lässt. Wer die Datenbank
schreiben kann — also der Betreiber — rechnet Wurzeln und Kette neu, und danach ist alles in sich
stimmig. Genau das führt die Angriffsdemo „Board umschreiben" vor.

Deshalb wird jede `batch_root(n)` bei **zwei voneinander unabhängigen Diensten** datiert
([[EIP-ADR-20260801-002_Externer-Anker-zwei-Zeitstempel-auf-die-Batch-Root]]):

| Dienst | Wie schnell | Wogegen |
|---|---|---|
| RFC 3161 (freetsa.org) | Sekunden | Prüfbar mit `openssl`, aber eine zentrale Stelle |
| OpenTimestamps → Bitcoin | Stunden | Prüfbar gegen die Blockheader, ohne jemandem zu glauben |

Auf der Board-Seite steht je Batch der Stand und ein Download der Wurzel und der Belege. Selbst
prüfen, für Batch N:

```bash
curl -sO http://127.0.0.1:8731/anker/{poll_id}/N/root          # die 32 Rohbytes der Wurzel
curl -sO https://freetsa.org/files/cacert.pem
curl -sO https://freetsa.org/files/tsa.crt
openssl ts -verify -data {poll_id}-batch-N.root -in {poll_id}-batch-N.tsr \
  -CAfile cacert.pem -untrusted tsa.crt

pip install opentimestamps-client
ots verify {poll_id}-batch-N.root.ots
```

Läuft die aus den Einträgen nachgerechnete Wurzel von der bezeugten weg, steht ein Banner auf der
Board-Seite und ein `inconsistency` im Debug-Modul. Verglichen wird dabei der Hash **aus dem
Beleg**, nicht der Wert aus der Datenbank: Wer die Datenbank umschreibt, ändert den Wert mit, den
signierten Beleg nicht.

**Was der Zeitstempel nicht leistet.** Er verhindert nicht, dass ein Betreiber von Anfang an zwei
verschiedene Boards führt und sie verschiedenen Betrachtern zeigt (*Split-View*). Beide Wurzeln
ließen sich ehrlich datieren. Dagegen hilft kein Zeitstempel, sondern nur, dass unabhängige Dritte
alle je veröffentlichten Wurzeln gegenzeichnen und untereinander vergleichen — das gibt es hier
noch nicht (EIP-T-036).

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
  geschlossener Umfrage nicht leer), veröffentlichter Batch **unter der Mindestmenge k**
  (`EIP-T-076` — zulässig, aber eine Abweichung von der Zusage aus KODEX § 2, und die muss während
  der Laufzeit sichtbar sein, nicht erst hinterher)

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
| `/version` | Welcher Stand hier läuft: Commit, Dateihash, und wie man ihn nachrechnet |

Dass diese Seiten existieren, ist keine Zugabe: § 10 des Kodex verlangt, dass Selbstbindung und
Verstöße von außen erreichbar sind (EIP-T-063). Ein Verstoßprotokoll, das nur der Betreiber lesen
kann, dokumentiert nichts, es beruhigt nur.

### Welcher Stand läuft hier: `/version`

Ohne Anmeldung, absichtlich — prüfen will die Instanz gerade, wer uns nicht vertraut. Die Antwort
nennt zwei Dinge mit sehr verschiedenem Gewicht: `commit` ist eine **Angabe** über die Herkunft,
`treehash` eine **Messung** über die Dateien, die tatsächlich ausgeliefert werden. Ein unverändertes
Commit-Feld neben abweichenden Dateien ist der Fall, den ein reiner Commit-Vergleich verdeckt.
Nachrechnen im Klon des Repositorys:

```bash
LC_ALL=C sh -c 'git ls-files -z | sort -z | xargs -0 sha256sum | sha256sum'
```

Abweichungen erscheinen im Debug-Modul unter *Auslieferung gegen Veröffentlichung* — als
`inconsistency`, nicht als Nebenbemerkung: Eine Instanz, die anderen Code ausliefert als den
veröffentlichten, ist eine Dateninkonsistenz wie eine gebrochene Board-Kette, nur eine, die das Board
selbst nicht sehen kann. Genau so entstand Verstoß V-001 (EIP-T-074).

**Was das nicht leistet.** Es ist die Selbstauskunft des Servers, den man gerade prüft. Gegen ein
Versehen hilft sie, gegen einen Betreiber, der lügt, nicht: Wer den Code ändert, kann diese Antwort
mit ändern. Wer nicht *uns* prüfen will, sondern den Code in seinem Browser, nimmt den Abschnitt
darunter.

### Läuft in meinem Browser der veröffentlichte Code?

Das ist die Frage, um die es § 20 eigentlich geht: Das Verblinden passiert im Browser, und damit ist
der ausgelieferte Client die Stelle, an der das Wahlgeheimnis unbemerkt abgeschaltet werden könnte.

Die App liefert allen Client-Code als **unveränderte Dateien** unter `/static/` aus — nichts wird
gebündelt, minifiziert oder in die Seite hineingeschrieben. Ein Build-Schritt, der reproduzierbar
sein müsste, existiert deshalb gar nicht: Was im Repository steht, geht Byte für Byte über die
Leitung. Prüfen lässt sich das **ohne diesen Server zu fragen**:

```bash
# Was liefert die Instanz aus:
curl -s https://eid-poll.onrender.com/static/blind.js | sha256sum
# Was ist veröffentlicht — im Klon, Ordner app/:
sha256sum static/blind.js
# Alle Client-Dateien auf einmal:
LC_ALL=C sh -c 'find static -type f | sort | xargs sha256sum | sha256sum'
```

Beide Größen stammen aus verschiedenen Quellen, keine aus einer Behauptung der App. `/version`
nennt unter `client` denselben Gesamthash und jede Datei einzeln, die Nachweis-Seite jeder Umfrage
zeigt Liste und Prüfbefehl — bequem, aber nicht nötig: Wer selbst abruft und selbst hasht, braucht
die Auskunft nicht.

Damit die Liste nicht *weniger* deckt, als sie aussieht, gibt es keinen ausführbaren Inline-Code
mehr in den Seiten (EIP-T-007; die Verdrahtung liegt in `static/poll.js`, `admin.js`, `debug.js`,
`theme.js`, umfragespezifische Werte kommen als JSON-Datenblock). Fällt jemand dahinter zurück,
meldet `stand.client_luecken()` das als Inkonsistenz im Debug-Modul.

**Was das nicht leistet.** Der Vergleich entlarvt eine Auslieferung, die für alle vom
veröffentlichten Stand abweicht. Er entlarvt **nicht** einen Server, der ausgerechnet einem
einzelnen Besucher anderen Code schickt — dagegen hilft nur, dass mehrere unabhängig abrufen und
vergleichen. Und er hilft niemandem, der nicht nachrechnet. Vollständig gelöst wäre das Problem erst
mit signierter App oder Browser-Erweiterung statt Web-Code (RFC § 12).

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
| `blind.py` | Blindsignatur, Serverseite (RFC 9474, `RSABSSA-SHA384-PSSZERO-Deterministic`, 3072 Bit). `testvektor()` rechnet Anhang A.4 des RFC nach. |
| `rfc9474_a4.json` | Der Testvektor aus RFC 9474 Anhang A.4, wörtlich übernommen. Python und JavaScript prüfen gegen dieselbe Datei — zwei getrennte Kopien könnten getrennt falsch werden. |
| `static/blind.js` | Dieselbe Krypto im Browser. Beide Seiten müssen bitgenau gleich rechnen. `finalizeGeprueft()` verifiziert die entblindete Signatur vor der Weitergabe (RFC 9474 §4.4) — mit WebCrypto, nicht mit der eigenen PSS-Implementierung. |
| `static/ballot.js` | Der Weg einer Stimme im Browser: Token erzeugen, verblinden, signieren lassen, entblinden, abgeben — plus der Zwischenstand, wenn die Abgabe danach abbricht (EIP-ADR-20260725-002). `blind.js` rechnet, `ballot.js` führt. `templates/poll.html` enthält nur noch die DOM-Verdrahtung. |
| `static/beleg.js` | Der Beleg: Kassenbon, QR-Code, Textdatei. Reine Darstellung — kein Krypto, kein Netz, kein Speicher. |
| `store.py` | SQLite der **Board-Seite**: `polls`, `spent`, `board`, `batches`, `anker` — ohne Eingangsreihenfolge (`WITHOUT ROWID`, EIP-T-033 E). Puffert Einträge und veröffentlicht sie als Batch. Enthält auch die gemeinsame Basis beider Speicher (`SqliteStore`: config, `vernichte_config`, `kopiere_ohne_geheimnisse`). Alle Zugriffe — auch lesende — laufen über ein `RLock`, weil sich alle Threads eine Verbindung teilen (EIP-T-019). |
| `berechtigung_store.py` | SQLite der **Berechtigungsseite** (EIP-T-033, Baustein G): `eligibility`, der kurzlebige `issue_retry` (EIP-T-070) und alle Schlüssel, die mit dem Pseudonym zu tun haben (`poll_secret`, `poll_key`, `cookie_secret`). Eigene Datei neben der Board-Datenbank — ein Join über beide Seiten ist damit eine bewusste Handlung über zwei Verbindungen, kein `SELECT` über zwei Tabellen derselben Datei. Die Trennlinie ist die künftige Betreibergrenze aus Stufe 2. |
| `board_eintrag.py` | Das Eintragsformat: kanonisches JSON, Blatt-Hash, Merkle-Baum, Batch-Kette, Konstruktoren (`vote`, `token_issued`, `poll_open` — trägt den öffentlichen Token-Schlüssel der Umfrage —, `poll_closed`) und `parse(entry) -> Vote \| TokenIssued \| PollOpen \| PollClosed \| Unlesbar`. Rohe Dicts baut und liest niemand mehr selbst. Ein Eintrag, den `parse` nicht deuten kann, wird zu `Unlesbar` — er zählt nirgends mit und macht das Ergebnis unbelastbar, statt still zu verschwinden. |
| `verifikation.py` | Die gesamte Prüfung über das veröffentlichte Board: `pruefe(batches, options) -> Pruefbericht` — Merkle-Wurzeln, Batch-Kette, Signaturen, Abrechnung, Auszählung. Den öffentlichen Schlüssel holt sie sich aus dem Board selbst (`schluessel_aus_board`); ein unabhängig mitgegebener wird dagegen gehalten. Ohne Datenbank, ohne privaten Schlüssel, auch als Kommandozeilen-Werkzeug für Dritte lauffähig. |
| `auditor.py` | Die unabhängige Gegenprobe (EIP-T-071): eine Datei, kein Import aus dem Projekt, rechnet Struktur, Signaturen, Token-Eindeutigkeit, Abrechnung und Auszählung allein aus dem Board-Export nach und hält sie gegen `/api/status`. Prüft mit `--beleg` auch Beleg-Signatur und Inklusionspfad. Gehört bewusst **nicht** zum Kern — sie darf nichts von ihm wissen. |
| `poll_service.py` | Phasenlogik, Regeln, Konsistenzprüfung. Die Auszählung selbst delegiert es an `verifikation.py` und übersetzt Befunde in Abweisungen. Hält den Lebenszyklus beider Umfrage-Schlüssel: erzeugen beim Anlegen, `vernichte_poll_secret()` und `vernichte_poll_key()` beim Schließen. Den privaten Signaturschlüssel liest es bewusst **ohne Zwischenspeicher** aus der Datenbank — ein Cache im Prozess hielte ihn über seine Vernichtung hinaus am Leben. |
| `anker.py` | Die externen Zeitzeugen (EIP-ADR-20260801-002): RFC 3161 und OpenTimestamps, beide hinter einer gemeinsamen schmalen Fläche (`beauftrage`, `werte_auf`, `bezeugter_hash`, `pruefanleitung`). Nichts davon ist selbst gerechnet — das ist Kodex § 3. Die Importe der beiden Fremdbibliotheken liegen bewusst *in* den Methoden: Fehlt eine, fällt genau dieser Zeuge aus und die App startet trotzdem. Kennt keine Datenbank und keinen Service. |
| `demo.py` | Die Angriffsdemos aus §9 — außerhalb des Kerns (EIP-T-050). Sie benutzen `PollService` von außen und schreiben an der Anwendung vorbei direkt in die Datenbank, weil genau das das Angreifermodell ist: Wer die Platte hat, braucht keine API. Verdrahtet nur bei `Settings.demos` (`EIDPOLL_DEMOS`, lokal an, öffentlich aus). |
| `debug.py` | Ringpuffer im Prozessspeicher (500 Ereignisse je Log), bewusst keine zweite Wahrheit. Drei getrennte Logs — Berechtigung, Board, Betrieb (EIP-T-033 G); `/debug` führt sie erst beim Anzeigen zusammen. |
| `stand.py` | Welcher Stand hier läuft (`/version`) und ob er vom veröffentlichten abweicht (EIP-T-074, Kodex § 20). Der Dateihash ist so definiert, dass ihn ein Dritter mit `git ls-files` und `sha256sum` nachrechnen kann — eine Definition für Instanz, Prüfskript und Außenstehende. Bildet die `.gitignore` in Python nach, weil der Container kein git hat. |
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
gegen Korrelation über die IP-Adresse hilft beides nicht (Abschnitt 5).

**Die Verbindung darunter (EIP-T-034):** Seit beide Phasen in einem Klick laufen, gehen sie
typischerweise über *dieselbe TCP-Verbindung* — wer den Socket sieht, verkettet Pseudonym und
Stimme, ohne ein Feld zu lesen. Deshalb gilt: Eine Verbindung, die eine Identität getragen hat,
endet mit ihrer Antwort (Phasen-Routen immer, jede Antwort mit Sitzungs- oder Admin-Cookie
ebenfalls); eine Verbindung ohne Identität bleibt nutzbar. Ob zwei Anfragen denselben Socket
hatten, wird bewusst **nicht gemessen** — das ginge nur, indem der Server Absender-Adresse und
-Port vorhält, und das verbietet Kodex § 1. Deshalb steht hier ausnahmsweise kein Befund im
Debug-Modul, sondern nur die Regel. Ehrlich dazu: Die Maßnahme wirkt auf *unsere* Verbindung; steht
ein fremder Proxy davor (öffentlich: Render, davor Cloudflare), sieht der weiterhin eine Verbindung
und die IP ohnehin. Der anonyme Zustellkanal ist entschieden und vertagt
(EIP-ADR-20260801-003, EIP-T-082).

Auch die **Prüfseite** gehört zur Sitzungstrennung: `/verify` nahm das Token früher als
GET-Parameter entgegen — wer nach der Abstimmung angemeldet prüfte, lieferte dem Server Pseudonym
(Session-Cookie) und Token in einem Request. Die Suche läuft deshalb jetzt im Browser
(`static/verify.js`): Der Server liefert das Board als Datei aus, gesucht wird lokal, und das Token
steht im URL-Fragment (`#`), das der Browser nie mitsendet. Der Server erfährt nur, dass jemand das
Board dieser Umfrage geladen hat.

**Getrennte Speicher und getrennte Logs (EIP-T-033, Baustein G):** Eligibility-Ledger und Board
liegen in zwei Datenbankdateien (`store.py` / `berechtigung_store.py`, der Pfad der zweiten wird aus
`EIDPOLL_DB` abgeleitet), und das Debug-Modul führt drei getrennte Logs — Berechtigungsseite
(eID-Anmeldung, Token-Ausgabe, Umfrage-Schlüssel), Board-Seite (Stimmabgabe, Batches) und Betrieb.
`/debug` führt sie erst beim Anzeigen zusammen. Ehrlich dazu: Beide Seiten laufen weiter in
**einem** Prozess bei **einem** Betreiber — die Trennung macht versehentliche Verkettung im Code
unmöglich und bereitet die Betreiber-Trennung aus Stufe 2 vor, sie ersetzt sie nicht. Und weil die
beiden Ledger-Zahlen nicht mehr aus einer Transaktion kommen, kann die Konsistenzprüfung unter Last
einen Durchlauf lang eine Abweichung zeigen, die beim nächsten Durchlauf verschwindet — eine
bleibende Meldung ist ein Befund, eine verschwindende war der Schnappschuss-Effekt der zwei Dateien.

### Einstellungen

| Variable | Voreinstellung | Zweck |
|---|---|---|
| `EIDPOLL_PORT` | `8731` | Port (nur `start.sh`) |
| `EIDPOLL_DB` | `app/data/eidpoll.sqlite3` | Board-Datenbank; die Berechtigungs-Datenbank liegt daneben (`<name>.berechtigung.sqlite3`, EIP-T-033 G) |
| `EIDPOLL_ADMIN_TOKEN` | `admin` | Admin-Zugang |
| `EIDPOLL_ANTWORT_FLOOR_S` | `0.3` | Mindest-Antwortzeit der Phasen-Routen in Sekunden, `0` schaltet ab (EIP-T-033 F) |
| `EIDPOLL_RETRY_CACHE_H` | `24` | Lebensdauer des Wiederhol-Puffers der Token-Ausgabe in Stunden, `0` schaltet ab (EIP-T-070) |
| `EIDPOLL_NENNER` | `59200000` | Nenner der Beteiligungsquote (EIP-T-025) |

**Der Nenner.** Jedes Ergebnis erscheint als Quote, nie als bloße Teilnahmezahl: *N von
59.200.000 Wahlberechtigten*. Der Nenner sind die Deutschen ab 18 im Inland nach der
[Schätzung der Bundeswahlleiterin zur Bundestagswahl 2025](https://www.bundeswahlleiterin.de/mitteilungen/bundestagswahlen/2025/20241204_btw25_schaetzung-wahlberechtigte.html)
— amtlich, registerbasiert, datiert, zu jeder Bundestagswahl neu festgestellt.

Nicht gewählt wurde „alle Ausweisinhaber": **diese Zahl existiert nicht.** Das BMI führt keine
zentrale Statistik über gültige Personalausweise; die Daten liegen bei rund 5.500
Ausweisbehörden, und ob ausgelieferte Ausweise noch im Umlauf sind, ist unbekannt. Ein Nenner,
den niemand nachschlagen kann, ist keiner.

Der Wert steht in `config.py` und nicht im Template, weil er vorab und dauerhaft feststehen muss.
Ein je Umfrage passend gewählter Nenner wäre genau der Methodentrick, gegen den dieses Verfahren
antritt. Eine **Veröffentlichungsschwelle** gibt es bewusst nicht: Jedes Ergebnis erscheint mit
seiner Quote, auch eine sehr kleine — was Dritte daraus machen, regelt Transparenz, nicht
Zurückhaltung.

**Schlüssel und ihre Lebensdauer.** Es gibt keinen globalen Token-Signaturschlüssel mehr
(EIP-T-069). Jede Umfrage bekommt beim Anlegen zwei eigene, beide in der Datenbank, beide beim
Schließen vernichtet:

| Schlüssel | Wozu | Wann weg |
|---|---|---|
| `poll_key:{id}` | signiert die Stimm-Token dieser Umfrage (RSA 3072, RFC 9474) | beim Schließen |
| `poll_secret:{id}` | leitet den Wahlberechtigungs-Schlüssel aus dem Pseudonym ab | beim Schließen |

Der *öffentliche* Teil des Token-Schlüssels steht im Board (`POLL_OPEN`) und überlebt dort — sonst
wäre die Auszählung nach dem Schließen nicht mehr nachprüfbar. Dauerhaft bleiben nur der
Beleg-Schlüssel (Ed25519) und der Cookie-Schlüssel; beide signieren nichts, was gezählt wird.

**Wird die Datenbankdatei gelöscht, werden alle ausgegebenen Tokens ungültig.**

### Tests

```bash
python3 app/blind.py         # RFC-9474-Testvektor A.4 und Roundtrip, Serverseite
node app/blind_vektor.mjs    # derselbe Vektor gegen static/blind.js, Browserseite
python3 app/smoke_test.py    # sieben Abnahmepunkte serverseitig, plus beide Angriffe
                             # darin: Board-Prüfung ohne SQLite und ohne TestClient,
                             # und beide Vektorprüfungen (die JS-Seite über node)
node app/ballot_test.mjs     # Stimmzettel-Flow ohne Browser: Abbruch zwischen Signatur
                             # und Abgabe, Wiederverwendung derselben Berechtigung

cd app && EIDPOLL_DB=/tmp/bt.sqlite3 python3 -m uvicorn web:app --port 8899 &
python3 app/browser_test.py  # derselbe Durchlauf im echten Browser
```

Die drei Krypto-Tests prüfen verschiedene Dinge und ersetzen einander nicht:

- **`blind.py` und `blind_vektor.mjs`** halten je eine Seite gegen den RFC. Sie beantworten die
  Frage, ob die Implementierung rechnet, was der Standard meint — mit Zahlen, die nicht aus diesem
  Projekt stammen. Ohne sie könnten beide Seiten denselben Fehler machen und sich deshalb einig sein.
- **`browser_test.py`** hält beide Seiten gegeneinander, im echten Browser gegen den echten Server.
  Nur dort zeigt sich, ob `blind.js` und `blind.py` *miteinander* bitgleich rechnen; weicht es ab,
  weist der Server die Stimme als „Token-Signatur ungültig" ab.
- **`ballot_test.mjs`** prüft die Krypto ausdrücklich nicht — dort ist der Server gestellt und die
  Signatur eine Attrappe; geprüft wird allein der Zustandsverlauf um EIP-ADR-20260725-002.

Fehlt `node`, meldet `smoke_test.py` die Browser-Seite als ungeprüfte Lücke statt den Prüffall
stillschweigend zu überspringen.

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
keine geprüfte Umsetzung gibt (PyPI-Suche **2026-08-01**: keine Distribution unter
`blind-rsa-signatures`, `blind_signatures`, `blindsig`, `rsa-blind-signatures`, `pyblindsig`,
`rsabssa`, `blind-signature`, `pyblind-rsa`, `blindrsa`, `py-blind-rsa`, `rfc9474`).
Geprüft zugekauft sind SHA-384 und die PSS-Verifikation aus `cryptography`; selbst geschrieben sind
EMSA-PSS-ENCODE, MGF1 und die Blinding-Arithmetik — in Python und in JavaScript. Deutlich besser
als der textbook-Chaum des Prototyps, aber kein Ersatz für einen Audit.

Was seit EIP-T-008 dazugekommen ist und was nicht: Beide Seiten rechnen den **Testvektor aus
RFC 9474 Anhang A.4** nach, Schritt für Schritt und mit dem Blendfaktor aus dem RFC statt einem
eigenen (Abschnitt „Tests"). Das schließt die Klasse von Fehlern aus, bei denen die Implementierung
in sich stimmig ist und trotzdem nicht das rechnet, was der Standard meint — genau die Klasse, die
ein Roundtrip-Test nicht sieht. Es schließt *nicht* aus, was ein Audit sähe: Seitenkanäle,
Zeitverhalten, Speicherbehandlung von Schlüsselmaterial. Der Vektor sagt „richtig gerechnet", nicht
„sicher implementiert".

**Für die Browser-Seite gibt es inzwischen eine Bibliothek, sie ist aber nicht eingebaut.**
`@cloudflare/blindrsa-ts` (0.4.6, Stand 2026-08-01) setzt RFC 9474 um und wird von Cloudflare für
Privacy Pass gepflegt. Der Einbau zieht eine npm-/Bundler-Toolchain in eine App, die heute nacktes
ES-Modul ausliefert und jede Client-Datei einzeln hashbar hält (§ 20, EIP-T-007) — das ist eine
Architekturentscheidung und keine Abhängigkeitspflege → EIP-T-079. Für Python gibt es weiterhin
nichts.

**Der Browser prüft die entblindete Signatur selbst** (seit 2026-08-01, EIP-T-080). RFC 9474 §4.4
Schritt 5 verlangt, dass der Client sein Ergebnis vor der Weitergabe verifiziert und bei einem
ungültigen einen Fehler ausgibt statt der Signatur. `static/blind.js:finalizeGeprueft()` tut das
mit **WebCrypto** und nicht mit eigener PSS-Verifikation — der Rest der Datei ist handgeschriebene
Krypto, und eine handgeschriebene Prüfung davon würde denselben Denkfehler zweimal machen und sich
bestätigen.

Sicherheitslücke war das Fehlen nicht: Der Server nimmt eine ungültige Signatur ohnehin nicht an,
und der §7.3-Angriff, gegen den die Prüfung mit schützt, greift hier nicht (siehe unten). Es kostete
Diagnosefähigkeit — eine kaputte Serverantwort (falscher Umfrage-Schlüssel, verrechnet, unterwegs
verstümmelt) sah für Teilnehmende aus wie ein abgewiesener Stimmzettel und stand im Debug-Modul als
abgewiesene Stimme statt als Serverfehler. Jetzt endet der Weg in Phase A, mit eigener Meldung, und
der Client sagt es dem Betreiber (`POST /api/melde/signatur/{poll}` → `error` im Debug-Modul,
Kategorie `signatur`). Die Berechtigung bleibt dabei wiederholbar: Der Zustand aus EIP-T-070 steht
noch, dieselbe verblindete Anfrage lässt sich unverändert erneut stellen.

Was die Meldung überträgt, ist die Tatsache und die Umfrage — kein Token, keine verblindete Form,
kein Freitext. Ein Freitextfeld wäre ein Kanal in das Log des Betreibers und kein Befund (Kodex §1).

**Warum PSSZERO-Deterministic vertretbar ist.** RFC 9474 §5 empfiehlt die *Randomized*-Varianten
und knüpft die deterministische an eine Bedingung, die §7.3 nennt: Ein Signierender mit bösartig
erzeugtem Schlüssel kann aus dem Blinding Rückschlüsse auf die Eingabe ziehen, wenn er sie erraten
kann. Hier ist die Eingabe das Stimm-Token: 32 Byte aus `crypto.getRandomValues`, im Browser
erzeugt, lange nachdem der Schlüssel feststand. Bedingung (2) aus §7.3 ist damit erfüllt. Das ist
kein Nebensatz, denn der Betreiber erzeugt den Signaturschlüssel allein — der Fall aus §7.3 *ist*
das Angreifermodell dieser App, und er trägt allein wegen dieser Entropie nicht. Deterministisch
gebraucht wird die Variante, weil ein Token sich im Board unter genau einer Signatur wiederfinden
lassen muss.

**Schlüssellänge: 3072 Bit, entschieden am 2026-08-01.** Vorher 2048. Ausschlaggebend war nicht
akute Schwäche von 2048, sondern Konsistenz nach außen: Die Basisidee setzt 3072 an, BSI TR-02102-1
empfiehlt für RSA mindestens 3000 Bit, und `EIP-RFC-20260726-002` beruft sich auf BSI-Vorgaben —
darunter zu liegen wäre im Pitch angreifbar gewesen. Gegen den Wechsel sprach nichts Messbares:
Schlüsselerzeugung ~0,2 s, Blinding 1,3 ms, Signieren und Entblinden 82 ms statt 24 ms; im Browser
bleibt es billig, weil der öffentliche Exponent 65537 nur 17 Bit hat. Der Wert gilt für neu
angelegte Umfragen — bereits laufende behalten ihren 2048-Bit-Schlüssel und funktionieren weiter,
weil der Modulus aus dem Schlüssel kommt und nicht aus der Konstanten.

**Keine Nötigungsresistenz.** Der Beleg ist eine Quittung. Bewusst so entschieden.

**Kein Schutz gegen den Betreiber auf Netzwerk-Ebene.** IP-Adressen und Zeitpunkte können die
kryptografisch getrennte Verbindung wiederherstellen. Das ist eine andere Schicht, gegen die die
Krypto hier wirkungslos ist (§13, Risiko-Knoten 1) — und eine vom Betreiber selbst betriebene
Anonymisierung schützt nicht gegen ihn.

**Kein geprüfter Client-Code.** Der Browser-Krypto-Code kommt vom Betreiber (§10, Helios-Problem).
Abgleichbar ist er seit dem 2026-08-01 (Abschnitt oben) — geprüft ist er damit nicht: Der Vergleich
zeigt, dass ausgeliefert wird, was veröffentlicht ist, nicht dass der veröffentlichte Code richtig
rechnet. Und er entlarvt keine Auslieferung, die einzelne Besucher gezielt anders bedient.

**Nicht gebaut** (§12): verteilte Schwellensignatur, Gegenzeichner gegen Split-View (der Zeitanker
steht seit 2026-08-01, die Gegenzeichner nicht), Produktiv-Berechtigungs-
zertifikat, eIDAS-Ausland, Multi-Tenant, mehrere Fragen oder Ranking. Die Oberfläche verspricht
nichts davon.
