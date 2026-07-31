<!-- Erzeugt von scripts/sync_public_docs.py aus KODEX.md im Elternordner.
     Nicht hier bearbeiten - Aenderungen gehoeren ins Original. -->
# Kodex

*Diese Seite ist der Kodex des Projekts im Wortlaut. Sie steht hier, weil § 10 verlangt, dass er von außen erreichbar ist — eine Selbstbindung, die nur der Betreiber lesen kann, ist keine. Kennungen der Form `EIP-T-…` verweisen auf projektinterne Tickets und Dokumente, die nicht veröffentlicht sind; sie stehen hier als Klartext, damit kein Verweis auflösbar aussieht, der es nicht ist. Änderungen und Verstöße: siehe [Kodex-Protokoll](/kodex/protokoll).*

> Lebendes Dokument — der Prüfmaßstab des Projekts, nicht seine Identität. Kein doc-id-Typ, kein Datum.
> Das [Manifest](/manifest) sagt, wer wir sind und was wir behaupten. Dieser Kodex sagt, was wir tun dürfen und
> was nicht. Manifest-Sätze sind Haltungen, Kodex-Sätze sind Tests: Eine Regel taugt nur etwas, wenn ein
> Feature an ihr scheitern kann.
> Historie: [Kodex-Protokoll](/kodex/protokoll) · Begriffe: Glossar (projektintern) ·
> These: EIP-RFC-20260726-001

**Version 11 — 2026-07-31**

---

# Leitfaden

Der Teil, den man bei einer Entscheidung tatsächlich aufschlägt. Die Paragraphen darunter sind das
Nachschlagewerk dazu.

## Vorrangregel

Unsere Grundsätze widersprechen sich real. Individuelle Verifizierbarkeit *erzeugt* die Quittung, die
Nötigung ermöglicht. Merkmalsauswertung erhöht die Aussagekraft und senkt die Anonymitätsmenge. Ohne
festgelegte Rangfolge entscheidet im Konflikt die Bequemlichkeit, und zwar immer zugunsten des Wachstums.

```
1. Wahlgeheimnis / Unverkettbarkeit
2. Ehrlichkeit über die eigenen Grenzen
3. Verifizierbarkeit
4. Aussagekraft
5. Reichweite
```

**Reichweite steht immer letzter.** Ein Argument der Form „das brauchen wir, sonst wachsen wir nicht"
entscheidet keinen Konflikt — es beschreibt ihn nur.

Dass Ehrlichkeit über Verifizierbarkeit steht, ist die zweite bewusste Setzung: Ein System, das etwas
beweisen kann, aber die Reichweite des Beweises überzeichnet, richtet mehr Schaden an als eines, das
weniger beweist und das sagt.

## Prüfliste

Bei jeder Entscheidung durchgehen (§ 19).

**Stoppfragen.** Ein „ja" heißt: nicht bauen, oder Kodex vorher ändern.

1. Entsteht ein neues Datum über Teilnehmende — auch temporär, auch im Log? (§ 1)
2. Wird die Trennung von Berechtigung und Stimme irgendwo schwächer, auch nur statistisch? (§ 2)
3. Ändert sich etwas an Frage, Nenner oder Schwelle, nachdem Zahlen sichtbar waren? (§ 7, § 8)
4. Steht irgendwo eine Zahl ohne ihren Nenner — oder behauptet die Darstellung mehr, als die beiden Zahlen hergeben? (§ 8, § 9)
5. Bekommt jemand Einfluss auf Fragen oder Ergebnisse, weil er zahlt oder Reichweite bringt? (§ 12, § 13)
6. Weicht der ausgelieferte Client vom veröffentlichten Code ab — oder lässt sich das nicht von außen nachprüfen? (§ 20)
7. Steht die Schuldenübersicht über der Grenze — und trägt das Vorhaben keine Schuld ab? (§ 4 b)

**Begleitfragen.** Kein Stopp, aber ohne Antwort ist die Entscheidung nicht getroffen.

8. Wird eine Zusage nur durch unser Verhalten gedeckt — und sagen wir das? (§ 4)
9. Welchen Rang hat der Konflikt hier: Steht Reichweite gegen etwas Höheres? (Vorrangregel)
10. Auf welcher Betriebsstufe greift das — und wird dort eine Fälligkeit fällig? (Betriebsstufen)

## Betriebsstufen

Fälligkeiten hängen an Ereignissen, und die wichtigsten Ereignisse sind Betriebszustände.

| Stufe | Was sie bedeutet | Heute |
|---|---|---|
| `lokal` | Läuft nur auf Rechnern des Projekts. Niemand von außen erreicht die Instanz | — |
| `öffentlich erreichbar` | Eine Instanz ist ohne Absprache aus dem Netz aufrufbar, auch als Vorführung, auch mit Demo-Daten, auch ohne echten eID-Flow | **ja, seit 2026-07-27** |
| `produktiv` | Echter eID-Flow, oder ein Ergebnis, das jemand außerhalb des Projekts ernst nehmen soll | nein |

**Die Stufe entsteht durch die Erreichbarkeit, nicht durch die Absicht.** „Das ist nur eine
Vorführung" senkt die Stufe nicht. Wer die Instanz aufruft, sieht keine Absicht, sondern eine Seite.

