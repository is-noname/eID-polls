<!-- Erzeugt von scripts/sync_public_docs.py aus KODEX-PROTOKOLL.md im Elternordner.
     Nicht hier bearbeiten - Aenderungen gehoeren ins Original. -->
# Kodex-Protokoll

*Änderungs- und Verstoßprotokoll zum [Kodex](/kodex) (§ 17, § 18). Das Verstoßprotokoll steht unten und ist der Teil, um dessentwillen diese Seite existiert: § 18 verlangt den Eintrag auch dann, wenn niemand außerhalb den Fehler bemerkt hätte. Kennungen der Form `EIP-T-…` verweisen auf projektinterne Tickets.*

> Archiv zum [Kodex](/kodex) — Änderungen und Verstöße. Ausgelagert in Version 5, weil beides Historie ist:
> Man liest es, wenn man wissen will, wie eine Regel entstanden ist oder wo sie gebrochen wurde, nicht
> wenn man gerade entscheidet. Der Kodex selbst bleibt damit das Dokument, das man im Moment der
> Entscheidung aufschlägt.
>
> Verbindlich sind § 17 (Änderungen versioniert und begründet) und § 18 (Verstöße dokumentiert) —
> beide Pflichten werden hier erfüllt, nicht im Kodex. Ein Eintrag hier ist Teil des Kodex, nicht sein
> Anhang.

## Änderungsprotokoll

### Version 18 — 2026-08-01

**§ 2 bekommt seine Netzwerkebene — und der Grund, sie überhaupt aufzuschreiben, ist ein Korrelator,
den der Paragraph bis heute nicht kannte**
(EIP-ADR-20260801-003,
EIP-T-034).

**Was der Paragraph nicht gesehen hat.** Die Netzwerkebene stand seit Version 7 als Zeiger auf ein
Ticket, und die Sache galt als „die IP sieht man während des Requests". Das war zu wenig. Seit
EIP-ADR-20260725-002 laufen beide Phasen in *einem* Klick gegen
dieselbe Origin — also typischerweise über **dieselbe TCP-Verbindung**. Wer den Socket sieht,
verkettet Pseudonym und Stimme, ohne ein Feld zu lesen. Baustein F aus EIP-T-033 nimmt dem
Abstimm-Request Cookie, Auth-Header und Referrer; die Schicht darunter hat er nie angefasst.

**Warum das die Entscheidung umdreht.** Heute verdeckt Renders Loadbalancer diesen zweiten
Korrelator — bei uns endet nur der Proxy-Socket. Ein Onion-Service nimmt genau diesen Proxy weg und
reichte uns den Client-Socket, den wir vorher nicht hatten. Der anonyme Kanal hätte also den
Korrelator ausgetauscht statt ihn zu entfernen. Gebaut wird deshalb zuerst die Verbindungstrennung,
und erst dann der Kanal.

**Was umgesetzt ist.** Eine Verbindung, die eine Identität getragen hat, endet mit ihrer Antwort:
die Phasen-Routen schließen immer, jede Antwort mit Sitzungs- oder Admin-Cookie ebenfalls. Eine
Verbindung ohne Identität bleibt nutzbar — die Regel ist gezielt, nicht pauschal, sonst wäre sie
ein Kostenposten ohne Wirkung. Dazu Kanalblindheit: Absender-IP aus der Proxy-Kette und
angesprochener Hostname stehen nirgends, und ein Test hält das fest, statt es zuzusagen.

**Was ausdrücklich nicht gemessen wird.** Ob zwei Requests denselben Socket hatten. Das ginge nur,
indem der Server Absender-Adresse und -Port vorhält — ein neues Datum über Teilnehmende und damit
§ 1. Die Regel wird verhindert statt gemeldet. Dass hier ausnahmsweise kein Befund im Debug-Modul
steht, ist keine Nachlässigkeit, sondern die Rangfolge: Ein Befund, den man nur durch Vorhalten der
IP erzeugen kann, ist teurer als das Problem, das er meldet.

**Was `offen` bleibt und jetzt ehrlicher dasteht.** Der Kanal selbst, als Option und nicht als
einziger Weg → EIP-T-082, fällig vor `produktiv`. Dazu zwei
Grenzen, die in den Paragraphen gehören und nicht in einen ADR allein: Die Verbindungstrennung
wirkt auf *unsere* Verbindung — auf der laufenden Instanz sieht der fremde Proxy weiterhin eine
Verbindung und die IP ohnehin. Und die Zusage k = 10 deckt den Kanal nicht: Die wirksame
Anonymitätsmenge eines Kanalnutzers ist die Zahl der Stimmen aus demselben Kanal im selben Batch,
bei einem einzelnen also 1. Ein Kanal, der als sicher angeboten und von drei Leuten benutzt wird,
ist eine Zusage ohne Deckung.

**Die Schuldenübersicht bekommt eine zweite Zeile für § 2, die Zahl bleibt bei 11 von 20.** Das ist
der zweite Fall nach Version 14, in dem die Kennzahl verschweigt, was passiert ist — hier sogar in
beide Richtungen: Es wurde etwas gebaut, *und* es wurde eine Schuld sichtbar gemacht, die vorher
nur als Zeiger im Fließtext stand. Wer Paragraphen zählt, sieht keins von beidem.

### Version 17 — 2026-08-01

**§ 2 bekommt seinen Anker — und § 2 wird zugleich korrigiert, weil er zu viel behauptet hat**
(EIP-ADR-20260801-002,
EIP-T-006).

**Was umgesetzt ist.** Jede `batch_root(n)` wird bei zwei unabhängigen Diensten datiert: einem
RFC-3161-Zeitstempel (freetsa.org, Antwort in Sekunden) und OpenTimestamps, das den Hash gebündelt
in eine Bitcoin-Transaktion schreibt. Beide Belege stehen öffentlich unter
`/anker/{umfrage}/{batch}/…` und sind mit `openssl ts -verify` und `ots verify` prüfbar — mit
Werkzeugen, die es vor uns gab, gegen Infrastruktur, die uns nicht gehört. Läuft die lokal
nachgerechnete Wurzel von der bezeugten weg, ist das ein Befund im Debug-Modul und ein Banner auf
der öffentlichen Board-Seite. Der Hash wird dabei aus dem **Beleg** gelesen, nicht aus der
Datenbankspalte: Wer die Datenbank umschreibt, ändert die Spalte mit, den signierten Beleg nicht.

**Was das schließt.** Das rückwirkende Umschreiben — die Angriffsdemo „Board umschreiben" unter
`/admin`. Sie rechnet die Kette neu und bleibt an jeder lokalen Prüfung unsichtbar; am Zeitstempel
nicht mehr, denn für die neue Wurzel gäbe es nur ein Datum von heute.

**Was der Paragraph falsch gesagt hat.** § 2 führte „öffentlicher Anker gegen Split-View" als einen
Vermerk. Das sind zwei Angriffe, und der Anker trifft nur den ersten. Gegen Split-View — zwei von
Anfang an parallel geführte Boards — leistet ein Zeitstempel prinzipiell nichts: Beide Wurzeln
ließen sich ehrlich datieren, jede zu ihrer Zeit. Dazu gehört Aufzählbarkeit, also unabhängige
Gegenzeichner, die alle je veröffentlichten Wurzeln vergleichen
(EIP-T-036). Der Vermerk wandert deshalb dorthin und wird **nicht**
gestrichen. Wer die Umsetzung als Auflösung dargestellt hätte, hätte einen Paragraphen freigekauft,
indem er die Hälfte eines Problems löst und die Überschrift behält.

**§ 4 bekommt dafür eine Kennzeichnungspflicht.** Wo ein Anker angezeigt wird, ist seine Grenze
mitzunennen. Die Board-Seite tut das im selben Abschnitt, in dem sie den Anker zeigt — nicht in
einer Fußnote.

**`check_kodex.py` unterscheidet jetzt Zitat und Zeiger.** § 2 nennt seit dieser Version zwei
Tickets: ein erledigtes als Beleg dafür, was der Anker schon leistet, und ein offenes für das, was
fehlt. Das Skript hätte den Beleg als Formfehler gemeldet — und damit ausgerechnet die ehrlichere
Fassung des Paragraphen bestraft. Es prüft deshalb nur noch Tickets, die als Zeiger (`→ EIP-T-NNN`)
genannt sind; ohne Zeiger zählt weiter jede Nennung, damit kein Paragraph durchrutscht, weil
niemand einen Pfeil gesetzt hat. Dieselbe Unterscheidung gilt im Wiki seit EIP-T-053.

**Die Zahl bleibt bei 11 von 20, Grenze 8, der Baustopp gilt weiter.** Zum fünften Mal in Folge
steht die Kennzahl still, während sich etwas bewegt — und diesmal ist das ausdrücklich richtig so:
Ein halb gelöstes Problem ist ein offenes Problem.

### Version 16 — 2026-08-01

**§ 2 löst zwei seiner drei Vermerke ein: Speichertrennung und die Token-Suche auf `/verify`**
(EIP-T-033, Bausteine F und G).

**Was umgesetzt ist.** Eligibility-Ledger, Wiederhol-Puffer und alle Pseudonym-Schlüssel liegen
jetzt in einer eigenen Datenbankdatei (`berechtigung_store.py`), getrennt von Board, Batches und
Vote-Ledger (`store.py`) — ein Join über beide Seiten ist eine bewusste Handlung über zwei
Verbindungen, kein `SELECT` über zwei Tabellen derselben Datei. Das Debug-Modul führt drei
getrennte Logs (Berechtigung, Board, Betrieb); kein einzelnes Log hält beide Phasen, `/debug`
führt sie erst beim Anzeigen zusammen. Und die Token-Suche auf `/verify` läuft im Browser über
den Board-Export: Das Token steht im URL-Fragment, das der Browser nie mitsendet — der Fall
„angemeldet geprüft, Pseudonym und Token im selben Request" ist damit strukturell weg, nicht nur
unterlassen.

