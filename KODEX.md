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

**Version 22 — 2026-08-01**

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

## Fälligkeitsereignisse

§ 4 a verlangt zu jeder Schuld ein Ereignis, vor dem sie aufgelöst sein muss. Zulässig sind
ausschließlich die folgenden. **Ein Ereignis, das hier nicht steht, ist eines, auf das sich niemand
berufen kann** — ein Vermerk, der ein anderes nennt, ist formfehlerhaft.

- `öffentlich erreichbar` — Betriebsstufe, siehe oben
- `produktiv` — Betriebsstufe, siehe oben
- ersten echten Durchlauf — die erste Umfrage, deren Ergebnis zählen soll
- ersten Frage außerhalb einer Vorführung — auch dann, wenn niemand das Ergebnis ernst nimmt
- ersten Einbettung — die erste Einbindung auf einer fremden Seite
- Annahme von Geld — die erste, gleich von wem und in welcher Höhe
- Trägerwechsel — das Projekt wechselt den Betreiber oder die Rechtsform

Diese Liste ist Kodextext, nicht Konfiguration: Sie zu erweitern ist eine Änderung nach § 17 und
braucht Version, Protokolleintrag und Begründung. `scripts/check_kodex.py` **liest sie von hier**
und hält keine eigene Fassung — eine zweite Liste im Code wäre ein zweiter Kodex ohne
Änderungspflicht (Herleitung: EIP-AUD-20260801-005 Abschnitt 5).

Die Formulierung im Status-Absatz muss das Ereignis wörtlich enthalten. Das ist Absicht: Wer sein
Ereignis frei formuliert, hat es für jede Prüfung unsichtbar gemacht, und genau das war bis
Version 22 bei § 12 der Fall.

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

**Status.** `bindend`. Die Umsetzung im Betrieb ist noch nicht abgeschlossen und bis dahin
`Disziplin` → EIP-T-075, fällig ab Betriebsstufe
`öffentlich erreichbar`. **Diese Fälligkeit ist gerissen** — maßgeblich ist der **Nachtrag vom
2026-07-31 zu V-002**, nicht dessen Kopf: Der Eintrag selbst steht auf „behoben", weil der
uvicorn-Zugriffslog aus ist; der Nachtrag sagt im letzten Satz, was hier gilt — *„V-002 ist
geschlossen, § 1 ist es nicht."* Ein zweiter Verstoßeintrag über denselben Sachverhalt wäre die
doppelte Fassung aus § 18.

Was daran noch offen ist, ist seit dem 2026-07-31 auf einen Punkt zusammengeschnurrt: die eigene
Seite — Zugriffslog, Reverse-Proxy, Debug-Modul, Schlüsselvernichtung samt WAL — ist erhoben,
abgeschaltet und getestet (EIP-T-041,
`EIP-RPT-20260731-002`). Übrig bleibt, was Renders Loadbalancer und TLS-Endpunkt mitschreiben. Das
ist keine Konfigurationsfrage mehr, sondern eine Auskunft, die ein Dritter geben muss.

Die Auswertung der öffentlichen Unterlagen am 2026-07-31 hat den Punkt verschärft, nicht entlastet:
Render sagt vertraglich „comprehensive and centralized logging and monitoring" der eigenen
Infrastruktur zu, ohne Angabe von Umfang oder Frist, und der gesamte Verkehr läuft davor über
Cloudflare. **Dass protokolliert wird, ist damit belegt** — offen ist nur noch, was und wie lange
(`EIP-RPT-20260731-002` § 1.5.1). Der Satz „keine verkettenden Daten, auch nicht bei Dritten"
steht damit nicht vor einer Wissenslücke, sondern vor einem benannten Widerspruch, den entweder
Renders Antwort auflöst oder ein Hosterwechsel.

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
**k = 10 Stimmen**, Zeitdeckel **6 Stunden**, bei Schließung sofort (der letzte Batch darf k
unterschreiten — dokumentierte Grenze, kein Fehler). Keine Tabelle trägt mehr eine
Eingangsreihenfolge. Dass k **Stimmen** zählt und nicht Einträge, ist eine Korrektur vom
2026-08-01 (Version 15, Begründung im [Kodex-Protokoll](/kodex/protokoll)): Vorher zählte k alle Einträge, und weil
jede Teilnahme zwei erzeugt (Ausgabe + Stimme), war die zugesagte Menge in Wahrheit k/2 — unter
Andrang lagen 23,6 % der Stimmen sogar unter 5
(EIP-RPT-20260731-001 Anonymitaetsmenge-Batch-Simulation; woher die Simulation stammt, steht
dort). An Stimmen gebunden fällt dieser Anteil auf 0,0 %, bei gleicher Batchgröße und gleicher
Wartezeit. Ehrlich zu nennen bleibt, was die Zusage **nicht** deckt: Löst der Zeitdeckel aus oder
endet die Umfrage, wird auch unter k veröffentlicht. Das Board nennt deshalb je Batch die
tatsächliche Stimmenzahl und hebt die kleinste hervor, und der Betreiber bekommt jeden solchen
Batch als Befund ins Debug-Modul — die Zusage gilt, wo sie greift, und wo sie nicht greift, steht
es da. Ebenfalls gemessen und ehrlich
zu nennen: Unterhalb von rund `k/Deckelfenster` Teilnahmen je Stunde greift der Zeitdeckel
statt k, und die Menge fällt gegen 1 — bei 25 Teilnehmenden über 7 Tage steht jede fünfte Stimme
allein in ihrem Batch. Das ist die Grenze des Mechanismus und durch keine Parameterwahl zu
beheben. Die Sitzungstrennung der Abstimm-Route
(Baustein F) ist seit Version 8 umgesetzt: Die Stimme geht ohne Cookie, Auth-Header und Referrer
an den Server, mitgesandter Sitzungskontext wird im Debug-Modul als Befund gemeldet, und beide
Phasen-Routen antworten nie schneller als der Antwort-Floor. Seit Version 16 sind auch die
Speichertrennung (Baustein G) und die Token-Suche auf `/verify` umgesetzt (Herleitung und
Ticketverweis im [Kodex-Protokoll](/kodex/protokoll), Version 16): Eligibility-Ledger und Board
liegen in zwei Datenbankdateien mit getrennten Zugriffspfaden und getrennten Debug-Logs, und die
Token-Suche läuft im Browser über den Board-Export — das Token steht im URL-Fragment und erreicht
den Server nicht mehr. Ehrlich dazu: Beide Seiten laufen weiter in einem Prozess bei einem
Betreiber; gegen Laufzeit-Beobachtung durch uns selbst hilft die Trennung der Dateien nicht
(EIP-T-037 für die Betreibergrenze).