An `öffentlich erreichbar` sind fällig: § 1 (Logs beim Hoster), § 4 (Kennzeichnung als Disziplin in
allem, was ausgeliefert wird), § 9 (Sprachregeln in jeder Oberfläche), § 10 (Kodex und
Verstoßprotokoll von außen erreichbar), § 20 (Übereinstimmung von Repository und Auslieferung).

Eine an dieser Stufe unerfüllte Fälligkeit ist ein Verstoß nach § 18 und gehört ins Verstoßprotokoll
— nicht auf eine Merkliste.

## Wie die Paragraphen zu lesen sind

**Regel** (imperativ und prüfbar) · **Warum** (wer den Grund nicht mehr teilt, muss die Regel ändern,
nicht umgehen) · **Konkret verboten** (macht den Paragraphen einsetzbar; ohne diesen Teil ist er
Dekoration) · **Status**.

Der Status ist `bindend` (gilt jetzt, verhandelbar nur über § 17), `offen` (die Regel steht noch aus,
der Paragraph markiert die Lücke bewusst) oder `Disziplin` (die Zusage wird heute nur durch unser
Verhalten gedeckt, nicht durch Technik).

`Disziplin` ist kein Makel, sondern eine Schuld — und **jede Schuld ist fällig gestellt**: Ein
`offen`- oder `Disziplin`-Vermerk nennt das **Ticket**, das ihn auflöst, und das **Ereignis**, vor dem
er aufgelöst sein muss. Ohne beides ist der Vermerk unzulässig und der Paragraph gilt als verletzt
(§ 4 a). Die Schuldenübersicht am Ende führt alle Vermerke zusammen; `scripts/check_kodex.py` prüft
ihre Form.

---

# Paragraphen

## I. Was wir über Teilnehmende wissen dürfen

### § 1 Datensparsamkeit

**Regel.** Wir erheben, verarbeiten und speichern kein Datum, das für Auszählung oder Betrieb nicht
zwingend notwendig ist — auch nicht temporär, auch nicht im Log, auch nicht bei Dritten in unserem Auftrag.
Für jedes gespeicherte Feld existiert eine benannte Notwendigkeit und eine Löschfrist.

**Warum.** Was nicht existiert, kann nicht verloren, verkauft, beschlagnahmt oder versehentlich verknüpft
werden. Die Kryptografie schützt die Stimme; sie schützt nichts, was daneben anfällt.

**Konkret verboten.** Vollständige IP-Adressen in Zugriffs- oder Anwendungslogs. Analytics-, Tracking- oder
Fehler-Reporting-Dienste Dritter. Cookies über das Sitzungsnotwendige hinaus. Browser-Fingerprinting, auch
zur Missbrauchsabwehr — dafür haben wir die eID. Speichern des Referrers der einbettenden Seite auf
Stimmen-Ebene. Übernahme weiterer eID-Datenfelder in die Anfrage an den eID-Server, selbst wenn das
Berechtigungszertifikat sie erlaubt.

**Status.** `bindend`. Die Umsetzung im Betrieb (Log-Konfiguration, Reverse-Proxy, Hosting-Provider) ist
noch nicht abgeschlossen und bis dahin `Disziplin` → EIP-T-041,
fällig ab Betriebsstufe `öffentlich erreichbar`. **Diese Fälligkeit ist gerissen** (V-002).

### § 2 Unverkettbarkeit

**Regel.** Kein Feature, keine Log-Zeile, keine Betriebsroutine darf die Verbindung zwischen
Eligibility-Ledger und Vote-Ledger herstellbar machen — weder für Außenstehende noch für uns.
Vor der Veröffentlichung eines Boards muss eine Mindest-Anonymitätsmenge erreicht sein.

**Warum.** Die Blindsignatur trennt Berechtigung und Stimme mathematisch. Diese Trennung ist keine
Eigenschaft des Verfahrens allein, sondern seiner Umgebung: Sie geht durch Nebenkanäle verloren, die mit
der Kryptografie nichts zu tun haben.

**Konkret verboten.** Zeitstempel in einer Auflösung, die Tokenabholung und Stimmabgabe korrelierbar macht.
Jede Betriebsform, in der Abholung und Abgabe typischerweise sekundennah aufeinanderfolgen, ohne dass
Batching oder Verzögerung dazwischenliegt — bei geringer Beteiligung ist die Blindsignatur sonst praktisch
wertlos. Sortierung des Boards in Eingangsreihenfolge. Sitzungs-IDs, die beide Phasen überspannen.
Admin-Ansichten, die beide Register nebeneinander zeigen. Support-Funktionen, die eine Stimme „wiederfinden"
können.

**Status.** `bindend` als Prinzip. Die konkreten Parameter sind seit Version 7 entschieden und
umgesetzt (EIP-ADR-20260728-001, 2026-07-31): Das Board wird als
Merkle-Set pro Batch mit verketteten Roots veröffentlicht, sortiert nach Blatt-Hash; Mindestmenge
**k = 10** Einträge, Zeitdeckel **6 Stunden**, bei Schließung sofort (der letzte Batch darf k
unterschreiten — dokumentierte Grenze, kein Fehler). Keine Tabelle trägt mehr eine
Eingangsreihenfolge. Ehrlich dazu: k zählt Einträge; im Ein-Klick-Flow sind das je Teilnahme zwei
(Ausgabe + Stimme), die wirksame Personen-Anonymitätsmenge ist also etwa k/2 — zu prüfen in
EIP-T-072. Die Sitzungstrennung der Abstimm-Route
(Baustein F) ist seit Version 8 umgesetzt: Die Stimme geht ohne Cookie, Auth-Header und Referrer
an den Server, mitgesandter Sitzungskontext wird im Debug-Modul als Befund gemeldet, und beide
Phasen-Routen antworten nie schneller als der Antwort-Floor. Noch `offen`: die Speichertrennung
(Baustein G) und die Token-Suche auf `/verify`, die das Session-Cookie im selben Request
mitempfängt →
EIP-T-033, fällig vor dem ersten echten
Durchlauf (Betriebsstufe `produktiv`). Der öffentliche Anker gegen Split-View ist
`offen` → EIP-T-006, dieselbe Fälligkeit.