**Was die Trennung kostet, offen gesagt.** Die Token-Ausgabe war vorher eine Transaktion
(Anspruch + Board-Eintrag); über zwei Dateien gibt es die nicht mehr. Der Ausgleichspfad nimmt
einen Anspruch zurück, dessen Board-Eintrag scheitert, und das verbleibende Fenster macht die
Konsistenzprüfung sichtbar statt eine Transaktion es zu verdecken. Unter Last kann sie deshalb
einen Durchlauf lang eine Abweichung zeigen, die beim nächsten verschwindet — die Leserichtung
ist so gewählt, dass daraus nie ein falscher *Überschuss* wird (die Richtung, die § 9 anzeigt).

**Was die Trennung nicht leistet.** Beide Seiten laufen weiter in einem Prozess bei einem
Betreiber. Wer beide Nachrichten empfängt, kann sie im Empfangsfenster zeitlich zuordnen — das
bleibt die Grenze des Einzelbetreibers (EIP-T-037) und der
Netzwerkebene (EIP-T-034). Die Trennung macht
versehentliche Verkettung im Code unmöglich und legt die Trennlinie dorthin, wo später die
Betreibergrenze verlaufen soll — sie ersetzt sie nicht.

**Die Zahl bleibt bei 11 von 20, Grenze 8, der Baustopp gilt weiter** — § 2 trägt noch den
Anker-Vermerk (EIP-T-006). Zum vierten Mal in Folge steht die Kennzahl still, während sich etwas
bewegt.

### Version 15 — 2026-08-01

**Die Mindestmenge aus § 2 gibt es jetzt.** Bis heute zählte k *Einträge*, und weil jede Teilnahme
zwei erzeugt (Ausgabe + Stimme), war die zugesagte Menge in Wahrheit die Hälfte. Seit
EIP-T-076 zählt sie **Stimmen**: k = 10 heißt zehn Stimmen, der
Zeitdeckel bleibt bei 6 Stunden.

**Warum das kein Tausch ist.** Der Befund kam aus einer Messung
(EIP-RPT-20260731-001 Anonymitaetsmenge-Batch-Simulation), und dieselbe Messung zeigt, dass die
Bindung an Stimmen nichts kostet: Der Anteil der Stimmen, die in einem Batch mit weniger als fünf
anderen liegen, fällt unter Andrang von 23,6 % auf 0,0 % — bei gleicher Batchgröße und gleicher
Wartezeit. Es gibt keinen Parameter, gegen den hier getauscht worden wäre; die alte Zählweise war
schlicht die falsche Größe. Die Simulation ist mitgezogen und läuft weiter gegen die Implementierung
(`scripts/sim_anonymitaetsmenge.py --gegenprobe`) — ein Modell, das neben dem Betrieb herläuft, misst
sonst irgendwann etwas anderes als der Betrieb.

**Was die Regel weiterhin nicht deckt, und was jetzt darüber gesagt wird.** Löst der Zeitdeckel aus
oder endet die Umfrage, wird auch unter k veröffentlicht — bei geringer Beteiligung ist das der
Normalfall und durch keine Parameterwahl zu beheben (bei 25 Teilnehmenden über sieben Tage steht
jede fünfte Stimme allein in ihrem Batch). Neu ist, dass diese Fälle nicht mehr nur im Kleingedruckten
stehen: Das Board nennt für jeden Batch die tatsächliche Stimmenzahl und hebt die kleinste hervor,
und der Betreiber bekommt jeden Batch unter k als Befund ins Debug-Modul, während die Umfrage läuft.
Eine Zusage, die man nur im Nachhinein prüfen kann, ist nach § 4 keine.

**Die Zahl bleibt bei 11 von 20, Grenze 8, der Baustopp gilt weiter** — § 2 trägt noch zwei
Vermerke. Zum dritten Mal in Folge steht die Kennzahl still, während sich etwas bewegt; die
Begründung steht bei der Schuldenübersicht.

### Version 14 — 2026-08-01

**§ 20 löst seine Schuld ein — und offenbart dabei eine ältere.** Der Client ist ab sofort
nachrechenbar, ohne diese Instanz zu fragen (EIP-T-007). Beim Nachsehen, was
der Paragraph eigentlich verlangt, fiel auf, dass sein **erster Satz** nie erfüllt war: Es gibt keine
Lizenz. Als Verstoß V-004 protokolliert.

**Was gebaut wurde, und warum es mehr ist als ein Hash.** Ein Hash über `static/` hätte sich an einem
Nachmittag veröffentlichen lassen — und wäre eine Aussage über einen Teil gewesen, die wie eine über
das Ganze aussieht: Die Verdrahtung der Umfrageseite stand **inline** in den Templates. Inline-Code
läuft im Browser, steckt aber in der gerenderten Seite und ist mit keiner Repo-Datei mehr
vergleichbar. Er ist deshalb in eigene Dateien gewandert (`static/poll.js`, `admin.js`, `debug.js`,
`theme.js`); die umfragespezifischen Werte kommen jetzt als JSON-Datenblock, also als Daten statt als
eingesetzter Quelltext. Ein Rückfall meldet sich selbst als Inkonsistenz im Debug-Modul, statt still
den Geltungsbereich des Hashs zu verkleinern.

**Der Unterschied zu EIP-T-074, und warum er der eigentliche Punkt ist.** Der `treehash` unter
`/version` ist eine Selbstauskunft: Wer den ausgelieferten Code ändert, ändert diese Antwort mit. Der
Client-Vergleich braucht sie nicht — abgerufene Datei gegen öffentliches Repository, zwei Größen aus
zwei Quellen, keine davon eine Behauptung dieser App. Damit ist der Satz aus § 20 eingelöst, der bis
heute der schwerste war: *Was im Browser läuft, muss aus dem veröffentlichten Stand reproduzierbar
sein.* Ein Build-Schritt, der dabei reproduziert werden müsste, existiert gar nicht — nichts wird
gebündelt oder minifiziert, und genau das ist die Bedingung, unter der die Prüfung ohne unser
Werkzeug funktioniert.

**Was der Paragraph nun ehrlicher sagt.** Der Vergleich entlarvt eine Auslieferung, die für alle
abweicht, nicht eine, die einem einzelnen Besucher anderen Code schickt — dieselbe Struktur wie
Split-View beim Board (§ 2). Und er hilft niemandem, der nicht nachrechnet. Beides steht jetzt im
Statusteil, nicht als Fußnote.

**Die Zahl bleibt bei 11 von 20, Grenze 8, der Baustopp gilt weiter** — zum zweiten Mal in Folge aus
einem Grund, den die Zahl verschweigt. Diesmal umgekehrt zu Version 13: Dort trug ein neuer Text
nichts ab, hier trägt gebaute Arbeit etwas ab, und der Paragraph bleibt trotzdem belastet, weil eine
zweite, ältere Schuld darunter zum Vorschein kam. **Die Lehre daran gilt über § 20 hinaus:** Ein Satz
auf `bindend` steht in keiner Schuldenübersicht und wird deshalb auch nie geprüft — er gilt als
erledigt, weil ihn nie jemand als offen markiert hat. V-004 lag über einen Monat offen im hellsten
Licht des Projekts, im ersten Satz des Paragraphen über Offenheit.

### Version 13 — 2026-08-01

**§ 16 bekommt sein Instrument — und die ehrliche Beschreibung davon.** Die
Nutzungsbedingungen für Einbetter liegen vor (EIP-T-062): Verbot
bindender Abstimmungen, Nennerpflicht, unveränderte Frage, erkennbare Herkunft, dazu die Rechtsfolge
(Entzug der Einbettungserlaubnis, Offenlegung im [Transparenzbericht](/transparenz)bericht, keine Vertragsstrafe) und
eine Aufstellung, welche der vier Zusagen technisch abgesichert ist. Ergebnis dieser Aufstellung:
zwei ja, eine halb, und ausgerechnet das Wahlverbot gar nicht.

Deshalb ändert sich auch die **Regel** von § 16. Sie sagte „Wir setzen das über Nutzungsbedingungen
durch, nicht nur als Bekenntnis" und ließ offen, was Durchsetzung hier heißt. Sie sagt jetzt, dass
es ein Entzugsrecht im Nachhinein ist und keine technische Verhinderung — wir sehen nicht, wozu
jemand ein Ergebnis verwendet. Das ist keine Abschwächung, sondern § 4 auf den eigenen Paragraphen
angewandt: Die alte Formulierung war die stärkere Behauptung, aber nicht die wahre.

**Der Vermerk wandert, statt zu verschwinden.** Er lautete „Durchsetzung über Nutzungsbedingungen"
und zeigte auf EIP-T-062; er lautet jetzt „Vergabe und Entzug der Einbettungserlaubnis" und zeigt
auf EIP-T-023. Grund: Was fehlt, ist nicht mehr der Text, sondern
der Zugang, den ein Verstoß kosten könnte. Ohne Einbettung gibt es keinen. Der Entzug ist damit die
einzige Folge, die überhaupt in unserer Hand liegt, und heute liegt sie es nicht.

**Grund für die Reihenfolge.** Die Bedingungen entstehen vor dem ersten Einbetter, obwohl niemand sie
verlangt hat und niemand sie liest. Eine Regel, die erst mit ihrem ersten Fall entsteht, entsteht
unter dessen Druck — und der erste Einbetter wird eine Redaktion mit Reichweite sein, nicht ein
Zufallsgast. Umgekehrt gilt § 4 b: Das Widget zu bauen, um den Paragraphen zu räumen, wäre unter dem
Baustopp nicht erlaubt und wäre auch die falsche Reihenfolge.

**Die Zahl bleibt bei 11 von 20, Grenze 8, der Baustopp gilt weiter.** § 16 war belastet und bleibt
es. Das ist das gewollte Ergebnis: Wer einen Paragraphen dadurch freikauft, dass er ein Dokument
schreibt, hat die Kennzahl bedient und nichts abgetragen. Ein Hinweis darauf steht jetzt über der
Schuldenübersicht.