Die **Netzwerkebene** ist seit Version 18 entschieden und zur Hälfte gebaut
(EIP-ADR-20260801-003, EIP-T-034). Sie trug zwei Korrelatoren,
nicht einen: die Absender-Adresse — und, seit beide Phasen in *einem* Klick laufen
(EIP-ADR-20260725-002), dieselbe **TCP-Verbindung**. Wer den
Socket sieht, verkettet Pseudonym und Stimme, ohne ein Feld zu lesen. Der zweite Korrelator ist
geschlossen: Eine Verbindung, die eine Identität getragen hat, endet mit ihrer Antwort; eine, die
nie eine trug, darf eine Stimme tragen. Dazu bleibt der Server kanalblind — über welchen Weg ein
Request kam, hält er nirgends fest, und ein Test hält das so. Nicht *gemessen*, ob zwei Requests
denselben Socket hatten: Das ginge nur, indem der Server Absender-Adresse und -Port vorhält, und
das verbietet § 1.

Was `offen` bleibt: der anonyme Kanal selbst — als **Option** neben dem normalen Weg, nicht als
einziger Weg → EIP-T-082, fällig vor Betriebsstufe `produktiv`.
Bis dahin gilt und wird so gesagt: Die Verbindungstrennung wirkt auf *unsere* Verbindung. Auf der
laufenden Instanz steht Renders Loadbalancer davor, sieht beide Phasen als eine Verbindung und die
IP ohnehin — dort ist die Maßnahme Voraussetzung, nicht Lösung. Und wenn der Kanal kommt, deckt er
nicht k = 10: Die wirksame Menge eines Kanalnutzers ist die Zahl der Stimmen aus demselben Kanal im
selben Batch. Bei einem einzelnen ist sie 1.

Der öffentliche Anker steht seit Version 17 (EIP-ADR-20260801-002,
EIP-T-006): Jede `batch_root(n)` wird bei zwei unabhängigen Diensten datiert — RFC 3161 und
OpenTimestamps/Bitcoin —, die Belege stehen öffentlich zum Download, und laufen lokale und bezeugte
Wurzel auseinander, ist das ein Befund im Debug-Modul und ein Banner auf der Board-Seite. Damit ist
das **rückwirkende Umschreiben** erledigt: Ein Betreiber, der ein altes Board ändert und die Kette
neu rechnet, bekommt für die neue Wurzel nur einen Zeitstempel von heute.

Was dieser Anker **nicht** leistet und was deshalb `offen` bleibt: **Split-View**. Wer von Anfang an
zwei Boards führt, lässt beide Wurzeln ehrlich datieren — ein Zeitstempel kann das prinzipiell nicht
aufdecken, dazu gehört Aufzählbarkeit durch unabhängige Gegenzeichner
→ EIP-T-036, fällig vor dem ersten echten Durchlauf (Betriebsstufe
`produktiv`). Die beiden Angriffe wurden hier bis Version 17 zusammen genannt; dass der Anker gegen
den zweiten hilft, war eine Ungenauigkeit dieses Paragraphen, keine Zusage der Umsetzung.

### § 3 Keine eigene Ausweis-Kryptografie