### § 3 Keine eigene Ausweis-Kryptografie

**Regel.** Wir implementieren keine eID-Kryptografie und keine Wahlprimitive selbst. Wir sind Nutzer
zertifizierter Komponenten und geprüfter Bibliotheken.

**Warum.** Die Kompetenz liegt nicht bei uns, die Prüfung ebenso wenig. Selbstgeschriebene Krypto ist der
klassischste Fehler in genau diesem Feld.

**Konkret verboten.** Eigene Implementierung von eID-Protokollteilen. Eigene RSA-Blindsignatur-Routinen.
Selbstgebaute Zufallsquellen. „Nur für den Prototyp" gilt als Begründung nicht, weil Prototypcode
weiterlebt.

**Status.** `bindend`.

### § 4 Selbstbindung statt Versprechen

**Regel.** Jede Zusage, die wir öffentlich machen, wird nach Möglichkeit technisch erzwungen statt
versprochen. Wo das (noch) nicht geht, wird die Zusage in der Außendarstellung als das gekennzeichnet, was
sie ist: Disziplin, nicht Mathematik. Die Kennzeichnung ist eine Schuld, kein Ersatz — deshalb gilt
zusätzlich:

**a) Fälligkeitspflicht.** Jeder `offen`- und `Disziplin`-Vermerk in diesem Kodex nennt ein
auflösendes Ticket und das Ereignis, vor dem er aufgelöst sein muss. Ein Vermerk ohne beides ist
unzulässig; der betroffene Paragraph gilt bis zur Nachbesserung als verletzt.

**b) Schuldengrenze.** Stehen mehr als **acht** Paragraphen ganz oder teilweise auf `offen` oder
`Disziplin`, darf kein Feature mehr gebaut werden, das nicht eine bestehende Schuld abträgt.
Erlaubt bleiben in diesem Zustand: Arbeit an einem Paragraphen der Schuldenübersicht, Korrektur von
Fehlern und Verstößen, Prüfwerkzeuge, Dokumentation, Sicherheitsarbeit. Nicht erlaubt: alles, was
Reichweite, Funktionsumfang oder Außenwirkung vergrößert.

**Warum.** Ein Projekt, das mit Vertrauen wirbt, wird an der Differenz zwischen „können wir nicht" und
„tun wir nicht" gemessen. Die Zusätze a) und b) stehen hier, weil die Kennzeichnungspflicht allein
einen Ausweg offenließ: Wer einen Text an den Ist-Zustand angleicht, hat diesem Paragraphen genügt,
ohne etwas gebaut zu haben (Herleitung: [Kodex-Protokoll](/kodex/protokoll), Version 3).

**Konkret verboten.** Formulierungen der Art „wir können nicht", wo tatsächlich „wir tun es nicht" gilt.
Aktuell betrifft das vor allem Ballot Stuffing: Solange eine Umfrage **läuft**, liegt ihr
Token-Signaturschlüssel bei uns allein, und wir könnten Phantom-Tokens signieren. Das ist Disziplin,
bis die Schwellensignatur steht — und wird so gesagt. Ebenfalls verboten: einen Vermerk auf `offen`
stehen lassen, ohne Ticket und Ereignis zu
nennen; die Grenze aus b) durch Umdeklarieren eines Features zu „Wartung" umgehen; die Grenze
anheben, statt eine Schuld abzutragen (das wäre eine Änderung nach § 17 und braucht deren Begründung).

Seit Version 9 gilt diese Disziplin nur noch **während** der Laufzeit einer Umfrage
(EIP-T-069, 2026-07-31): Jede Umfrage hat ein eigenes
Signaturschlüsselpaar, dessen privater Teil beim Schließen vernichtet wird. Danach kann niemand
mehr gültige Token herstellen, auch wir nicht — die Auszählung ist eingefroren. Vorher ändert sich
nichts, und genau dort findet Stuffing statt. Die Schuld ist damit zeitlich halbiert, nicht
getilgt; wer sie als erledigt darstellt, verstößt gegen diesen Paragraphen.

**Status.** `bindend`. Eigene Schuld: Ballot Stuffing bleibt `Disziplin` **für die Laufzeit einer
Umfrage**, bis der Signaturschlüssel geteilt ist →
EIP-T-040, fällig vor dem ersten echten Durchlauf.
Dagegen helfen nur verteilte Dritte (§ 12); was bleibt, ist die Ledger-Abrechnung, die den
Überschuss sichtbar macht. Die weiteren Schulden dieses Paragraphen sind bei ihren Paragraphen
geführt: öffentlicher Anker gegen Split-View (§ 2), reproduzierbarer Build (§ 20).

### § 5 Behörden, Herausgabe und Auskunft