### Version 12 — 2026-07-31

**§ 2 verliert seine Mindestmenge.** Die Regel verlangt, dass „vor der Veröffentlichung eines Boards
eine Mindest-Anonymitätsmenge erreicht sein muss". Die Simulation aus
EIP-T-072 hat gemessen, dass es diese Menge heute nicht gibt
(`EIP-RPT-20260731-001`): k zählt Board-*Einträge*, und weil jede Teilnahme zwei erzeugt
(Tokenausgabe + Stimme), liegt eine Stimme unter genau 5 anderen statt unter 10. Schlimmer ist der
zweite Befund — weil die Mischung aus Ausgaben und Stimmen im Puffer schwankt, ist selbst diese 5
keine Schranke: Unter Andrang liegen bis zu 23,6 % der Stimmen in einem Batch mit weniger als 5
Stimmen. Der Statusteil von § 2 sagt das jetzt, und die Schuldenübersicht führt den Vermerk mit
Fälligkeit vor `produktiv` → EIP-T-076.

**Grund.** Die Zahl 10 stand seit Version 7 im Kodex und war nie gemessen — die ADR hatte sie
begründet, nicht geprüft, und der Kodex hatte den Vorbehalt „etwa k/2" bereits notiert und auf
EIP-T-072 gezeigt. Damit war der Punkt korrekt fällig gestellt; unzulässig wäre gewesen, ihn nach
der Messung stehen zu lassen. Die Formulierung „etwa k/2" war zudem zu weich: Es ist im
Sättigungsfall exakt k/2 und darunter, wenn der Zeitdeckel greift.

Mitgeschrieben, weil es den Kodex selbst betrifft: Bei 25 Teilnehmenden über 7 Tage steht **jede
fünfte Stimme allein in ihrem Batch** — bei jedem k. Das ist keine Schuld, die ein Ticket abträgt,
sondern die Grenze des Mechanismus. Sie gehört in § 2 und in die Kommunikation
(EIP-T-028), nicht in die Schuldenübersicht.

**Die Zahl ändert sich nicht: 11 von 20, Grenze 8, der Baustopp gilt weiter** — § 2 war bereits
belastet. Genau das ist hier bemerkenswert: Ein Befund dieser Größe bewegt die Kennzahl um null,
weil sie Paragraphen zählt und nicht Schulden. Der Hinweis darauf steht jetzt in der
Schuldenübersicht, damit ein späterer Leser den 2026-07-31 nicht für einen ruhigen Tag hält. Die
Änderung ist unter § 4 b zulässig als Arbeit, die einen Mangel prüft und dokumentiert; die Behebung
ist Aufgabe von EIP-T-076 und trägt die Schuld dann tatsächlich ab.

**Nachtrag, gleiche Version (EIP-T-073, 2026-08-01).** Der Schuld-Vermerk unter § 5 begründete das
Fehlen des Eingangskanals mit „das Projekt hat keine Domain". Diese Begründung ist überholt: Der
Betreiber hat entschieden, den Kanal als eigenes Postfach bei einem Mailprovider zu führen — ohne
eigene Domain und ohne die private Adresse an das Projekt zu binden. Damit ist offen nur noch die
Einrichtung, nicht mehr die Frage. § 5, die Schuldenübersicht, [Transparenzbericht](/transparenz) und
EIP-RFC-20260729-001 sagen das jetzt gleichlautend.

**Grund für den Eintrag.** Eine stehengebliebene Begründung ist nicht harmlos: „keine Domain" liest
sich als äußeres Hindernis, „noch nicht eingerichtet" als offene eigene Arbeit. Der Unterschied ist
genau der zwischen einer Lücke, die man erklärt, und einer, die man schuldet — und § 4 verlangt die
zweite Lesart, wo sie zutrifft.

**Die Zahl ändert sich nicht: 11 von 20, Grenze 8, der Baustopp gilt weiter.** § 5 bleibt belastet,
bis die Adresse erreichbar und veröffentlicht ist. Zulässig unter § 4 b als Arbeit, die eine Schuld
präzisiert und ihren Abtrag vorbereitet; keine Regeländerung, deshalb keine neue Version.

**Nachtrag, gleiche Version (EIP-T-074, 2026-08-01).** § 20 führte die Übereinstimmung von
Repository und Auslieferung als `Disziplin` — eine Zusage, die niemand prüfte und die deshalb reißen
konnte, ohne aufzufallen. Genau das war V-001. Seit EIP-T-074 weist die Instanz ihren Stand unter
`/version` aus: benannter Commit **und** ein Hash über die Dateien, die sie tatsächlich ausliefert.
`app/DEPLOY.md` beschreibt den Prüfweg in zwei Befehlen, die ohne Rückfrage bei uns auskommen —
das verlangt § 20 im letzten Satz. Abweichungen erscheinen im Debug-Modul als Inkonsistenz, und der
Abgleich gehört als Pflichtschritt zu jeder Veröffentlichung.

**Grund für den Eintrag.** Die Fälligkeit dieser Betriebsstufe war nicht „es entsteht keine
Abweichung" — das wäre bei getrenntem Arbeitsbaum und Instanz nicht einlösbar —, sondern „eine
entstandene fällt auf". Der Unterschied ist der zwischen einem Versprechen und einem Melder, und der
Statusteil von § 20 sagt jetzt beides: was der Melder leistet, und dass er die Selbstauskunft des
Servers bleibt, den man gerade prüft. Gegen einen Betreiber, der lügt, hilft er nicht — dafür steht
weiterhin EIP-T-007, fällig `produktiv`. Wer den Vermerk verschwinden ließe, hätte aus „prüfbar"
ein „bewiesen" gemacht, und das ist der Fehler, gegen den § 4 geschrieben ist.

Mitgeschrieben, weil es eine Formkorrektur am Kodex ist: § 2 verlinkte für die Herkunft der
Simulationszahlen EIP-T-072, ein erledigtes Ticket. Nach § 4 a liest sich das wie eine Schuld, die an
einem abgeschlossenen Ticket hängt — `scripts/check_kodex.py` hat es zu Recht beanstandet. Die
Herkunft steht im Report selbst; § 2 verweist jetzt dorthin.

**Die Zahl ändert sich nicht: 11 von 20, Grenze 8, der Baustopp gilt weiter.** § 20 bleibt belastet,
solange der reproduzierbare Build aussteht. Dass ein Ticket, das eine Fälligkeit vollständig
einlöst, die Kennzahl nicht bewegt, ist dieselbe Schwäche der Zahl wie am 2026-07-31 — sie zählt
Paragraphen, nicht Schulden. Zulässig unter § 4 b als Arbeit, die eine Schuld abträgt und einen
Verstoßmechanismus schließt; keine Regeländerung, deshalb keine neue Version.

### Version 11 — 2026-07-31

§ 18 bekommt die Abgrenzung, die ihm gefehlt hat: **wann ein Befund ins Verstoßprotokoll gehört und
wann in den Ticket-Verlauf.** Drei Fragen (Kodex-Bezug, Wirksamkeit, schon vermerkte Schuld), die
Zweifelsregel zugunsten des Protokolls, und die Regel „ein Sachverhalt, ein Eintrag". Dazu ein
`Konkret verboten`-Teil — der Paragraph hatte keinen, und nach der Leseanleitung ist er ohne diesen
Teil Dekoration.

**Grund.** Die Lücke war nicht theoretisch. Der erste Verstoß dieses Projekts (V-001, falsche
Anonymitätszusagen auf der öffentlichen Instanz) lag als Notiz in einem Ticket-Verlauf, während das
Verstoßprotokoll leer blieb — bemerkt hat das erst EIP-T-058, und zwar nicht aus einer Regel
heraus, sondern weil jemand hinsah. Ohne geschriebene Grenze fällt die Entscheidung im Einzelfall,
und sie fällt vorhersehbar: Der Ticket-Verlauf ist die bequemere Ablage, weil ihn nur wir lesen.
Genau die Asymmetrie, gegen die § 18 Satz 2 geschrieben ist.

Die zweite Frage (Wirksamkeit) zieht die Grenze bewusst am ausgelieferten Stand und nicht an der
Schwere: „stand eine Stunde auf der öffentlichen Instanz" ist ein Verstoß, „im Arbeitsbaum gebaut und
dort behoben" ist es nicht. Das ist prüfbar, während „wie schlimm war es" es nicht ist. Die dritte
Frage hält Schuldenübersicht und Protokoll auseinander: Eine bewusst vermerkte, noch nicht fällige
Lücke ist kein Verstoß — eine gerissene Fälligkeit schon (so schon im Abschnitt Betriebsstufen).

**Die Zahl ändert sich nicht: 11 von 20, Grenze 8, der Baustopp gilt weiter.** § 18 stand und steht
`bindend`; die Änderung schärft ihn, ohne eine Schuld zu tilgen oder zu erzeugen. Zulässig unter
§ 4 b als Arbeit, die einen Verstoß dokumentiert und seine Wiederholung erschwert.