**Regel.** Wir implementieren keine eID-Kryptografie und keine Wahlprimitive selbst. Wir sind Nutzer
zertifizierter Komponenten und geprüfter Bibliotheken.

**Warum.** Die Kompetenz liegt nicht bei uns, die Prüfung ebenso wenig. Selbstgeschriebene Krypto ist der
klassischste Fehler in genau diesem Feld.

**Konkret verboten.** Eigene Implementierung von eID-Protokollteilen. Eigene RSA-Blindsignatur-Routinen.
Selbstgebaute Zufallsquellen. „Nur für den Prototyp" gilt als Begründung nicht, weil Prototypcode
weiterlebt.

**Status.** `bindend` — und **gerissen** (V-005, seit dem 2026-08-01 bekannt, im Betrieb seit
2026-07-27). Die Blindsignatur ist in ihren Kernschritten selbst geschrieben: EMSA-PSS-ENCODE, MGF1,
die Blinding-Arithmetik und die rohe RSA-Operation in `app/blind.py` und `static/blind.js`.
Zugekauft und geprüft sind SHA-384 und die PSS-Verifikation aus `cryptography`. Der Grund ist echt —
für Python existiert keine geprüfte RFC-9474-Umsetzung — und ändert am Status nichts: Bis eine
Bibliothek eintauschbar ist, gilt hier `Disziplin`, gedeckt durch die Testvektoren aus RFC 9474 A.4,
die Korrektheit belegen und Seitenkanalfreiheit nicht →
EIP-T-008, fällig vor Betriebsstufe `produktiv`.

Dass dieser Paragraph bis zum 2026-08-01 ohne Vermerk dastand, während der Code seine Abweichung im
eigenen Docstring benannte, ist der Befund — nicht die Abweichung selbst.

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

**Gezählt werden Paragraphen, nicht Vermerke.** Ein Paragraph mit drei Vermerken zählt einmal. Das
ist gewählt, nicht zufällig: Die Vermerksgrenze ist rein redaktionell — wer einen Absatz teilt,
erzeugt zwei Schulden, wer zwei zusammenschreibt, eine —, während die Paragraphengrenze nach § 17
nicht beiläufig verschiebbar ist. Die Kennzahl ist damit gegen Umformulieren robust und **blind
gegenüber Zuwachs und Abtrag innerhalb eines bereits belasteten Paragraphen**. Diese Blindheit ist
der Preis der Robustheit und wird hier einmal benannt, statt bei jedem Anlass neu erklärt zu werden.
Wer wissen will, was sich wirklich bewegt hat, liest die Tabelle, nicht die Zahl.

**Der Name bleibt.** „Schuldengrenze" sagt, was begrenzt wird — der Rückstand des Projekts —, und
der Satz darüber sagt, woran er gemessen wird. Ihn in „Paragraphengrenze" umzubenennen würde die
Messgröße zum Gegenstand machen und den Blick genau von dem wegführen, um den es geht.

**Warum.** Ein Projekt, das mit Vertrauen wirbt, wird an der Differenz zwischen „können wir nicht" und
„tun wir nicht" gemessen. Die Zusätze a) und b) stehen hier, weil die Kennzeichnungspflicht allein
einen Ausweg offenließ: Wer einen Text an den Ist-Zustand angleicht, hat diesem Paragraphen genügt,
ohne etwas gebaut zu haben (Herleitung: [Kodex-Protokoll](/kodex/protokoll), Version 3).

**Konkret verboten.** Formulierungen der Art „wir können nicht", wo tatsächlich „wir tun es nicht" gilt.
Aktuell betrifft das vor allem Ballot Stuffing: Solange eine Umfrage **läuft**, liegt ihr
Token-Signaturschlüssel bei uns allein, und wir könnten Phantom-Tokens signieren. Das ist Disziplin,
bis die Schwellensignatur steht — und wird so gesagt. Seit Version 17 gilt dasselbe für die externen
Zeitstempel (§ 2): Sie schließen das rückwirkende Umschreiben, nicht Split-View. Wo ein Anker
angezeigt wird, ist diese Grenze mitzunennen — ein Zeitstempel, der als Schutz gegen zwei parallel
geführte Boards dargestellt wird, ist eine Zusage, die der Mechanismus nicht hergibt. Ebenfalls
verboten: einen Vermerk auf `offen`
stehen lassen, ohne Ticket und Ereignis zu
nennen; die Grenze aus b) durch Umdeklarieren eines Features zu „Wartung" umgehen; die Grenze
anheben, statt eine Schuld abzutragen (das wäre eine Änderung nach § 17 und braucht deren Begründung).
Ebenfalls verboten, seit Version 22 ausdrücklich: **eine Schuld in einen bereits belasteten
Paragraphen umhängen.** Die Zahl fällt dabei um eins, ohne dass sich etwas ändert — und weil die
Bewegung im Fließtext eines Paragraphen stattfindet, ist sie von außen nicht als Umgehung erkennbar.
Eine Schuld gehört zu dem Paragraphen, dessen Zusage sie bricht; passt sie auf zwei, wird sie bei
beiden geführt und nicht bei dem billigeren.

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
geführt: öffentlicher Anker gegen Split-View (§ 2). Die Lizenzfrage aus § 20 ist seit dem 2026-08-01
beantwortet (AGPL-3.0-or-later) und keine Schuld mehr. Der Abgleich des
ausgelieferten Clients ist seit dem 2026-08-01 keine Disziplin mehr, sondern von außen messbar.

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
bestimmte Adresse gehen; die gibt es noch nicht. Der Weg dorthin steht seit dem 2026-08-01 fest — ein
eigenes Postfach bei einem Mailprovider, ohne eigene Domain und ohne die private Adresse des
Betreibers (Betreiberentscheidung, → EIP-T-073). Offen
ist damit nicht mehr die Frage, sondern nur die Einrichtung. Bis sie erfolgt ist, erreicht eine
Behörde das Projekt nur über den Betreiber persönlich, und der Transparenzbericht sagt das. Fällig ab
Betriebsstufe `produktiv`.

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