**Regel.** Wir geben nur heraus, wozu wir rechtlich verpflichtet sind, und veröffentlichen jede Anfrage,
soweit uns das erlaubt ist. Der primäre Schutz ist § 1: Was wir nicht haben, können wir nicht herausgeben.

**Warum.** Der Betreiber ist der wahrscheinlichste Angriffspunkt, nicht die Kryptografie. Eine Anfrage
kommt irgendwann, und die Antwort darauf muss vorher feststehen — nicht unter Zeitdruck entstehen.

**Konkret verboten.** Stille Kooperation. Anlassbezogene Erweiterung der Protokollierung auf Zuruf. Zusagen
gegenüber Behörden, die über den Kodex hinausgehen, ohne öffentliche Änderung desselben.

**Status.** `bindend` seit Version 4. Das Verfahren steht in
EIP-RFC-20260729-001, der Bericht unter [Transparenzbericht](/transparenz) und auf
der öffentlichen Instanz unter `/transparenz` — beginnend beim Nullfall, damit sein erstes Erscheinen
nicht selbst zur Auskunft wird.

Der **Eingangskanal** ist dagegen `offen`: Anfragen sollen an eine eigene, ausschließlich dafür
bestimmte Adresse gehen; die gibt es noch nicht, weil das Projekt keine Domain hat. Bis dahin
erreicht eine Behörde das Projekt nur über den Betreiber persönlich, und der Transparenzbericht sagt
das → EIP-T-073, fällig ab Betriebsstufe `produktiv`.

### § 6 DSGVO-Kollision

**Regel.** Wir behandeln das Pseudonym als personenbezogenes Datum. Der Konflikt zwischen Auskunfts- und
Löschansprüchen einerseits und Unverkettbarkeit sowie append-only Board andererseits wird vorab entschieden,
dokumentiert und öffentlich begründet — nicht im Moment der ersten Anfrage.

**Warum.** Beide Seiten sind berechtigt. Eine Auskunft „welche Stimme gehört zu mir" würde genau das
Wahlgeheimnis brechen, das wir zusagen; diese Spannung ist nicht auflösbar, nur sauber begründbar.

**Konkret verboten.** So zu tun, als bestünde der Konflikt nicht. Nachträgliches Aufweichen von § 2, um
einen Auskunftsanspruch bedienen zu können.

**Status.** `offen` → EIP-T-061, fällig vor Betriebsstufe
`produktiv`.

---

## II. Wie wir Ergebnisse erzeugen und darstellen

### § 7 Präregistrierung

**Regel.** Vor dem Start jeder Umfrage stehen öffentlich fest: Frage, Antwortoptionen, Laufzeit, gewählter
Nenner, Veröffentlichungsschwelle und Auswertungsplan. Nach Sicht der Zahlen wird daran nichts mehr
geändert.

**Warum.** Der wirksamste Manipulationsweg ist nicht die Auszählung, sondern die nachträgliche Wahl des
Maßstabs. Präregistrierung ist der einzige Schutz dagegen, der ohne Vertrauen auskommt.

**Konkret verboten.** Nachträgliche Änderung des Nenners. Absenken der Veröffentlichungsschwelle, weil sie
knapp verfehlt wurde. Verlängerung einer laufenden Umfrage wegen des Zwischenstands. Nachträglich
hinzugefügte Untergruppen-Auswertungen, die vorher nicht geplant waren.

**Status.** `bindend`.

### § 8 Zahlen-Ehrlichkeit

**Regel.** Beteiligungsquote und benannter Nenner werden gleichrangig mit jedem Ergebnis veröffentlicht.
Wird die vorab festgelegte Schwelle nicht erreicht, erscheint kein Ergebnis — nur die Tatsache, dass die
Schwelle nicht erreicht wurde.

**Warum.** Der Nenner ist die eigentliche Innovation. Eine Zahl ohne ihn ist genau die Sorte Zahl, gegen
die wir angetreten sind.

**Konkret verboten.** Prozentwerte ohne absolute Zahlen. Ergebnisgrafiken, die die Quote kleiner setzen als
das Ergebnis. Veröffentlichung „nur intern" oder „nur für den Partner" unterhalb der Schwelle.
Zwischenstände während der Laufzeit über den reinen Teilnahmezähler hinaus.

**Status.** `bindend`.

### § 9 Sprachregeln

**Regel.** Jede eigene Aussage über ein Ergebnis nennt die Stimmanzahl und den Nenner im selben Satz:

> „1,2 Mio. Menschen haben mit Ausweis abgestimmt, 68 % davon sagen X. Das sind 2 % der 61 Mio.
> Wahlberechtigten."

Nie „die Bevölkerung denkt X", nie „repräsentativ". Die Regel bindet uns, unsere Grafiken und das
Einbettungs-Widget — nicht Dritte, die zitieren.

**Warum.** Die Zahlen erledigen das Argument selbst: Wer den Nenner danebenstehen sieht, kann nicht
mehr behaupten, hier spreche das Land. Dafür braucht es kein Fachwort und keine Zitierauflage, nur
die Disziplin, den Nenner nie wegzulassen.

**Konkret verboten.** „Deutschland sagt", „die Mehrheit der Deutschen", „repräsentative Erhebung".
Prozentwerte ohne die absolute Zahl daneben. Hochrechnungen. Gewichtungen. Vergleichsgrafiken mit
Institutszahlen, die die Gattungsdifferenz verwischen. Widget-Konfigurationen, mit denen ein Einbetter
die Quote ausblenden kann.