**Nachtrag, gleiche Version.** Der § 20-Statuspunkt in der Schuldenübersicht führte bis hierhin eine
Momentaufnahme („erfüllt, Deploy `c3c3a5e`"). Beim Ausliefern dieser Version fiel auf, dass der Satz
damit **bei jeder Kodex-Änderung für die Dauer des Deploys falsch** ist und danach von Hand
nachgezogen werden müsste — ein Vermerk, der seine eigene Pflege verlangt, ist genau der Drift, den
EIP-T-074 beheben soll. Der Punkt sagt jetzt die Regel statt des Standes. Keine Regeländerung,
deshalb keine neue Version; hier vermerkt, damit sie nicht still geschieht (§ 17).

**Zweiter Nachtrag, gleiche Version (EIP-T-075).** § 1 sagte an drei Stellen sinngemäß, was Renders
Loadbalancer und TLS-Endpunkt protokollieren, sei „ungeprüft" und eine Auskunft stehe aus. Die
Auswertung der öffentlichen Unterlagen von Render und Cloudflare am Nachmittag des 2026-07-31 zeigt,
dass das den Stand zu unseren Gunsten beschreibt: Renders Auftragsverarbeitungsvereinbarung — die
über die Terms of Service auch im Gratis-Tarif ohne Zutun gilt — sagt in Exhibit C „comprehensive
and centralized logging and monitoring of our products and infrastructure" zu und lässt die
Aufbewahrungsdauer in Exhibit A offen. Cloudflare ist benannter Subprozessor, durch dessen Netz
jeder Request läuft, und wir sind dort nicht Zoneninhaber.

**Dass protokolliert wird, ist damit belegt; unbekannt sind nur noch Umfang und Frist.** § 1 sagt
aber nicht „nicht verkettbar", sondern „fällt nicht an" — der Vermerk stand also vor einer
Wissenslücke und steht jetzt vor einem benannten Widerspruch. Die Formulierungen in § 1, im
Betriebsstufen-Abschnitt und in der Schuldenübersicht sind entsprechend nachgezogen, ebenso
`EIP-RPT-20260731-002` § 1.5.1 und § 4.

Keine Regeländerung und keine neue Version: § 1 bleibt Wort für Wort stehen, sein Status bleibt
`Disziplin`, die Zahl bleibt 11 von 20 und der Baustopp gilt weiter. Vermerkt wird es hier, weil ein
Kodex, der eine Belastung milder beschreibt als sie ist, nach § 4 selbst das Problem wäre — und weil
eine stille Korrektur genau der Vorgang ist, gegen den § 17 geschrieben ist. Die Grenze ist am selben
Tag auch auf `/transparenz` benannt worden; sie nur intern zu führen, wäre § 10 mit umgekehrtem
Vorzeichen.

### Version 10 — 2026-07-31

§ 10 ist vollständig `bindend`. Der Paragraph stand seit Version 1 mit drei offenen Punkten da —
Frist, Format und der Weg, auf dem Kodex und Verstoßprotokoll überhaupt nach außen gelangen. Der
dritte war der schwerste: Ein Verstoßprotokoll, das in einer Datei neben dem Ticketordner liegt,
erfüllt keine Offenlegungspflicht. Es dokumentiert nur für uns, und § 18 ist gerade gegen diese
Asymmetrie geschrieben.

**Was jetzt gilt.** Frist: sieben Tage ab *Kenntnis*, nicht ab Behebung — sonst verschweigt ein
langwieriger Fix den Fehler ebenso lange. Format: der Eintrag im Verstoßprotokoll selbst, mit
Sachverhalt, berührten Paragraphen, betroffenen Ergebnissen (auch: keinen), Zeitraum und Folge. Kein
zweites Format daneben. Weg: `/kodex`, `/kodex/protokoll` und `/transparenz` auf der öffentlichen
Instanz, ohne Anmeldung erreichbar, erzeugt aus den maßgeblichen Dateien durch
`scripts/sync_public_docs.py` — eine handgepflegte Zweitfassung wäre nach § 20 selbst ein Verstoß,
und genau dieser Drift ist mit dem Manifest schon einmal passiert (EIP-T-044).

§ 5 wird im Gegenzug **belastet**. Der Transparenzbericht ist damit veröffentlicht — beginnend beim
Nullfall, samt monatlichem Vermerk, dass keine Anordnung mit Schweigegebot vorliegt. Der
Eingangskanal aber fehlt: Anfragen sollen an eine eigene, ausschließlich dafür bestimmte Adresse
gehen, die es ohne Domain nicht gibt. Die naheliegende Abkürzung — eine private Adresse dauerhaft
öffentlich an das Projekt binden — ist verworfen worden (Betreiberentscheidung, EIP-T-063). Der
Bericht sagt deshalb, dass eine Behörde das Projekt nur über den Betreiber persönlich erreicht.
Ehrlich, aber nicht erfüllt: → EIP-T-073, fällig ab `produktiv`.

**Die Zahl ändert sich nicht: 11 von 20, Grenze 8, der Baustopp gilt weiter.** § 10 geht, § 5 kommt.
Das ist kein Rechentrick, sondern der ehrliche Stand — gebaut wurde ein Weg nach außen, nicht ein
Kanal nach innen. Die Umsetzung war unter § 4 b zulässig: Sie trägt eine Schuld ab und behebt eine
gerissene Fälligkeit.

**Nebenwirkung, positiv.** Mit dem Weg hat sich der letzte offene Punkt aus V-001 (siehe unten)
geschlossen und damit der Verstoß insgesamt — ausgeliefert und gegen die Instanz geprüft am
2026-07-31, `ad45d76`. An der Betriebsstufe `öffentlich erreichbar` bleibt damit nur noch § 1
gerissen (V-002, EIP-T-041).

### Version 9 — 2026-07-31

§ 4: Die Ballot-Stuffing-Schuld ist **zeitlich halbiert, nicht getilgt**
(EIP-T-069). Bisher gab es einen globalen
Token-Signaturschlüssel, der nie verschwand; damit konnte der Betreiber jederzeit und für jede
Umfrage gültige Token nachproduzieren, auch Jahre später. Jetzt bekommt jede Umfrage beim Anlegen
ihr eigenes Schlüsselpaar, der private Teil wird beim Schließen vernichtet (überschreiben, löschen,
`VACUUM` — derselbe Weg wie beim Umfrage-Schlüssel aus § 2), der öffentliche steht im
POLL_OPEN-Eintrag des Boards und überlebt dort.

Zwei Wirkungen: Ein Token aus Umfrage A ist in Umfrage B strukturell wertlos, weil die Signatur
dort nicht gilt. Und nach dem Schließen ist die Auszählung eingefroren — auch ein kompromittierter
oder böswilliger Betreiber mit der Datenbank in der Hand kann kein gültiges Token mehr herstellen.

**Was das nicht auflöst.** Während eine Umfrage *läuft*, liegt ihr Signaturschlüssel weiterhin
allein bei uns, und genau dann findet Stuffing statt. Die Schuld bleibt also bestehen und ihr
Ticket (EIP-T-040) auch; verengt ist nur ihr Zeitraum. Der Vermerk in § 4 und die
Schuldenübersicht sagen das jetzt so. **Die Zahl ändert sich nicht: 11 von 20, Grenze 8, der
Baustopp gilt weiter.** Die Umsetzung war unter § 4 b zulässig (sie trägt an einer Schuld ab).

Nebenwirkung auf § 7, in dieselbe Richtung: Der Schlüssel, gegen den geprüft wird, liegt jetzt
unter der Merkle-Wurzel statt daneben in der Datenbank. Ein nachträglicher Tausch bricht die Kette,
und `--pubkey` ersetzt den Schlüssel im Prüfwerkzeug nicht mehr, sondern wird dagegen gehalten.

Formatbruch, angekündigt wie beim letzten Mal: POLL_OPEN trägt ein neues Pflichtfeld `pubkey`.
Datenbanken ohne dieses Feld werden beim Start mit Anleitung abgewiesen — ihre Boards wären nach
der Vernichtung des globalen Schlüssels nicht mehr prüfbar. Ältere Board-Exporte sind mit dem
neuen Prüfer nicht mehr lesbar.

### Version 8 — 2026-07-31

§ 2: Baustein F aus EIP-T-033 (Sitzungstrennung der Abstimm-Route) ist umgesetzt, der Vermerk
entsprechend verengt. Konkret: Der Client gibt die Stimme ohne Cookie, Auth-Header und Referrer ab
(`credentials: "omit"`, `referrerPolicy: "no-referrer"` in `ballot.js`); der Server meldet
trotzdem mitgesandten Sitzungskontext als Befund ins Debug-Modul, statt ihn still zu empfangen
(bewusst keine Abweisung — die Verkettung ist mit dem Empfang passiert, eine Abweisung kostete nur
die Stimme); und `/api/token` wie `/api/vote` antworten nie schneller als der Antwort-Floor
(`EIDPOLL_ANTWORT_FLOOR_S`, Voreinstellung 0,3 s), damit die Bearbeitungsdauer keine Auskunft gibt.

**Was das nicht auflöst.** § 2 bleibt belastet, die Zahl ändert sich nicht: **11 von 20, Grenze 8,
der Baustopp gilt weiter.** Offen sind die Speichertrennung (Baustein G) und ein bei der Umsetzung
festgehaltener Nebenbefund: Die Token-Suche auf `/verify` nimmt das Token als GET-Parameter
entgegen, während der Browser das Session-Cookie an dieselbe Route mitschickt — wer angemeldet
seine Stimme prüft, liefert dem Server Pseudonym und Token in einem Request. Beides in EIP-T-033
geführt. Ehrlich dazu: Der Floor ist ein Floor, keine Konstante, und gegen IP-/Zeitkorrelation auf
Netzwerkebene hilft die Sitzungstrennung nicht (→ EIP-T-034). Die Umsetzung war unter § 4 b
zulässig (sie trägt eine Schuld ab).

### Version 7 — 2026-07-31

§ 2: Der Vermerk „Zeitauflösung, Batch-Größe, Mindest-Anonymitätsmenge offen" ist aufgelöst. Die
Parameter sind mit EIP-ADR-20260728-001 (angenommen 2026-07-31, Kursabgleich
EIP-AUD-20260731-001) entschieden und im Code umgesetzt: Merkle-Set pro Batch mit verketteten
Roots, Sortierung nach Blatt-Hash, k = 10, Zeitdeckel 6 h, bei Schließung sofort. Die Sortierung
in Eingangsreihenfolge ist aus allen Tabellen entfernt (`WITHOUT ROWID`, Blatt-Hash statt Index),
die laufende Nummer im `TOKEN_ISSUED`-Payload durch einen Zufalls-Nonce ersetzt. Neu ist der
signierte Inklusionsbeleg (eigener Ed25519-Schlüssel): Die individuelle Verifizierbarkeit heißt
jetzt „sofort beweisbar gebunden, öffentlich sichtbar mit dem nächsten Batch" — der Wortlaut steht
in Beleg, Board-Seite und `DOKU.md`.

**Was das nicht auflöst.** § 2 bleibt teilbelastet: Sitzungs- und Speichertrennung der
Abstimm-Route (Bausteine F und G aus EIP-T-033) sind offen — der Sitzungscookie läuft weiterhin an
die Abstimm-Route mit, und beide Ledger liegen in derselben Datenbank. Die Zahl der belasteten
Paragraphen ändert sich nicht: **11 von 20, Grenze 8, der Baustopp gilt weiter.** Die Umsetzung
selbst war unter § 4 b zulässig (sie trägt eine Schuld ab und ist Sicherheitsarbeit).

Ehrlich vermerkt in § 2: k zählt Board-Einträge, nicht Personen — im Ein-Klick-Flow entstehen je
Teilnahme zwei Einträge, die wirksame Anonymitätsmenge ist also etwa k/2. Ob 10 der richtige Wert
ist, klärt EIP-T-072 (Timing-Simulation).

Formatbruch wie in der ADR angekündigt: Datenbanken im alten Ketten-Format werden beim Start mit
Anleitung abgewiesen; die lokale Vorführdatenbank wurde verworfen (umbenannt auf
`eidpoll.sqlite3.kettenformat-verworfen`). Bestehende Board-Exporte sind mit dem neuen Prüfer
nicht mehr lesbar.

### Version 6 — 2026-07-29

§ 9 neu gefasst. Die Regel „jede Aussage wird als untere Schranke formuliert" ist ersetzt durch die
Pflicht, Stimmanzahl und Nenner im selben Satz zu nennen, mit ausformuliertem Beispielsatz. Die
Zitierbedingung für Dritte ist **gestrichen**, nicht erfüllt. Der § 9-Vermerk verschwindet damit aus
der Schuldenübersicht: 12 → 11 belastete Paragraphen. Prüfliste Punkt 4 nachgezogen.

**Grund, erster Teil: das Fachwort.** „Untere Schranke" ist die korrekte Bezeichnung und die falsche
Formulierung. Der Kodex verlangte damit einen Satz, den die Adressaten nicht verstehen, um eine
Aussage zu vermeiden, die sie sofort verstehen würden. Die Zahlen leisten dasselbe ohne Vokabel: Wer
„1,2 Mio. von 61 Mio. Wahlberechtigten" liest, kann daraus nicht „Deutschland sagt X" machen, ohne
selbst zu lügen. Der Schutz lag nie im Begriff, sondern im mitgeführten Nenner — und der steht
ohnehin schon in § 8. § 9 regelt jetzt nur noch die Satzform, in der beide Zahlen auftreten.

**Grund, zweiter Teil: die Zitierbedingung.** Sie war der einzige Teil des Kodex, der Dritte binden
sollte, und sie konnte das nie. Eine Beteiligungszahl ist kein geschütztes Werk; ein Zitat durch
Presse oder Politik entsteht ohne Nutzungsverhältnis, an das eine Bedingung anknüpfen könnte.
Durchsetzbar wäre nur gewesen, wer etwas von uns bezieht — Widget oder API —, und dafür gibt es
weiterhin § 16. Der Satz behauptete also eine Bindung, die weder bestand noch herstellbar war: genau
der Fall, den § 4 verbietet („nicht können" als „nicht tun" ausgeben, hier umgekehrt). Ein Vermerk,
der auf ein unerreichbares Ziel zeigt, ist keine Schuld, sondern ein Fehler im Kodex.

**Was die Änderung nicht tut.** Kein Verbot ist entfallen. „Repräsentativ", Hochrechnungen,
Gewichtungen, Prozent ohne absolute Zahl, ausblendbare Quote im Widget — alles unverändert verboten,
die Liste ist um den Prozent-Fall sogar länger geworden. Auch die Geltung ab Betriebsstufe
`öffentlich erreichbar` bleibt. Neu ist nur ein ausdrücklicher Abschnitt **„Nicht verboten"**: dass
Dritte anders formulieren. Das war vorher nicht erlaubt und wurde trotzdem nicht durchgesetzt — der
schlechteste der drei möglichen Zustände.

**Die Gegenposition, damit sie nachlesbar ist.** Erfahrungsgemäß wird eine solche Zahl von Dritten
zur Prozentaussage umformuliert, und § 9 alt war der Versuch, dem etwas entgegenzusetzen. Die
Entscheidung des Betreibers lautet, das hinzunehmen: Wer umformuliert, verantwortet es selbst,
solange unsere eigene Darstellung den Nenner mitführt. Wer diese Abwägung später anders trifft,
ändert den Paragraphen — er braucht dafür keine neuen Argumente, sondern nur einen Weg, die Bedingung
tatsächlich durchzusetzen.

**Offen bleibt § 16** (kein Einsatz in bindenden Abstimmungen, Durchsetzung gegenüber Einbettern) →
EIP-T-062, fällig vor der ersten Einbettung durch
Dritte. Das ist keine Sprachfrage und wird von dieser Änderung nicht berührt. Der genaue Wortlaut der
Ergebnisdarstellung → EIP-T-028.

Die Änderung trägt eine Schuld ab und ist unter § 4 b zulässig. Der Baustopp gilt weiter: 11 von 20
bei einer Grenze von 8.

### Version 5 — 2026-07-29

Kein Paragraph inhaltlich geändert. Umbau der Form: Vorrangregel, Betriebsstufen und Prüfliste stehen
jetzt als **Leitfaden** vorn statt verteilt über das Dokument. Änderungs- und Verstoßprotokoll in
diese Datei ausgelagert. Die Begründungsteile („Warum") auf zwei Sätze gekürzt, wo sie zu Essays
angewachsen waren — am deutlichsten bei § 4, dessen zweiter Begründungsabsatz den Eintrag zu
Version 3 wortgleich wiederholte und deshalb nur noch hier steht.

**Grund.** Der Kodex war auf 714 Zeilen gewachsen, davon 188 Zeilen Historie und 381 Zeilen
Paragraphen bei durchschnittlich 19 Zeilen je Regel. Was man bei einer Entscheidung tatsächlich
heranzieht — Vorrangregel und Stoppfragen — waren darin etwa 30 Zeilen, und sie standen am Anfang
und am Ende. Ein Prüfmaßstab, den man erst durchsuchen muss, wird nicht geprüft, sondern erinnert;
und erinnert wird das, was ohnehin gerade passt.

Der Umfang hatte bereits einen messbaren Effekt: Die Schuldenübersicht sagte „12 von 20", während
`CLAUDE.md` an anderer Stelle „13 von 20" führte. Je mehr Stellen dasselbe sagen, desto mehr Stellen
sagen es irgendwann verschieden.

Was die Änderung **nicht** tut: eine Regel abschwächen. Kein Verbot, kein Status und keine Fälligkeit
ist entfallen; die Schuldenübersicht ist unverändert, die Grenze aus § 4 b steht weiter bei acht und
ist weiter überschritten. § 17 verlangt für eine Kürzung dieselbe Begründung wie für eine
Verschärfung, deshalb dieser Eintrag. Wer prüfen will, ob hier still etwas verschwunden ist, hat den
Diff — genau dafür verlangt § 17 ihn.

Die Kürzung selbst trägt keine Schuld ab und ist unter § 4 b nur als Dokumentation zulässig. Sie
wurde einmalig gemacht und ist kein Anlass, den Kodex weiter zu bearbeiten, solange der Baustopp
gilt.

### Version 4 — 2026-07-29

§ 5 von `offen` auf `bindend`. Das Verfahren liegt als
EIP-RFC-20260729-001 vor (EIP-T-060). Schuldenübersicht von 13
auf 12 belastete Paragraphen. Sonst unverändert.

**Grund.** § 5 war der Vermerk, dessen Fälligkeit am spätesten eintritt und der deshalb am längsten
folgenlos stehen konnte — und zugleich der, bei dem ein `offen` am teuersten ist: Der Paragraph
verlangt selbst, dass die Antwort *vor* der ersten Anfrage feststeht. Ein offener Vermerk verschiebt
die Arbeit genau in den Moment, für den sie nicht gedacht ist.

Drei Setzungen des Verfahrens gehen über das hinaus, was der Paragraph verlangt, und sind deshalb
hier festgehalten. Erstens eine Klasse von Positionen, die **in keiner Lage** herausgegeben werden:
der Token-Signaturschlüssel, jede Anordnung zur Änderung des ausgelieferten Clients, jede
prospektive Protokollierung, jede Verknüpfung der beiden Register. Diese vier nehmen nicht einzelnen
Teilnehmenden ihre Vertraulichkeit, sondern allen die Aussage des Verfahrens. Zweitens die
Veröffentlichung des Nullfalls: Ein Bericht, der erst mit der ersten Anfrage entsteht, verrät durch
sein Erscheinen, was ein Schweigegebot gerade verbietet. Drittens der monatlich neu datierte
Negativ-Vermerk für den Fall einer Anordnung, über die nicht gesprochen werden darf — rechtlich
ungeklärt, im Dokument als ungeklärt benannt, und trotzdem gewählt, weil die Alternative den einzigen
Zeitraum unsichtbar lässt, auf den es ankommt.

Was die Änderung **nicht** tut: eine neue Schuld eröffnen. Dass Eingangskanal und Transparenzbericht
von außen noch nicht erreichbar sind, ist der Offenlegungsweg aus § 10 und dort seit Version 3
geführt (EIP-T-063, gerissen). Ein zweiter Vermerk unter § 5 hätte die Zahl in der Übersicht erhöht,
ohne dass mehr offen wäre — die Übersicht soll den Bestand zeigen, nicht die Zahl der Erwähnungen.
Der Betriebsstufe nach ändert sich nichts: § 5 wird an `öffentlich erreichbar` nicht fällig, sondern
war es erst mit dem Berechtigungszertifikat. Er wird trotzdem jetzt eingelöst, weil eine Schuld
abzutragen unter § 4 b die einzige Arbeit ist, die noch zulässig ist.

### Version 3 — 2026-07-28

§ 4 um Fälligkeitspflicht (a) und Schuldengrenze (b) erweitert. Betriebsstufen als eigener Abschnitt
eingeführt. Alle bestehenden `offen`- und `Disziplin`-Vermerke rückwirkend auf Ticket und Ereignis
nachgezogen. Schuldenübersicht angelegt. Prüfliste um Stoppfrage 7 und Begleitfrage 10 erweitert.

**Grund.** Eine Bilanzprüfung von Kodex, Manifest und Ticketstand (EIP-T-057) hat ergeben: Das
Projekt löst seine Zusagen überwiegend textlich ein statt technisch — nicht durch Regelbruch, sondern
durch eine Lücke in der Regel. § 4 verlangte, eine nicht erzwingbare Zusage als Disziplin zu
kennzeichnen, nannte das eine Schuld, stellte sie aber nie fällig: keine Frist, kein auflösendes
Ticket, keine Obergrenze. Damit war „Text an den Ist-Zustand angleichen" regelkonform. Über die
letzten 25 Tickets hinweg war jedes erledigte ein Text-, Oberflächen- oder Werkzeugticket und jedes
technisch einlösende offen. Die Grenze in § 4 b ist die einzige Maßnahme, die den Durchsatz umlenkt
statt ihn zu protokollieren — sie ist absichtlich unbequem.

Der zweite Befund betrifft die Fälligkeitstermine, die es gab: Sie zeigten alle auf denselben nie
eingetretenen Moment („vor dem ersten echten Durchlauf"), während seit dem 2026-07-27 eine
öffentliche Instanz läuft. Der Kodex kannte diesen Zustand nicht und unterschied nur lokal und
produktiv. Damit war der tatsächliche Betriebszustand der einzige ohne jede Fälligkeit. V-001
Punkt 3 hatte dieselbe Lücke von der anderen Seite getroffen: Kein Satz verlangte, dass eine als
erledigt geführte Korrektur die öffentliche Instanz auch erreicht.

Die Änderung ist verschärfend, nicht klärend. Eine Fassung, die den Ist-Zustand nur besser
beschrieben hätte, wäre genau der Fehler gewesen, gegen den EIP-T-057 geschrieben ist. Die Grenze in
§ 4 b ist beim Inkrafttreten bereits überschritten (13 von 20 Paragraphen bei einer Grenze von 8);
das ist beabsichtigt und die Probe darauf, dass die Zahl nicht am Ist-Zustand entlang gewählt wurde.
Die neue Betriebsstufe hat zugleich einen bis dahin unerkannten Verstoß sichtbar gemacht (V-002).

### Version 2 — 2026-07-27

§ 20 ergänzt (offener Code, nachprüfbarer Build). Grund: Das [Manifest](/manifest) sagt öffentlich zu, den
Code zu veröffentlichen — als einzige Zusage ohne Paragraphen, an dem sie scheitern kann. Der
Auslöser war die Angleichung des Manifests an diesen Kodex, bei der die Lücke sichtbar wurde. Der
Paragraph geht über die Manifest-Zusage hinaus: Weil das Blinding im Client läuft, ist offener Code
ohne reproduzierbaren Build keine überprüfbare Aussage über die tatsächlich benutzte Seite. § 4
verweist für seine offene Schuld „reproduzierbarer Build" jetzt dorthin.

Prüfliste umgestellt: Die neue § 20-Frage war als einzige invertiert — ein „nein" wäre das
Stoppsignal gewesen, während bei allen anderen das „ja" stoppt. Statt die Ausnahme zu erklären,
ist die Liste jetzt in Stoppfragen (1–6, alle gleich gepolt) und Begleitfragen (7–8) geteilt. Die
§ 20-Frage ist entsprechend umformuliert. Inhaltlich unverändert gegenüber Version 1, außer der
Ergänzung.

### Version 1 — 2026-07-26

Kodex angelegt. Werte und Zusagen aus dem [Manifest](/manifest) in prüfbare Regeln überführt, ergänzt um die
bis dahin ungeregelten Bereiche: Metadaten und Logs (§ 1), Zeitkorrelation (§ 2), Präregistrierung (§ 7),
Fehleroffenlegung (§ 10), Behördenanfragen (§ 5), DSGVO-Kollision (§ 6), Geld und Unabhängigkeit (§ 13),
Nachfolge (§ 14). Vorrangregel gesetzt mit Reichweite an letzter Stelle.

---

## Verstoßprotokoll

### V-001 — Falsche Anonymitätszusagen auf der öffentlichen Vorführinstanz
**Datum des Eintrags:** 2026-07-28 · **Paragraphen:** § 4, § 9, § 10, § 18 ·
**Ticket:** EIP-T-058 · **Status:** **behoben am 2026-07-28**, Offenlegung nach § 10 steht aus

**Was geschah.** Die öffentliche Instanz <https://eid-poll.onrender.com> trägt seit dem Deploy am
2026-07-27 vier Aussagen, die mehr behaupten, als das Verfahren hält:

| Ort | Aussage | Warum falsch |
|---|---|---|
| Startseite | „Solange eine Umfrage läuft, sieht niemand die Verteilung der Stimmen — auch der Betreiber nicht." | `tally()` verweigert das Ergebnis vor Umfrage-Ende, aber `/board/{id}` und `/api/board/{id}` geben die Einträge samt gewählter Option im Klartext heraus. Jeder Besucher zählt den Zwischenstand aus. Nicht nach § 4 ungenau, sondern unwahr |
| Startseite | „Wer wie gestimmt hat, kann niemand sehen." | Für den Betreiber im Moment der Abgabe nicht haltbar; § 4 verlangt hier die Kennzeichnung als Selbstbindung |
| `/verify` | „…ohne dass jemand anderes erfährt, dass die Stimme dir gehört." | Der Lookup läuft über den Server und gibt genau diese Zuordnung preis. Die Aussage beschreibt das Gegenteil dessen, was die Funktion tut |
| `/board` | „Jede Stimme von einer berechtigten Person" | Die Signaturprüfung deckt nicht ab, dass der Betreiber sich selbst Tokens signiert (§ 4, Ballot Stuffing) |

**Wie es dazu kam.** Alle vier Stellen wurden mit EIP-T-042 am 2026-07-28 korrigiert. Die Korrektur
liegt im lokalen Arbeitsbaum und ist nicht veröffentlicht: `origin/prototype` — der Stand, den Render
ausliefert — steht zwei Commits zurück und enthält keine der Änderungen. Das Ticket wurde mit
abgehakten Kriterien nach `done/` gelegt. Am 2026-07-28 gegen die laufende Instanz nachgeprüft: alle
vier Sätze stehen weiterhin live.

**Was daraus folgt.**

1. Der Eintrag steht hier, bevor die Korrektur ausgeliefert ist — § 18 verlangt die Dokumentation
   unabhängig davon, ob sie jemand von außen bemerkt hätte.
2. Die Auslieferung ist die eigentliche Behebung und noch offen (EIP-T-058).
3. Der Befund ist nicht durch einen Paragraphen gedeckt gewesen: Kein Satz dieses Kodex verlangt, dass
   eine als erledigt geführte Textkorrektur die öffentliche Instanz auch erreicht. § 20 greift nicht —
   ausgelieferter und veröffentlichter Stand *stimmen* überein, beide sind der alte. Die Lücke ist
   Gegenstand von EIP-T-057.
4. Offenlegung nach § 10 steht aus. Dieses Protokoll liegt in einer Datei außerhalb des öffentlichen
   Repositorys; ein Eintrag hier erfüllt die Offenlegungspflicht nicht. Auch das gehört zu EIP-T-057.

**Nachtrag 2026-07-28 (Version 3).** Punkt 3 ist geschlossen: Die Betriebsstufe `öffentlich
erreichbar` existiert jetzt, und § 20 wird an ihr fällig. Der Befund ist damit nachträglich von einem
Paragraphen gedeckt. Punkt 4 ist nicht geschlossen, sondern in EIP-T-063 überführt und als eigene
Fälligkeit von § 10 geführt — ebenfalls gerissen.

**Behebung 2026-07-28.** Der korrigierte Stand ist ausgeliefert: `517a273..c63dd06` nach
`origin/prototype`, Commit `2c801cc` trägt die Textkorrekturen. Gegen die laufende Instanz
nachgeprüft — gegen die Instanz, nicht gegen den Arbeitsbaum, denn das Prüfen am falschen Ort war der
ursprüngliche Fehler:

| Stelle | Stand nach dem Deploy |
|---|---|
| Startseite, „auch der Betreiber nicht" | ersetzt; die Auszählbarkeit über `/board` wird jetzt benannt |
| Startseite, „Wer wie gestimmt hat, kann niemand sehen" | ersetzt, mit Verweis auf das Manifest |
| `/verify`, „ohne dass jemand anderes erfährt…" | ersetzt; die Seite warnt jetzt, dass der Lookup über den Server läuft, und nennt den Weg ohne uns |
| `/board`, „Jede Stimme von einer berechtigten Person" | ersetzt durch „trägt eine gültige Berechtigung", mit Absatz zum Ballot Stuffing |
| `/poll`, „Warum kann mir meine Stimme niemand zuordnen?" | ersetzt durch „Wer kann meine Stimme mir zuordnen?", mit § 4-Kennzeichnung |

Die Aussagen sind damit in Übereinstimmung mit § 4 und § 9. **Offen bleibt Punkt 4**: Die Offenlegung
nach § 10 ist nicht erfolgt, weil dieses Protokoll weiterhin außerhalb des öffentlichen Repositorys
liegt → EIP-T-063. Der Verstoß ist behoben, seine Offenlegung nicht.

**Nachtrag 2026-07-31 (Version 10) — Punkt 4, Offenlegung.** Der Weg nach außen ist gebaut: Kodex,
dieses Protokoll und der Transparenzbericht laufen als abgeleitete Kopien im App-Repo mit
(`scripts/sync_public_docs.py`) und werden unter `/kodex`, `/kodex/protokoll` und `/transparenz`
ohne Anmeldung ausgeliefert. Wer diesen Absatz auf der öffentlichen Instanz liest, liest damit die
Offenlegung des Verstoßes, um dessentwillen der Weg entstanden ist.

**Ausgeliefert 2026-07-31.** `c63dd06..ad45d76` nach `origin/prototype`. Gegen die laufende Instanz
nachgeprüft — gegen die Instanz, nicht gegen den Arbeitsbaum:

| Seite | Befund |
|---|---|
| `/kodex` | 200, Version 10, Schuldenübersicht sichtbar, § 10 als erfüllt ausgewiesen |
| `/kodex/protokoll` | 200, V-001 und V-002 im Wortlaut, dieser Nachtrag eingeschlossen |
| `/transparenz` | 200, Nullfall und Negativ-Vermerk |
| `/manifest` | 200, unverändert erreichbar |
| Startseite | Navigationspunkt **Kodex** vorhanden |
| alle vier | ohne Anmeldung erreichbar, keine unaufgelösten Wikilinks |

**V-001 ist damit vollständig geschlossen** — Behebung am 2026-07-28, Offenlegung am 2026-07-31. An
der Betriebsstufe `öffentlich erreichbar` bleibt allein § 1 gerissen (V-002, EIP-T-041).

**Nachtrag 2026-08-01: dieselbe Aussage stand noch in drei weiteren Dateien.** Kein Paragraph ändert
sich dadurch, deshalb keine neue Kodex-Version — nur das Verstoßprotokoll wächst (§ 18).
(EIP-T-083)

Die erste Zeile der Tabelle oben — „niemand sieht die Verteilung" — wurde am 2026-07-28 dort
korrigiert, wo sie aufgefallen war: auf der Startseite. Nicht korrigiert wurde sie in `DEPLOY.md`
(„Nur der Teilnahmezähler ist sichtbar, kein Zwischenstand (§7)"), in `README.md` („ist nur der
Teilnahmezähler sichtbar (§7)") und in `DOKU.md`, wo sie am weitesten ging: Dort bekam die
Anzeigesperre eine Schutzbegründung („Zwischenstände beeinflussen laufende Abstimmungen und erlauben
Timing-Rückschlüsse") und wurde damit vom Verhalten der Oberfläche zur Eigenschaft des Verfahrens
befördert. Alle drei Dateien liegen im öffentlichen Repository. Alle drei riefen § 7 als Beleg auf,
der das nicht deckt: § 7 regelt, was *wir* veröffentlichen, nicht, was sich aus dem Board ablesen
lässt.

**Wie es dazu kam.** V-001 wurde als Befund über *die Instanz* geführt und an den Seiten geprüft,
die sie ausliefert. Die Betriebsdokumente wurden nicht mitgelesen, obwohl sie seit demselben Deploy
öffentlich sind. Die Nachprüfung am 2026-07-31 lief gegen die laufende Instanz — richtig gegen den
damaligen Befund, aber blind für denselben Satz in einer Datei, die keine Route hat.

**Was daraus folgt.**

1. Der Eintrag steht als Nachtrag zu V-001 und nicht als V-005. Es ist derselbe Verstoß in einer
   Datei, die beim Aufräumen übersehen wurde — eine neue Nummer würde eine unvollständige Behebung
   als neuen Befund ausgeben und die Lücke zwischen beiden verdecken.
2. Eine Textkorrektur ist erst dann erledigt, wenn nach der Aussage gesucht wurde und nicht nach der
   Stelle. Bei V-001 war es der umgekehrte Fall: vier bekannte Stellen abgearbeitet, nie `grep` auf
   die Behauptung.
3. Die Sache dahinter bleibt offen und wird hier nicht mitentschieden: ob der Zwischenstand
   überhaupt verborgen sein soll (EIP-T-056). Dieser
   Nachtrag stellt nur her, dass die Dokumente den heutigen Zustand beschreiben.
4. Die Batch-Veröffentlichung (k = 10, 6 h) verzögert den ablesbaren Stand. Sie darf dafür nicht in
   Anspruch genommen werden — sie ist gegen Verkettung gebaut, und ein Nebeneffekt als Schutz
   ausgegeben ist genau die Bewegung, die § 4 verbietet.

### V-002 — Vollständige IP-Adressen im Zugriffslog der öffentlichen Instanz
**Datum des Eintrags:** 2026-07-28 · **Paragraphen:** § 1, § 4, § 18 ·
**Ticket:** EIP-T-041 · **Status:** behoben, Wirksamkeit auf der Instanz bestätigt am 2026-07-31
(siehe Nachtrag unten). Der uvicorn-Zugriffslog war der Gegenstand dieses Verstoßes; was Render
darüber hinaus protokolliert, ist offen und gehört weiter zu EIP-T-041

**Was geschah.** Die öffentliche Instanz startet uvicorn ohne `--no-access-log` und mit
`--proxy-headers --forwarded-allow-ips='*'` (`render.yaml`, `Dockerfile`). Uvicorn schreibt damit für
jede Anfrage eine Zugriffszeile mit der **echten** Client-IP nach stdout — die Proxy-Header-Option
sorgt gerade dafür, dass dort nicht die IP des Render-Proxys steht, sondern die des Besuchers. Render
sammelt stdout in seiner Log-Ansicht. § 1 verbietet unter „Konkret verboten" ausdrücklich
*„Vollständige IP-Adressen in Zugriffs- oder Anwendungslogs"*.

Betroffen ist jede Anfrage an <https://eid-poll.onrender.com> seit dem Deploy am 2026-07-27,
einschließlich der Aufrufe von `/board` und der Stimmabgabe. In Verbindung mit den Zeitstempeln des
Boards ist das zusätzlich ein Nebenkanal im Sinne von § 2, auch wenn auf dieser Instanz keine echten
Stimmen liegen.

**Wie es dazu kam.** § 1 stand seit Version 1 auf `bindend` mit dem Zusatz, die Umsetzung im Betrieb
sei bis auf Weiteres `Disziplin`. Ein Fälligkeitsereignis nannte der Vermerk nicht, und die einzigen
Termine im Kodex zeigten auf den Produktivbetrieb. Der Deploy einer öffentlichen Vorführinstanz war
damit kein Anlass, die Zusage einzulösen — der Kodex kannte diesen Zustand nicht. Sichtbar wurde der
Befund erst durch die Betriebsstufen aus Version 3, also durch dieselbe Änderung, die ihn zum
Verstoß macht.

**Was daraus folgt.**

1. Der Verstoß bestand schon vor Version 3; neu ist nur, dass ein Paragraph ihn erfasst. Er wird
   deshalb ab dem Deploy-Datum gezählt, nicht ab heute — § 17 verbietet, einen Paragraphen
   rückwirkend an eine getroffene Entscheidung anzupassen, und dasselbe gilt umgekehrt für das
   Kleinrechnen eines Befunds.
2. Behebung über EIP-T-041: `--no-access-log` im Startbefehl, ersatzweise ein Log-Format ohne IP,
   und eine Prüfung der Aufbewahrung auf Render-Seite. Die Angabe `--proxy-headers` bleibt nötig,
   damit die App HTTPS erkennt.
3. Solange nicht behoben, ist die Aussage der Datensparsamkeit gegenüber Besuchern der Instanz nicht
   haltbar und darf dort nicht unqualifiziert stehen (§ 4).
4. Offenlegung nach § 10 steht aus, aus demselben Grund wie bei V-001 Punkt 4 → EIP-T-063.

**Behebung 2026-07-28, mit einer offenen Flanke.** `--no-access-log` ergänzt in `render.yaml`,
`Dockerfile` und `start.sh` (Commit `c63dd06`). Lokal gegengeprüft: Mit einem gesetzten
`X-Forwarded-For` erscheint die Besucher-IP ohne den Schalter im Log und mit ihm nicht — auch bei
`--log-level info`. `--proxy-headers` bleibt, weil die App hinter dem TLS-Endpunkt sonst kein HTTPS
erkennt.

**Was noch nicht bestätigt ist.** Ob die Instanz den geänderten Startbefehl tatsächlich übernommen
hat, lässt sich von außen nicht sehen: Der Log liegt im Dashboard des Hosters, und ein Blueprint
übernimmt eine geänderte `startCommand` nicht in jedem Fall automatisch. Der Eintrag bleibt deshalb
offen, bis jemand im Dashboard nachgesehen hat. Ihn jetzt auf „behoben" zu setzen, wäre exakt der
Fehler aus V-001 — ein abgehaktes Kriterium ohne Prüfung am wirksamen Ort.

**Was der Fix nicht erfasst.** Loadbalancer, TLS-Endpunkt und DDoS-Schutz des Hosters protokollieren
unabhängig von der App. Das liegt außerhalb dessen, was ein Startbefehl regelt, und bleibt in
EIP-T-041 offen. § 1 ist damit weiterhin `Disziplin` und die Fälligkeit an der Betriebsstufe
`öffentlich erreichbar` weiterhin gerissen.

**Nachtrag 2026-07-31 — im Dashboard nachgesehen, Wirksamkeit bestätigt.** Der Betreiber hat den
Log-Stream des Services geöffnet. Zwei Belege, beide aus dem Zeitraum 15:55:36–16:25:22 UTC:

1. **Der Startbefehl ist übernommen.** Jede Startzeile des Zeitraums lautet
   `==> Running 'uvicorn web:app --host 0.0.0.0 --port $PORT --proxy-headers
   --forwarded-allow-ips='*' --no-access-log'` — fünfmal, über drei Deploys und beide
   Container-Generationen. Die Sorge, ein Blueprint ziehe die geänderte `startCommand` nicht nach,
   war unbegründet.
2. **Es fällt keine Zugriffszeile an.** In dem Zeitraum liefen mehrere Dutzend Anfragen gegen die
   Instanz (Deploy-Prüfläufe im Sekundentakt, zwei Versionsabgleiche, Abrufe von `/kodex`). Der Log
   enthält für keine davon eine Zeile, weder mit noch ohne IP. Sichtbar sind ausschließlich
   Prozess-, Start- und Deploy-Meldungen.

**Wie belastbar der zweite Beleg ist.** Er stammt nicht aus dem dafür gesetzten Markierungsaufruf:
Der lief um 16:29:53 UTC und damit nach dem Ende des vorliegenden Ausschnitts. Der Nachweis stützt
sich stattdessen auf die Anfragen *innerhalb* des abgedeckten Fensters — dieselbe Aussage, aus mehr
Anfragen, nur ohne die vorgesehene Beschriftung. Das wird hier gesagt, statt den Markierungstest als
bestanden auszugeben, den niemand gesehen hat.

**Was das nicht bedeutet.** Der Verstoß betraf den uvicorn-Zugriffslog, und der ist aus. Renders
eigene Protokollierung am Loadbalancer und TLS-Endpunkt ist damit **nicht** geprüft — sie erscheint
in diesem Log-Stream gar nicht, weil er nur stdout des Containers zeigt. Der Absatz darüber gilt
unverändert: § 1 bleibt `Disziplin`, die Fälligkeit an der Betriebsstufe `öffentlich erreichbar`
bleibt gerissen, und die Schuldenzahl ändert sich nicht (11 von 20). V-002 ist geschlossen, § 1 ist
es nicht.

### V-003 — Vernichteter Umfrage-Schlüssel überlebte im WAL der Datenbank
**Datum des Eintrags:** 2026-07-31 · **Paragraphen:** § 1, § 4, § 18 ·
**Ticket:** EIP-T-041 · **Status:** im Code behoben am 2026-07-31, mit reproduzierbarem Nachweis
(`smoke_test.datenabzug_nach_schluss`); ausgeliefert mit `6b19bed`, **Wirksamkeit auf der laufenden
Instanz nicht bestätigt** — siehe „Was das nicht bedeutet"

**Was geschah.** `Store.vernichte_config` überschreibt den Wert, löscht die Zeile und schreibt die
Datei mit `VACUUM` neu. Der Docstring behauptete dazu, VACUUM räume das Write-Ahead-Log gleich mit
ab. Das tut es nicht. Nach dem Schließen einer Umfrage stand der Umfrage-Schlüssel — der Schlüssel,
mit dem sich die Teilnahmeliste auf Ausweis-Pseudonyme zurückrechnen lässt — vollständig in
`<datenbank>-wal`, während die Datenbankdatei selbst sauber war.

Damit war die Zusage aus Baustein D von EIP-T-033 für jeden nicht erfüllt, der die Dateien
neben der Datenbank mitnimmt — also für jede Beschlagnahme, jedes Datenleck und jede Sicherung, die
das Verzeichnis kopiert statt die Datenbank. Das WAL ist keine Sicherungskopie, sondern Teil der
laufenden Datenbank; die im Text genannte Grenze „gilt für Sicherungskopien nicht" deckt es nicht ab.

**Warum es ein Verstoß und nicht nur ein Fehler ist.** Die Vernichtung stand nicht nur im Code. Sie
steht öffentlich:

| Ort | Wortlaut |
|---|---|
| `/transparenz` | „Der Umfrage-Schlüssel, mit dem sich die Teilnahmeliste auf Ausweise zurückrechnen ließe, wird beim Schließen einer Umfrage vernichtet." |
| Board-Seite jeder Umfrage | „Sobald die Umfrage endet, wird der *private* Teil dieses Schlüssels vernichtet." |

Beide Sätze waren nicht haltbar, solange das WAL den Schlüssel trug. § 4 verlangt, dass keine
Oberfläche mehr behauptet, als der Code hält; § 18 macht die Abweichung zum Eintrag hier.

**Wie es dazu kam.** Die Löschung war sorgfältig gebaut — Überschreiben, Löschen, VACUUM — und der
Docstring benannte sogar die Grenzen der Zusage (Snapshots, SSD-Blockverwaltung). Geprüft wurde nur
nie der Abzug selbst: Ob nach dem Schließen tatsächlich nichts mehr dasteht, war eine Annahme über
das Verhalten von VACUUM, kein Test. Genau diesen Test verlangt Akzeptanzkriterium 5 von EIP-T-041,
und beim ersten Lauf ist er sofort fehlgeschlagen.

**Behebung.** `PRAGMA wal_checkpoint(TRUNCATE)` nach dem VACUUM: Das WAL wird in die frisch
geschriebene Datei zurückgeführt und auf Länge 0 gesetzt. Nachgewiesen wird das nicht mehr durch
eine Zusage, sondern durch `smoke_test.datenabzug_nach_schluss` — der Test zieht nach dem Schließen
den SQL-Abzug, die rohen Bytes von Datenbank, `-wal` und `-shm` sowie den vollständigen Inhalt des
Debug-Moduls und sucht darin nach Pseudonym, Zugangscode und beiden Schlüsseln.

**Was das nicht bedeutet — zuerst: nicht, dass die Instanz den Fix hat.** Der Nachweis oben gilt für
den Arbeitsbaum. Zwischen dem Eintrag hier und der Auslieferung lag ein Stand, in dem dieser Absatz
„behoben" sagte, während <https://eid-poll.onrender.com> die Lücke noch trug. Ausgeliefert ist der
Fix seit `6b19bed` (2026-07-31); ob die laufende Instanz ihn übernommen hat, ist **von außen nicht
feststellbar** — die App hat keine Versionsanzeige, und die Änderung wirkt in Dateien im Container,
nicht in einer Antwort. Bestätigen kann das nur die Deploy-Liste im Render-Dashboard. Das ist
dieselbe Lücke wie bei V-002, und sie wird hier genauso offen benannt statt abgehakt.

**Was das ebenfalls nicht bedeutet.** Ein `truncate` gibt Blöcke frei, es löscht sie nicht physisch.
Sicherungskopien, Dateisystem-Snapshots und die Blockverwaltung einer SSD bleiben außerhalb dessen,
was ein Programm überschreiben kann — das steht unverändert im Docstring und ist keine Formalie: Die
Backup-Regel dazu ist offen und gehört zu EIP-T-041 (Akzeptanzkriterium 3). Bis sie steht, ist die
öffentliche Zusage für *diese eine Datei samt WAL* eingelöst und für alles daneben nicht.

### V-004 — Öffentlicher Code ohne Lizenz: Weiterbetrieb rechtlich nicht erlaubt
**Datum des Eintrags:** 2026-08-01 · **Paragraphen:** § 20, § 14, § 18 ·
**Ticket:** EIP-T-078 · **Status:** offen. Die Behebung
ist eine Lizenzwahl und damit eine Entscheidung des Betreibers, keine Umsetzungsaufgabe

**Was geschah.** § 20 Satz 1 lautet seit Version 1: *„Der Quellcode ist öffentlich, unter einer
Lizenz, die Prüfung und Weiterbetrieb erlaubt."* Status: `bindend`, ohne Vorbehalt und ohne
Fälligkeitsdatum. Das Repository <https://github.com/is-noname/eID-polls> enthält keine
Lizenzdatei und keine Lizenzangabe in `README.md`, `DOKU.md` oder `DEPLOY.md`. Ohne solche Angabe
gilt der gesetzliche Normalfall: alle Rechte vorbehalten. Lesen und Prüfen bleibt möglich, der
**Weiterbetrieb nicht** — also genau die Hälfte der Zusage, die der Paragraph gibt.

Betroffen ist der Zeitraum seit der Veröffentlichung des Repositorys, jedenfalls seit dem Deploy der
öffentlichen Instanz am 2026-07-27, ab dem die Betriebsstufe `öffentlich erreichbar` läuft.

**Wie es dazu kam.** Der Satz stand nie in der Schuldenübersicht — er war `bindend`, und `bindend`
heißt in diesem Kodex „gilt", nicht „ist eingelöst". Geprüft wird aber nur, was als `offen` oder
`Disziplin` vermerkt ist: `scripts/check_kodex.py` verlangt für jeden solchen Vermerk ein Ticket und
ein Ereignis. Ein bindender Satz ohne Vermerk kommt in dieser Prüfung gar nicht vor. Aufgefallen ist
es beim Räumen der *anderen* § 20-Schuld (EIP-T-007), also nur deshalb, weil
jemand denselben Paragraphen aus einem anderen Grund von vorn gelesen hat.

**Was daraus folgt.**

1. Der Verstoß wird ab dem Deploy-Datum gezählt, nicht ab heute — dieselbe Regel wie bei V-002: Ein
   Befund wird nicht dadurch jünger, dass er spät bemerkt wurde.
2. § 20 bleibt in der Schuldenübersicht, obwohl die Schuld, die dort stand, eingelöst ist. Der
   Vermerk wird ausgetauscht, nicht gestrichen — dasselbe Muster wie bei § 16 in Version 13, hier
   allerdings aus einem schwereren Grund: Dort verschob sich eine offene Aufgabe, hier trat ein
   Bruch an ihre Stelle.
3. **Der Kodex prüft seine bindenden Sätze nicht.** V-004 ist ein Befund über den Kodex selbst, nicht
   nur über das Repository: Solange nur Vermerke geprüft werden, ist jeder Satz auf `bindend` ein
   blinder Fleck. Ob daraus eine Prüfpflicht folgt (etwa ein regelmäßiger Durchgang durch alle 20
   Paragraphen mit der Frage „woran sähe man, dass dieser Satz eingelöst ist?"), ist eine
   Kodex-Änderung und gehört nicht in dieses Ticket — festgehalten ist sie hier.
4. Bis zur Lizenz darf nach außen nicht behauptet werden, der Code lasse sich weiterbetreiben. Was
   heute stimmt: Er ist einsehbar und prüfbar.