**Status.** `bindend`, und der zweite Satz ist technisch erzwungen: Es gibt keinen Weg, Frage oder
Optionen einer laufenden Umfrage zu ändern. Der **erste** ist `offen` — von den sechs Größen, die
vor dem Start feststehen müssen, kennt die App nur zwei (Frage, Antwortoptionen). Laufzeit, Nenner,
Veröffentlichungsschwelle und Auswertungsplan existieren im Datenmodell nicht (V-006) →
EIP-T-025, fällig vor Betriebsstufe `produktiv`. Ohne sie
gibt es nichts, woran eine nachträgliche Änderung sich messen ließe — die Präregistrierung schützt
dann eine Zusage, die nie gemacht wurde.

### § 8 Zahlen-Ehrlichkeit

**Regel.** Beteiligungsquote und benannter Nenner werden gleichrangig mit jedem Ergebnis veröffentlicht.
Wird die vorab festgelegte Schwelle nicht erreicht, erscheint kein Ergebnis — nur die Tatsache, dass die
Schwelle nicht erreicht wurde.

**Warum.** Der Nenner ist die eigentliche Innovation. Eine Zahl ohne ihn ist genau die Sorte Zahl, gegen
die wir angetreten sind.

**Konkret verboten.** Prozentwerte ohne absolute Zahlen. Ergebnisgrafiken, die die Quote kleiner setzen als
das Ergebnis. Veröffentlichung „nur intern" oder „nur für den Partner" unterhalb der Schwelle.
Zwischenstände während der Laufzeit über den reinen Teilnahmezähler hinaus.

**Status.** `bindend`. Eingelöst ist, was ohne Nenner einlösbar ist: Kein Prozentwert steht ohne
seine absolute Zahl, die Bezugsgröße wird an Ort und Stelle benannt, und einen Zwischenstand über
den Teilnahmezähler hinaus gibt es nicht (EIP-T-083). `offen` ist die Zusage selbst — es gibt weder
eine Beteiligungsquote noch einen benannten Nenner noch eine Schwelle, unterhalb derer kein Ergebnis
erscheint; der Prozentwert auf der Board-Seite bezieht das Ergebnis auf sich selbst (V-006) →
EIP-T-025, fällig vor Betriebsstufe `produktiv`. Bis
dahin sagt der Ergebnisblock selbst, dass ihm der Nenner fehlt: Eine Zahl ohne ihn ist nach dem
*Warum* dieses Paragraphen genau die Sorte Zahl, gegen die das Projekt angetreten ist — auch in
einer Vorführung.

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

Ebenfalls `offen` und bis zum 2026-08-01 unbemerkt: die **Hinweispflicht am Ergebnis**. Der
Ergebnisblock der Board-Seite nennt die eID-Verfügbarkeit als Zugangsvoraussetzung nicht — der
Paragraph verlangt sie ausdrücklich „bei jedem Ergebnis, nicht nur im Manifest" (V-006, derselbe
Sachverhalt wie bei § 7 und § 8) → EIP-T-025, fällig vor
Betriebsstufe `produktiv`. Die Ausschlusswirkung gehört an die Zahl, weil sie sonst genau dort
fehlt, wo jemand die Zahl weiterträgt.

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

Die **Zwischenregel** dieses Paragraphen — neutrale Formulierung, immer eine Enthaltungsoption,
Veröffentlichung abgelehnter Vorschläge — gilt schon jetzt. Von ihren drei Zusagen ist eine seit dem
2026-08-01 **erzwungen**: Die Umfrageanlage weist eine Antwortliste ab, in der keine Option genau
`Enthaltung`, `Weiß nicht` oder `Weiss nicht` heißt; die Abweisung nennt diesen Paragraphen und steht
im Debug-Modul (EIP-T-085). Geprüft wird auf feste Texte statt auf
ein enthaltenes Wort — sonst hätte jede Umbenennung die Regel ausgehebelt —, und der feste Text ist
zugleich die einzige Form, die ein Dritter am veröffentlichten `POLL_OPEN`-Eintrag nachrechnen kann.