**Nicht verboten.** Dass Dritte die Zahl anders formulieren. Zitieren ist frei; wer daraus
„Deutschland sagt X" macht, verantwortet das selbst. Eine Bedingung, die wir gegenüber Presse oder
Politik ohnehin nicht durchsetzen könnten, steht hier nicht (Herleitung: [Kodex-Protokoll](/kodex/protokoll),
Version 6).

**Status.** `bindend` — und ab Betriebsstufe `öffentlich erreichbar` gilt das für jede ausgelieferte
Oberfläche, nicht erst für veröffentlichte Ergebnisse (V-001). Der genaue Wortlaut, überall gleich,
wird in EIP-T-028 festgelegt; das ist eine
Formulierungsaufgabe, keine offene Regel.

### § 10 Fehler, Widerruf und Offenlegung

**Regel.** Ein Fehler, der ein veröffentlichtes Ergebnis oder eine Zusage dieses Kodex berührt, wird
öffentlich gemacht — unaufgefordert, mit Post-Mortem, und ohne dass wir abwarten, ob es jemand merkt.
Betroffene Ergebnisse werden zurückgezogen, nicht korrigiert nachgereicht.

**Warum.** Wir treten mit dem Anspruch an, dass niemand uns glauben muss; der einzige Weg, das nach einem
Fehler aufrechtzuerhalten, ist, ihn selbst zu berichten. Ein still gefixter Bug ist die teuerste
Zeitbombe, die dieses Projekt haben kann.

**Frist.** Sieben Tage ab Kenntnis. Nicht ab Behebung — ein Fehler, der lange gefixt wird, wird lange
verschwiegen, und die Frist soll gerade den Zeitraum decken, in dem noch nichts repariert ist. Ein
unfertiger Stand wird als unfertig veröffentlicht.

**Format.** Jedes Post-Mortem ist ein Eintrag im Verstoßprotokoll des [Kodex-Protokoll](/kodex/protokoll) und nennt:
was geschah · welche Paragraphen berührt sind · welche veröffentlichten Ergebnisse betroffen sind
(auch: keine) · seit wann bis wann der Zustand bestand · was daraus folgt, mit Ticket. Kein eigenes
Format daneben: Ein Post-Mortem, das woanders steht als der Verstoß, den es erklärt, wird beim
nächsten Mal nicht gefunden.

**Weg.** Kodex, Verstoßprotokoll und Transparenzbericht ([Transparenzbericht](/transparenz), § 5) sind auf der
öffentlichen Instanz unter `/kodex`, `/kodex/protokoll` und `/transparenz` erreichbar, ohne
Anmeldung. Sie werden aus den maßgeblichen Dateien erzeugt (`scripts/sync_public_docs.py`); eine
zweite, handgepflegte Fassung wäre nach § 20 selbst ein Verstoß.

**Konkret verboten.** Stilles Patchen sicherheits- oder ergebnisrelevanter Fehler. Rückdatierte oder
kommentarlos ersetzte Board-Stände. Korrektur eines veröffentlichten Ergebnisses ohne sichtbaren Hinweis
auf den ursprünglichen Stand. Ein Post-Mortem, das auf die Behebung wartet.

**Status.** `bindend`. Frist, Format und Offenlegungsweg sind seit Version 10 entschieden und
umgesetzt (EIP-T-063); die Fälligkeit aus V-001 Punkt 4
ist damit erfüllt.

### § 11 Zugang und Ausschluss

**Regel.** Wir benennen die Ausschlusswirkung des Verfahrens bei jedem Ergebnis, nicht nur im Manifest.
Barrierefreiheit und die Unterstützung von eID-Karte und eAT sind keine Zusatzfeatures, sondern
Grundanforderungen.

**Warum.** Rund 18 Prozent der Erwachsenen haben eine nutzbare eID. Das System schließt strukturell aus,
und wer teilnimmt, unterscheidet sich systematisch von wer nicht teilnimmt — das gehört an die Zahl, nicht
in eine Fußnote.

**Konkret verboten.** Ergebnisdarstellung ohne Hinweis auf die eID-Verfügbarkeit als Zugangsvoraussetzung.
Beschränkung auf den deutschen Personalausweis, wo eID-Karte und eAT technisch mitgehen. Flows, die ohne
Sehvermögen oder Maus nicht bedienbar sind.

**Status.** `bindend`. Der Umsetzungsstand bei eAT und Barrierefreiheit ist `offen` →
EIP-T-064, fällig vor dem ersten echten Durchlauf
(Betriebsstufe `produktiv`).

---

## III. Wer über uns bestimmt

### § 12 Fragehoheit

**Regel.** Die Macht darüber, welche Frage gestellt wird, wie sie formuliert ist, welche Antworten zur
Wahl stehen und wann sie läuft, ist die wirksamste Form der Ergebnissteuerung. Sie gehört nicht dauerhaft
uns. Bis zur Übergabe an ein unabhängiges Gremium gilt: jede Frage neutral formuliert, immer mit
Enthaltungsoption, und abgelehnte Fragevorschläge werden mitsamt Ablehnungsgrund veröffentlicht.

**Warum.** Es wäre absurd, dem Auftraggeber der Meinungsforschung diese Macht zu nehmen, um sie uns selbst
zu geben. Sichtbar wird Themenauswahl nur, wenn auch das Abgelehnte sichtbar ist.

**Konkret verboten.** Suggestivformulierungen. Antwortlisten ohne Enthaltung oder „weiß nicht". Unvollständige
oder tendenziös geschnittene Antwortoptionen. Themenwahl nach erwarteter Aufmerksamkeit. Timing nach
politischer Opportunität.

**Status.** `offen` — und der größte ungelöste Knoten des Projekts →
EIP-T-022. Die Übergabe erfolgt, **bevor** die Instanz groß genug ist,
um politisch zu zählen, nicht danach; das ist zugleich das Fälligkeitsereignis. Weil dieser Zeitpunkt
sich nicht von außen ankündigt, gilt ersatzweise die Betriebsstufe `produktiv` als späteste
Fälligkeit.

### § 13 Unabhängigkeit und Geld

**Regel.** Alle Geldgeber werden mit Betrag und Zeitraum offengelegt. Finanzierung begründet keinen Einfluss
auf Formulierung, Zeitpunkt, Veröffentlichung oder Auswertung. Es gibt keine Exklusivität an Ergebnissen.
Daten werden nicht verkauft, Werbung nicht geschaltet.

**Warum.** „Wer bezahlt, wählt die Frage" ist unser eigener Vorwurf an die Institute. Er trifft uns, sobald
wir Geld annehmen, und zwar mit doppelter Wucht.

**Konkret verboten.** Auftragsfragen mit Ergebnisexklusivität oder Sperrfrist zugunsten des Zahlenden.
Sponsoring, das an Themen gebunden ist. Verkauf oder Auswertung von Teilnahmedaten in jeder Form.
Vertragliche Zusagen an Geldgeber, die diesem Kodex widersprechen.

**Status.** `offen` in den Details — die Ausformulierung hängt am Finanzierungsmodell aus
EIP-RFC-20260726-002 → EIP-T-026, fällig
vor der ersten Annahme von Geld. Offenlegungspflicht, Einflussverbot und Datenverkaufsverbot
gelten ab sofort `bindend`.

### § 14 Nachfolge und Fortbestand

**Regel.** Dieser Kodex bindet auch jeden Rechtsnachfolger. Verkauf, Übernahme, Trägerwechsel oder
Einstellung des Betriebs erfolgen nicht ohne öffentliche Ankündigung. Bei Einstellung bleiben die Boards
verifizierbar archiviert; die Register mit Pseudonymen werden gelöscht.

**Warum.** Ein Regelwerk ohne Exit-Klausel überlebt den ersten Eigentümerwechsel nicht — und der
Eigentümerwechsel ist der Moment, in dem der Datenbestand am meisten wert ist und die Grundsätze am
wenigsten kosten.

**Konkret verboten.** Stiller Trägerwechsel. Übertragung des Datenbestands als Vermögenswert.
Abschaltung ohne Archivierung der veröffentlichten Boards.

**Status.** `offen`. Die rechtliche Absicherung hängt an der Rechtsform, die noch nicht gewählt ist →
EIP-T-065, fällig vor Betriebsstufe `produktiv`, jedenfalls vor
jedem Trägerwechsel.

### § 15 Kein Engagement-Optimieren

**Regel.** Wir machen kein Spiel aus dem Abstimmen und wachsen nicht über Empörung. Optimiert werden dürfen
ausschließlich: Abschlussquote des eID-Flows, Verständlichkeit, Zugänglichkeit, eID-Aktivierungen.

**Warum.** Alles, was Menge belohnt, erzeugt Klicks statt Meinungen — und liefert jedem Kritiker die
Munition frei Haus. Wachstum über Aufregung wäre exakt die Parteilichkeit, die wir anderen vorwerfen.

**Konkret verboten.** Punkte, Serien, Streaks, Ranglisten, Belohnungen für Teilnahmehäufigkeit. Push- oder
E-Mail-Reaktivierung mit Aufmerksamkeitslogik. Themenauswahl nach Reichweitenpotenzial. Ergebnis-Teilen
mit Wettbewerbscharakter.

**Status.** `bindend`.

### § 16 Grenzen der Nutzung

**Regel.** Ergebnisse haben keine Rechtswirkung. Das Verfahren wird nicht in bindenden Entscheidungen
eingesetzt, nicht als Wahl, nicht als Volksentscheid, nicht als Betriebsrats- oder Vereinswahl. Wir setzen
das über Nutzungsbedingungen für Einbetter durch, nicht nur als Bekenntnis.

**Warum.** Uns fehlen die Schutzmechanismen des Wahlrechts, allen voran die Nötigungsresistenz: Unsere
individuelle Verifizierbarkeit ist zugleich eine vorzeigbare Quittung. Das ist eine bewusste
Architekturentscheidung — und sie schließt jeden Wahleinsatz aus.

**Konkret verboten.** Vermarktung als Wahlsystem. Kooperationen, deren Zweck eine bindende Abstimmung ist.
Stillschweigende Duldung, wenn ein Einbetter das Widget so einsetzt.

**Status.** `bindend`. Die Durchsetzung über Nutzungsbedingungen ist `offen` →
EIP-T-062, fällig vor der ersten Einbettung durch
Dritte, spätestens vor Betriebsstufe `produktiv`.

---

## IV. Verfahren

### § 17 Änderung dieses Kodex