Die beiden anderen Zusagen bleiben `Disziplin`: Neutralität einer Formulierung ist maschinell nicht
prüfbar, und die Veröffentlichung abgelehnter Vorschläge setzt einen Eingangsweg für Vorschläge
voraus, den es nicht gibt — beides gehört zur Übergabe an das Gremium →
EIP-T-022, fällig vor der ersten Frage außerhalb einer Vorführung.
Bis dahin gelten sie, werden aber durch nichts als unser Verhalten gedeckt (§ 4).

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
eingesetzt, nicht als Wahl, nicht als Volksentscheid, nicht als Betriebsrats- oder Vereinswahl. Wir binden
Einbetter über Nutzungsbedingungen für Einbetter daran, nicht nur über ein Bekenntnis — und sagen dabei, was
dieses Instrument ist: ein Entzugsrecht im Nachhinein, keine technische Verhinderung. Wozu jemand ein
Ergebnis verwendet, sehen wir nicht.

**Warum.** Uns fehlen die Schutzmechanismen des Wahlrechts, allen voran die Nötigungsresistenz: Unsere
individuelle Verifizierbarkeit ist zugleich eine vorzeigbare Quittung. Das ist eine bewusste
Architekturentscheidung — und sie schließt jeden Wahleinsatz aus.

**Konkret verboten.** Vermarktung als Wahlsystem. Kooperationen, deren Zweck eine bindende Abstimmung ist.
Stillschweigende Duldung, wenn ein Einbetter das Widget so einsetzt.

**Status.** `bindend`. Die Nutzungsbedingungen für Einbetter liegen seit dem 2026-08-01 vor (Version 13) und
enthalten das Verbot, die Nennerpflicht,
die Rechtsfolge und die Aufstellung, was davon erzwingbar ist. Was fehlt, ist nicht mehr der Text,
sondern der Griff: Solange es keine Einbettung gibt, gibt es keinen Zugang, der entzogen werden
könnte. `offen` bleibt deshalb die Vergabe und der Entzug der Einbettungserlaubnis →
EIP-T-023, fällig mit der ersten Einbettung durch Dritte, spätestens
vor Betriebsstufe `produktiv`. Das Widget darf nicht ausgeliefert werden, bevor dieser Weg steht.

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

**Status.** `bindend` und seit dem 2026-08-01 in beiden Teilen eingelöst. Reproduzierbarer Build,
Hash-Veröffentlichung und Prüfanleitung stehen (Version 14 im [Kodex-Protokoll](/kodex/protokoll)); die Lizenz aus
dem ersten Satz steht seit Version 19: **AGPL-3.0-or-later**, Volltext als `LICENSE` im App-Repo,
Begründung in dessen `README.md` (EIP-T-078, Verstoß V-004
damit behoben). Gewählt wurde nicht permissiv, weil der Paragraph *Weiterbetrieb* zusagt und zugleich
verbietet, einen abweichenden Client auszuliefern: Die Netzwerk-Klausel der AGPL bindet beides
aneinander — wer eine veränderte Fassung öffentlich betreibt, schuldet deren Quellcode den Nutzern
seiner Instanz. Unter MIT oder Apache dürfte er still abweichen, unter der gewöhnlichen GPL ebenso,
weil Serverbetrieb keine Weitergabe ist.

Was die Lizenz nicht leistet: Sie bindet niemanden an diesen Kodex. Ein fremder Betreiber schuldet
seinen Nutzern den Code, nicht die Regeln — die Bindung des Regelwerks an einen Nachfolger ist § 14
und offen.

**Der Client ist nachrechenbar, und zwar ohne diesen Server zu fragen.** Aller Client-Code liegt
unverändert unter `/static/` — nicht gebündelt, nicht minifiziert; ein Build-Schritt, der
reproduzierbar sein müsste, existiert nicht. Ausführbaren Inline-Code in den Seiten gibt es seit dem
2026-08-01 keinen mehr, denn er stünde in der gerenderten Seite und wäre mit keiner Repo-Datei
vergleichbar — ein Hash über `static/` hätte seine Abwesenheit dann nur vorgetäuscht. `/version`
nennt jede Client-Datei mit ihrem Hash, die Nachweis-Seite jeder Umfrage zeigt Liste und Prüfbefehl,
`app/DOKU.md` und `app/DEPLOY.md` beschreiben den Weg. Entscheidend ist, was der Vergleich
vergleicht: die abgerufene Datei gegen das öffentliche Repository. Beide Größen stammen aus
verschiedenen Quellen, keine aus einer Behauptung dieser App — anders als beim `treehash`, der eine
Selbstauskunft bleibt. Ein Rückfall zu Inline-Code meldet sich selbst als Inkonsistenz im
Debug-Modul.