**Regel.** Änderungen erfolgen versioniert, mit datiertem Eintrag im Änderungsprotokoll
([Kodex-Protokoll](/kodex/protokoll)) und einer Begründung, die den Grund benennt — nicht nur die neue Formulierung.
Der Diff bleibt öffentlich nachvollziehbar. Ein Paragraph darf nicht rückwirkend auf eine bereits
getroffene Entscheidung angepasst werden, um sie nachträglich zu decken. Eine Kürzung braucht dieselbe
Begründung wie eine Verschärfung.

**Warum.** Ein Regelwerk, das man still ändern kann, ist keins. Die Änderungshistorie ist der eigentliche
Beleg dafür, ob der Kodex Entscheidungen geformt hat oder ihnen nur hinterhergeschrieben wurde.

**Status.** `bindend`.

### § 18 Verstöße

**Regel.** Verstöße gegen diesen Kodex werden im Verstoßprotokoll ([Kodex-Protokoll](/kodex/protokoll)) dokumentiert:
was geschah, welcher Paragraph, was daraus folgte. Auch dann, wenn niemand außerhalb es bemerkt hätte.

**Protokoll oder Ticket-Verlauf.** Drei Fragen, in dieser Reihenfolge:

1. **Berührt der Befund eine Zusage dieses Kodex?** Nein → Ticket-Verlauf. Ein Fehler ohne
   Kodex-Bezug ist Arbeit, kein Verstoß.
2. **War der Bruch wirksam?** Wirksam heißt: ausgeliefert, veröffentlicht, an Dritte gegeben oder als
   Entscheidung getroffen. Was im Arbeitsbaum entsteht und dort behoben wird, bevor es einen
   ausgelieferten Stand erreicht, ist Arbeit. Was auf der öffentlichen Instanz stand, war wirksam —
   auch für eine Stunde, auch unbemerkt, auch wenn es niemand aufgerufen hat.
3. **Ist die Lücke schon als `offen` oder `Disziplin` vermerkt?** Dann trägt sie die
   Schuldenübersicht, nicht das Protokoll. Es sei denn, die Fälligkeit ist gerissen — das Ereignis ist
   eingetreten oder die Betriebsstufe erreicht, und der Vermerk steht noch. Dann ist es ein Verstoß.

Im Zweifel ins Protokoll. Maßgeblich ist nicht, wie schwer der Fall demjenigen wiegt, der ihn gemacht
hat, sondern wie er aussähe, wenn ihn jemand von außen fände.

**Ein Sachverhalt, ein Eintrag.** Der Faktenkern steht im Verstoßprotokoll, das Ticket verweist darauf
und trägt den Arbeitsweg. Nicht umgekehrt, nicht zweimal — eine zweite Fassung driftet von der ersten
weg (EIP-T-044).

**Warum.** Siehe § 10. Dieselbe Logik gilt für Regelbrüche wie für Bugs. Ein leeres Verstoßprotokoll nach
Jahren Betrieb ist kein gutes Zeichen, sondern ein verdächtiges. Die Abgrenzung steht hier, weil sie
sonst im Einzelfall gezogen wird — und dann regelmäßig zugunsten der Stelle, die niemand außerhalb
liest: Der erste Verstoß dieses Projekts lag ein halbes Jahr als Ticket-Notiz vor, während das
Protokoll leer blieb (V-001, EIP-T-058).

**Konkret verboten.** Einen Befund, der die drei Fragen passiert, allein im Ticket-Verlauf ablegen.
Den Eintrag sparen, weil der Fehler bereits behoben ist — behoben ändert die Folge, nicht die
Pflicht. Einen bestehenden Eintrag nachträglich entschärfen oder entfernen; Korrekturen sind
Nachträge, kein Umschreiben (§ 17 sinngemäß).

**Status.** `bindend`.

### § 19 Prüfpflicht

**Regel.** Jede ADR, jedes Ticket mit Architektur- oder Außenwirkung und jede Veröffentlichung durchläuft
die Prüfliste. Berührte Paragraphen werden im jeweiligen Dokument benannt.

**Status.** `bindend`.

### § 20 Offener Code und nachprüfbarer Build

**Regel.** Der Quellcode ist öffentlich, unter einer Lizenz, die Prüfung und Weiterbetrieb erlaubt.
Für den Client gilt zusätzlich: Was im Browser läuft, muss aus dem veröffentlichten Stand
reproduzierbar sein — mit veröffentlichtem Hash und benanntem Commit. Der Prüfweg wird so
dokumentiert, dass ihn jemand außerhalb des Projekts ohne Rückfrage gehen kann.

**Warum.** Die Unverkettbarkeit entsteht im Browser, nicht auf dem Server: Das Blinding läuft im
Client, und damit ist der ausgelieferte Client die Stelle, an der das Wahlgeheimnis unbemerkt
abgeschaltet werden könnte. Ohne reproduzierbaren Build ist „unser Code ist öffentlich" eine
Aussage über ein Repository, nicht über die Seite, die jemand gerade benutzt.

**Konkret verboten.** Ausliefern von Client-Code, der nicht dem veröffentlichten Stand entspricht.
Minifizierte oder gebündelte Auslieferung ohne reproduzierbaren Weg vom Quelltext dorthin. Stille
Änderung des ausgelieferten Stands ohne neuen veröffentlichten Hash. Server-seitige Ausführung von
Schritten, die im Client laufen müssen — allen voran das Blinding. Fremde Bibliotheken sind dagegen
erlaubt und nach § 3 geboten; sie gehören in den veröffentlichten, gehashten Stand.