Was auch das nicht leistet, weil § 4 es verlangt: Es entlarvt eine Auslieferung, die **für alle**
vom veröffentlichten Stand abweicht, nicht eine, die ausgerechnet einem einzelnen Besucher anderen
Code schickt. Dagegen hilft nur, dass mehrere unabhängig abrufen und vergleichen — dieselbe Struktur
wie beim Split-View-Problem des Boards (§ 2) und mit denselben Grenzen. Und es hilft niemandem, der
nicht nachrechnet; vollständig gelöst wäre es erst mit signierter App statt Web-Code.

Die Übereinstimmung von Repository und Auslieferung ist seit dem 2026-08-01 (Stand `ec1044d`)
**feststellbar statt behauptet**: Die Instanz weist ihren Stand unter `/version` aus — benannter Commit und ein Hash über die Dateien, die sie
tatsächlich ausliefert —, und `app/DEPLOY.md` beschreibt den Prüfweg dorthin in zwei Befehlen, die
ohne Rückfrage bei uns auskommen. Damit ist die Fälligkeit dieser Betriebsstufe erfüllt: Sie verlangt
nicht, dass keine Abweichung entsteht, sondern dass eine entstandene auffällt. Ein Commit, der hier
liegen bleibt, ist ab sofort ein Befund im Debug-Modul und im Abgleich vor jeder Veröffentlichung,
kein stiller Zustand mehr wie bei V-001.

Was daran Selbstauskunft bleibt: der `treehash` über den **gesamten** Stand, Server-Code
eingeschlossen. Welchen Python-Code ein fremder Container ausführt, kann von außen niemand messen —
wer ihn ändert, kann diese Antwort mit ändern. Für den Teil, an dem das Wahlgeheimnis hängt, ist das
seit dem 2026-08-01 nicht mehr nötig (siehe oben); für den Rest bleibt es Disziplin, und dagegen hilft
keine Zeile in diesem Paragraphen, sondern erst ein Betrieb, der nicht allein bei uns liegt (§ 4,
EIP-T-040).

---

## Schuldenübersicht

Alle Paragraphen, die ganz oder teilweise auf `offen` oder `Disziplin` stehen. Die Liste ist
abgeleitet, nicht eigenständig: Maßgeblich ist der Status beim jeweiligen Paragraphen.
`scripts/check_kodex.py` prüft, dass beide übereinstimmen und dass kein Vermerk ohne Ticket und
Ereignis dasteht. Was die Zahl darunter zählt und was sie dabei nicht sieht, steht in § 4 b und
nicht hier.

**Stand 2026-08-01: 13 von 20 Paragraphen. Die Grenze aus § 4 b liegt bei 8 — sie ist überschritten,
der Baustopp gilt.**

Version 20 ist der größte Sprung, den diese Zahl je gemacht hat, und **kein einziger Vermerk
beschreibt einen neuen Zustand**: § 3, § 7 und § 8 kommen hinzu, § 11 und § 12 bekommen einen
zweiten Halbsatz — gefunden im ersten vollständigen Durchgang durch die bindenden Sätze
(EIP-AUD-20260801-004, Anlass war V-004). Vier bindende Sätze waren
nicht eingelöst, drei davon seit dem ersten Tag des öffentlichen Betriebs (V-005, V-006). Die Zahl
war vorher falsch, nicht die Lage besser. Wer 10 gelesen hat, hat ein Maß für Aufmerksamkeit
gelesen, nicht für Rückstand — und genau das ist der Grund, warum der Durchgang selbst ein
Verfahren braucht → EIP-T-084.

Version 19 nimmt § 20 aus dieser Liste: Der Code steht seit dem 2026-08-01 unter AGPL-3.0-or-later,
Prüfung **und** Weiterbetrieb sind eingeräumt (EIP-T-078,
V-004 behoben). Damit sinkt die Zahl zum ersten Mal seit Version 9 — und ausgerechnet an dem
Paragraphen, der seinen Vermerk erst vier Versionen zuvor bekommen hatte, weil ein `bindend`er Satz
nie geprüft worden war. Der Befund darüber (Ein Satz auf `bindend` steht in keiner Prüfung) ist mit
der Lizenz **nicht** erledigt; er gehört zu keinem Paragraphen und taucht deshalb in dieser Tabelle
auch jetzt nicht auf → EIP-T-084.

Version 15 löst den dritten Vermerk unter § 2 auf: Die Mindestmenge zählt jetzt Stimmen und ist
damit die Zahl, die sie zu sein behauptet (EIP-T-076). Die Zahl
oben bleibt trotzdem bei 11, weil § 2 zwei weitere Vermerke trägt — dieselbe Schwäche der Kennzahl
wie bei ihrer Entstehung in Version 12, nur in die andere Richtung: Damals verschwieg sie einen neuen
Befund, jetzt verschweigt sie gebaute Arbeit.

Die Zahl steht seit Version 9 unverändert, obwohl § 10 mit Version 10 herausfällt: § 5 tritt an
seine Stelle. Der Offenlegungsweg ist gebaut, der Eingangskanal für Behördenanfragen ist es nicht —
das war die bewusste Entscheidung, keine private Adresse dauerhaft an das Projekt zu binden
(EIP-T-063). Ein Tausch, kein Abtrag.

Mit Version 12 kommt ein dritter Vermerk unter § 2 hinzu, ohne dass die Zahl steigt — § 2 war
bereits belastet. **Das ist die Blindheit der Kennzahl, keine Entwarnung** (seit Version 22 in § 4 b
selbst benannt und begründet). Der neue Vermerk ist keine kleine Ergänzung, sondern der Befund, dass
die Mindestmenge aus der Regel von § 2 heute nicht existiert. Wer nur auf die 11 sieht, hält den
2026-07-31 für einen Tag ohne Veränderung.

Version 14 lässt die Zahl zum zweiten Mal in Folge stehen, und zum zweiten Mal aus einem Grund, den
die Zahl verschweigt: § 20 hat seine Schuld eingelöst — der Client ist nachrechenbar, ohne diese
Instanz zu fragen — und trägt trotzdem weiter einen Vermerk, weil beim Nachsehen auffiel, dass der
**erste** Satz des Paragraphen nie erfüllt war. Es gibt keine Lizenz. Der Fund ist die eigentliche
Nachricht dieser Version: Ein Satz auf `bindend` steht nicht in der Schuldenübersicht und wird
deshalb auch nicht geprüft — er gilt als erledigt, weil er nie als offen markiert wurde. Wer wissen
will, wo noch solche Sätze stehen, findet sie nicht in dieser Tabelle.

Version 13 ändert die Zahl ebenfalls nicht, und auch hier lohnt der Blick auf den Grund: § 16 hat
seinen Text bekommen (Nutzungsbedingungen für Einbetter), aber nicht seinen Griff. Ein Regelwerk ohne
entziehbaren Zugang trägt die Schuld nicht ab, es verschiebt sie an die Stelle, wo sie hingehört —
das Widget. Wer sie hier als erledigt geführt hätte, hätte einen Paragraphen freigekauft, indem er
ein Dokument schreibt.

| § | Was offen ist | Ticket | Fällig vor | Seit |
|---|---|---|---|---|
| 1 | Protokollierung beim Hoster (Loadbalancer, TLS-Endpunkt, Cloudflare) — belegt, dass sie stattfindet; Umfang und Frist offen. Die eigene Seite ist erledigt | EIP-T-075 | `öffentlich erreichbar` | 2026-07-26 |
| 2 | Split-View: zwei parallel geführte Boards. Der Zeitanker steht seit 2026-08-01 (EIP-T-006) und schließt das rückwirkende Umschreiben; Equivocation deckt er prinzipiell nicht auf, dazu braucht es Gegenzeichner | EIP-T-036 | `produktiv` | 2026-07-26 |
| 2 | Netzwerkebene: anonymer Zustellkanal als Option. Entschieden und zur Hälfte gebaut (Verbindungstrennung, Kanalblindheit, EIP-T-034); der Kanal selbst ist eine Betriebsentscheidung und hängt an der Hosterfrage | EIP-T-082 | `produktiv` | 2026-08-01 |
| 3 | Blindsignatur in ihren Kernschritten selbst geschrieben (EMSA-PSS-ENCODE, MGF1, Blinding-Arithmetik, rohe RSA-Operation), weil es für Python keine geprüfte RFC-9474-Bibliothek gibt. Gedeckt durch die RFC-Testvektoren — Korrektheit, nicht Seitenkanäle. Verstoß V-005 | EIP-T-008 | `produktiv` | 2026-08-01 |
| 4 | Ballot Stuffing bleibt Disziplin **während der Laufzeit** (Schlüssel liegt allein bei uns; nach Schließung vernichtet, EIP-T-069) | EIP-T-040 | `produktiv` | 2026-07-26 |
| 5 | Eigener Eingangskanal für Behördenanfragen — Bauform entschieden (Postfach ohne Domain), Einrichtung offen | EIP-T-073 | `produktiv` | 2026-07-31 |
| 6 | DSGVO-Kollision entschieden und begründet | EIP-T-061 | `produktiv` | 2026-07-26 |
| 7 | Von den sechs Größen, die vor dem Start feststehen müssen, kennt die App zwei. Laufzeit, Nenner, Veröffentlichungsschwelle und Auswertungsplan gibt es im Datenmodell nicht. Verstoß V-006 | EIP-T-025 | `produktiv` | 2026-08-01 |
| 8 | Keine Beteiligungsquote, kein benannter Nenner, keine Schwelle — der Prozentwert auf der Board-Seite bezieht das Ergebnis auf sich selbst. Verstoß V-006 | EIP-T-025 | `produktiv` | 2026-08-01 |
| 11 | eAT-Unterstützung, Barrierefreiheit | EIP-T-064 | `produktiv` | 2026-07-26 |
| 11 | Hinweispflicht am Ergebnis: Die Ergebnisdarstellung nennt die eID-Verfügbarkeit als Zugangsvoraussetzung nicht. Verstoß V-006 | EIP-T-025 | `produktiv` | 2026-08-01 |
| 12 | Übergabe der Fragehoheit an ein unabhängiges Gremium | EIP-T-022 | politische Relevanz, spät. `produktiv` | 2026-07-26 |
| 12 | Zwischenregel bis zur Übergabe: die Enthaltungsoption ist seit dem 2026-08-01 erzwungen (EIP-T-085); neutrale Formulierung und Veröffentlichung abgelehnter Vorschläge bleiben Disziplin — das eine ist maschinell nicht prüfbar, das andere braucht einen Eingangsweg für Vorschläge | EIP-T-022 | erste Frage außerhalb einer Vorführung | 2026-08-01 |
| 13 | Finanzierungsmodell im Detail | EIP-T-026 | erste Annahme von Geld | 2026-07-26 |
| 14 | Rechtsform und Nachfolgebindung | EIP-T-065 | `produktiv`, jed. vor Trägerwechsel | 2026-07-26 |
| 16 | Vergabe und Entzug der Einbettungserlaubnis. Die Nutzungsbedingungen selbst stehen seit 2026-08-01 (EIP-T-062); ohne Einbettung gibt es keinen Zugang, den ein Verstoß kosten könnte | EIP-T-023 | erste Einbettung, spät. `produktiv` | 2026-07-26 |