**Status.** `bindend` für die Veröffentlichung des Quellcodes. Reproduzierbarer Build,
Hash-Veröffentlichung und Prüfanleitung sind `offen` → EIP-T-007, fällig vor
dem ersten echten Durchlauf (Betriebsstufe `produktiv`).

Bis dahin ist die Übereinstimmung von Repository und Auslieferung `Disziplin` und wird so gesagt
(§ 4) → EIP-T-074, fällig ab Betriebsstufe `öffentlich
erreichbar`. Nach V-001 wieder hergestellt (Stand `c63dd06`, 2026-07-28) — und weil nur Disziplin sie
hält, reißt sie mit jedem lokalen Commit erneut, der nicht ausgeliefert wird.

---

## Schuldenübersicht

Alle Paragraphen, die ganz oder teilweise auf `offen` oder `Disziplin` stehen. Die Liste ist
abgeleitet, nicht eigenständig: Maßgeblich ist der Status beim jeweiligen Paragraphen.
`scripts/check_kodex.py` prüft, dass beide übereinstimmen und dass kein Vermerk ohne Ticket und
Ereignis dasteht.

**Stand 2026-07-31: 11 von 20 Paragraphen. Die Grenze aus § 4 b liegt bei 8 — sie ist überschritten,
der Baustopp gilt.**

Die Zahl steht seit Version 9 unverändert, obwohl § 10 mit Version 10 herausfällt: § 5 tritt an
seine Stelle. Der Offenlegungsweg ist gebaut, der Eingangskanal für Behördenanfragen ist es nicht —
das war die bewusste Entscheidung, keine private Adresse dauerhaft an das Projekt zu binden
(EIP-T-063). Ein Tausch, kein Abtrag.

| § | Was offen ist | Ticket | Fällig vor | Seit |
|---|---|---|---|---|
| 1 | Log-Konfiguration bei Proxy und Hoster | EIP-T-041 | `öffentlich erreichbar` | 2026-07-26 |
| 2 | Speichertrennung der Abstimm-Route (Baustein G) und Session-Cookie an /verify | EIP-T-033 | `produktiv` | 2026-07-26 |
| 2 | Öffentlicher Anker gegen Split-View | EIP-T-006 | `produktiv` | 2026-07-26 |
| 4 | Ballot Stuffing bleibt Disziplin **während der Laufzeit** (Schlüssel liegt allein bei uns; nach Schließung vernichtet, EIP-T-069) | EIP-T-040 | `produktiv` | 2026-07-26 |
| 5 | Eigener Eingangskanal für Behördenanfragen (keine Domain) | EIP-T-073 | `produktiv` | 2026-07-31 |
| 6 | DSGVO-Kollision entschieden und begründet | EIP-T-061 | `produktiv` | 2026-07-26 |
| 11 | eAT-Unterstützung, Barrierefreiheit | EIP-T-064 | `produktiv` | 2026-07-26 |
| 12 | Übergabe der Fragehoheit an ein unabhängiges Gremium | EIP-T-022 | politische Relevanz, spät. `produktiv` | 2026-07-26 |
| 13 | Finanzierungsmodell im Detail | EIP-T-026 | erste Annahme von Geld | 2026-07-26 |
| 14 | Rechtsform und Nachfolgebindung | EIP-T-065 | `produktiv`, jed. vor Trägerwechsel | 2026-07-26 |
| 16 | Durchsetzung über Nutzungsbedingungen | EIP-T-062 | erste Einbettung, spät. `produktiv` | 2026-07-26 |
| 20 | Reproduzierbarer Build, Hash, Prüfanleitung | EIP-T-007 | `produktiv` | 2026-07-27 |
| 20 | Übereinstimmung Repository und Auslieferung | EIP-T-074 | `öffentlich erreichbar` | 2026-07-27 |

Drei Fälligkeiten hängen an der Betriebsstufe `öffentlich erreichbar`, die seit dem 2026-07-27 läuft.
Stand 2026-07-31:

- **§ 20** — erfüllt **im Moment jeder Prüfung, nicht dauerhaft**: Zwischen einer Änderung hier und
  ihrem Deploy zeigt die Instanz einen älteren Stand, und niemand außer uns bemerkt das. Kein
  Verstoß nach § 18, solange die Instanz korrekt sagt, welche Version sie zeigt — aber auch kein
  Zustand, den dieser Punkt dauerhaft behaupten kann. Deshalb steht hier keine Momentaufnahme:
  Was der ausgelieferte Stand ist und wie man ihn prüft, ist die Aufgabe von
  → EIP-T-074. Bis dahin trägt es Disziplin
- **§ 10** — erfüllt: Kodex, Verstoßprotokoll und Transparenzbericht sind auf der Instanz ohne
  Anmeldung erreichbar (Version 10, EIP-T-063)
- **§ 1** — weiterhin nur teilweise: Die App protokolliert keine IPs mehr, was der Hoster daneben
  mitschreibt, ist ungeprüft (V-002, Wirksamkeit auf der Instanz nicht bestätigt). **Die einzige
  gerissene Fälligkeit dieser Betriebsstufe**

Die Spalte *Seit* nennt das Datum der Kodex-Version, in der der Vermerk zuerst stand, nicht das
Datum dieser Übersicht. Ein Vermerk wird durch die Aufnahme hier nicht jünger.

---

Änderungen und Verstöße: [Kodex-Protokoll](/kodex/protokoll) (§ 17, § 18).