Drei Fälligkeiten hängen an der Betriebsstufe `öffentlich erreichbar`, die seit dem 2026-07-27 läuft.
Stand 2026-08-01:

- **§ 20** — der Nachprüfbarkeits-Teil ist erfüllt, und seit dem 2026-08-01 auch für die Stelle, an
  der das Wahlgeheimnis hängt: Die Instanz weist ihren Stand unter `/version` aus (EIP-T-074), und
  der Client lässt sich Datei für Datei gegen das Repository halten, **ohne diese Antwort zu
  benutzen** (EIP-T-007). Zwischen einer Änderung hier und ihrem Deploy zeigt die Instanz weiterhin
  einen älteren Stand — das ist keine Abweichung, sondern der Weg dorthin; neu ist, dass es
  **sichtbar** ist statt still.
  **Der andere Teil desselben Paragraphen ist seit dem 2026-08-01 nachgezogen**: Der Code steht unter
  AGPL-3.0-or-later, Weiterbetrieb ist eingeräumt und an die Pflicht gebunden, eine veränderte
  öffentlich betriebene Fassung offenzulegen (V-004 behoben,
  EIP-T-078). Damit ist § 20 als einziger der drei
  Fälligkeiten dieser Stufe vollständig erfüllt — und war es an dem Tag, an dem er zum ersten Mal
  vollständig gelesen wurde
- **§ 10** — erfüllt: Kodex, Verstoßprotokoll und Transparenzbericht sind auf der Instanz ohne
  Anmeldung erreichbar (Version 10, EIP-T-063)
- **§ 1** — weiterhin nur teilweise, aber die Hälfte steht: Dass die App keine IPs mehr
  protokolliert, ist seit dem 2026-07-31 **am wirksamen Ort belegt** — der Startbefehl der Instanz
  trägt `--no-access-log`, und über dutzende Anfragen fällt keine Zugriffszeile an (V-002 damit
  geschlossen). Der gesamte übrige Anfall auf unserer Seite ist am 2026-07-31 erhoben und je Position
  auf Notwendigkeit geprüft (`EIP-RPT-20260731-002`). Was Renders Loadbalancer und TLS-Endpunkt
  daneben mitschreiben, erscheint im Container-Log gar nicht — und ist seit dem 2026-07-31 nicht
  mehr bloß unbekannt: Render sagt vertraglich zentrale Infrastruktur-Protokollierung zu, ohne
  Umfang und Frist zu nennen. Offen ist die Auskunft darüber, nicht mehr die Existenz →
  EIP-T-075.
  **Gerissen, seit die Stufe läuft** — und nach der Behebung von V-004 wieder die einzige. Dass die
  fehlende Lizenz keinen vollen Tag in dieser Liste stand, ändert nichts daran, dass sie seit dem
  2026-07-27 fällig war: Der Verstoß zählt ab dem Deploy, nicht ab dem Bemerken

Die Spalte *Seit* nennt das Datum der Kodex-Version, in der der Vermerk zuerst stand, nicht das
Datum dieser Übersicht. Ein Vermerk wird durch die Aufnahme hier nicht jünger.

---

Änderungen und Verstöße: [Kodex-Protokoll](/kodex/protokoll) (§ 17, § 18).
