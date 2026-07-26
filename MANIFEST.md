<!-- Erzeugt von scripts/sync_manifest.py aus MANIFEST.md im Elternordner.
     Nicht hier bearbeiten - Aenderungen gehoeren ins Original. -->
# Manifest

**Wir bauen einen Ort, an dem sich zeigen lässt, was die Menschen in diesem Land wirklich denken — so, dass niemand es wegdiskutieren kann.**

## Das Problem

Es gibt keinen Mangel an Umfragen. Es gibt einen Mangel an Umfragen, denen jemand glaubt.

**Institute** befragen tausend Menschen und rechnen hoch. Methodisch sauber, aber die Gewichtung ist die eigentliche Aussage, und sie ist nicht nachprüfbar. Wer bezahlt, wählt die Frage.

**Websites** befragen ihre eigenen Leser. Eine Umfrage auf einem Boulevardportal misst Boulevardleser, eine auf einem linken Blog misst dessen Publikum. Beide messen korrekt — nur eben nicht das Land. Und weil niemand prüft, wer abstimmt, stimmt ab, wer will: so oft er will, notfalls automatisiert.

**Die Folge:** Jedes Ergebnis ist bestreitbar. Und solange jedes Ergebnis bestreitbar ist, muss sich niemand dazu verhalten. Der Zweifel an der Zahl ist der bequemste Ausweg aus der Rechenschaft — und Politik nutzt ihn, völlig zu Recht, weil die Zahlen es hergeben.

Wir halten das für den Kern des Problems: Nicht dass niemand fragt. Sondern dass die Antworten folgenlos bleiben dürfen.

## Was wir dagegen bauen

Eine einzige Umfrage-Instanz, die drei Dinge zusammenbringt, die es bisher nur getrennt gibt:

**Ein Ausweis, eine Stimme.** Authentifizierung über den Online-Ausweis. Keine Bots, keine Zweitaccounts, keine Mehrfachstimmen — keine Heuristik, die man umgehen kann, sondern eine harte kryptografische Schranke. Wir sagen bewusst „ein Ausweis" und nicht „ein Mensch": Das Pseudonym hängt am Chip, nicht an der Person. Wer einen neuen Ausweis bekommt, bekommt ein neues Pseudonym. Das ist die genaue Reichweite der Zusage, und wir formulieren sie lieber selbst, als sie uns vorhalten zu lassen.

**Trotzdem geheim.** Wir wissen, *dass* du abgestimmt hast, und wir wissen, *was* abgestimmt wurde. Wir können beides nicht verbinden — auch nicht, wenn wir wollten. Das ist keine Zusage, der man vertrauen muss, sondern Mathematik: deine Stimme wird blind signiert, wir sehen sie nie.

**Öffentlich nachzählbar.** Jede Stimme steht in einem öffentlichen Register. Jeder kann das Ergebnis selbst nachrechnen. Jeder kann die eigene Stimme wiederfinden. Wir bitten niemanden, uns zu glauben.

## Warum das etwas ändert

Weil zum ersten Mal ein **Nenner** existiert.

„12.000 Leser haben abgestimmt" heißt nichts — von wie vielen? Und wie viele davon waren dieselbe Person?

„12.000 von M Berechtigten, jeder genau einmal, öffentlich nachgezählt" ist eine andere Art von Satz. Was darin steht, ist gezählt und nicht geschätzt: keine Stichprobe, keine Hochrechnung, kein Gewichtungsmodell.

Wir behaupten trotzdem nicht, dass diese Zahl unangreifbar ist. Ein Einwand bleibt, und er ist berechtigt: Wer bei uns abstimmt, hat sich dafür entschieden. Unsere Teilnehmenden sind nicht das Land. Diesen Einwand können wir nicht ausräumen, und wir versuchen es auch nicht — dafür müssten wir Daten über unsere Teilnehmenden erheben, die wir bewusst nicht erheben.

Was bleibt, gibt es trotzdem bisher nirgends: eine **untere Schranke**. Mindestens N verifizierte Menschen in diesem Land sagen X — jeder genau einmal, öffentlich nachzählbar. Dieser Satz gilt unabhängig davon, wer erschienen ist. Er ist bescheidener als „so denkt Deutschland", und er ist dafür wahr.

Gegen eine solche Zahl kann man sich entscheiden. Das ist legitim — wir leben in einer repräsentativen Demokratie, und niemand muss einer Mehrheit folgen. Aber man muss es dann **sichtbar** tun, und man muss es begründen. Genau das ist unser Ziel: nicht Bindung, sondern Begründungslast.

## Warum viele Seiten, ein Ergebnis

Identitätsprüfung allein macht eine Umfrage nicht repräsentativ. Wer teilnimmt, entscheidet weiter jeder selbst.

Deshalb ist unsere Instanz einbettbar: dieselbe Frage auf dem Boulevardportal, in der überregionalen Zeitung, beim Fachverband, auf der Gemeindeseite, im linken Blog — aber **ein gemeinsamer Topf**, in dem jeder Ausweis genau einmal liegt. Wer sein Publikum mobilisiert, holt sein Publikum, einmal.

Damit wird die Teilnehmerschaft **breiter**. Sie wird nicht neutral: Eine Summe verschieden gefärbter Publika ist keine Bevölkerung, und wie die Mischung ausfällt, entscheidet nicht die Bevölkerungsstruktur, sondern wer wie stark mobilisiert. Wir behaupten hier also keinen Ausgleich der Verzerrung, sondern ihre Verbreiterung — das ist weniger, aber es ist wahr.

Und wir treten dabei **ergänzend auf, nicht ersetzend**: Wer eine eigene Umfrage betreibt, betreibt sie weiter. Unsere kommt daneben — als die Zahl, die auch außerhalb des eigenen Publikums zitierfähig ist.

Das kann heute niemand, und zwar aus einem prinzipiellen Grund: Ohne Deduplizierung sind zwei Umfragen nicht zusammenführbar. Mit ihr sind sie es.

Das Vollbild — eine Instanz, auf die sich alle einigen — ist ein Zielbild, kein Mechanismus, der von selbst greift. Es setzt Reichweite voraus, die wir heute nicht haben.

## Wofür wir uns verbürgen

- **Wir fragen nur das Pseudonym ab.** Keinen Namen, kein Geburtsdatum, keine Adresse. Wir könnten mehr, wir wollen nicht.
- **Wir schreiben keine eigene Ausweis-Kryptografie.** Niemals. Wir sind Nutzer zertifizierter Komponenten, nicht ihr Erfinder.
- **Wir veröffentlichen unseren Code.** Wer prüfen will, was in seinem Browser läuft, muss es prüfen können.
- **Wir veröffentlichen die Beteiligungsquote immer mit** — auch wenn sie niedrig ist. Besonders dann.
- **Wir sagen, was wir nicht können,** bevor jemand anders es findet.

## Was wir nicht sind

Wir halten diesen Abschnitt für den wichtigsten des Dokuments. Ein Projekt, das mit Vertrauen wirbt, verliert es genau hier zuerst.

**Kein Volksentscheid.** Unsere Ergebnisse haben keine Rechtswirkung. Sie erzeugen Öffentlichkeit, sonst nichts.

**Kein Ersatz für Wahlen.** Es fehlen die Schutzmechanismen des Wahlrechts. Vor allem eines: Wer neben dir steht, während du abstimmst, kann dich beeinflussen, und unsere individuelle Nachprüfbarkeit ist zugleich eine Quittung, die man vorzeigen kann. Das ist eine bewusste Entscheidung gegen ein Verfahren, das nirgends auf der Welt produktiv funktioniert — und es schließt jeden Einsatz als Wahl aus.

**Kein Ersatz für Meinungsforschung.** Institute liefern Zeitreihen und Untergruppenanalysen, die wir nicht liefern. Wir liefern eine Sache, die sie nicht liefern können. Andere Gattung, nicht bessere Version.

**Nicht repräsentativ im statistischen Sinn.** Wer teilnimmt, wählt sich selbst aus. Heute ist unsere mögliche Teilnehmerschaft zusätzlich jünger, männlicher, städtischer und höher gebildet als das Land, weil die Online-Ausweisfunktion so verteilt ist. Wir sagen deshalb nie „die Bevölkerung denkt X", sondern immer „von den Teilnehmenden — N von M Berechtigten — denken X".

## Wo wir stehen

Ehrlich: am Anfang, und mit einem harten Deckel über dem Kopf.

Rund **18 Prozent** der Erwachsenen haben die Online-Ausweisfunktion aktiviert *und* kennen ihre PIN. Das ist die reale Obergrenze der Beteiligung, nicht die Zahl der Ausweisinhaber. Eine Beteiligung von 80 Prozent ist ein Mehrjahresziel, kein Startzustand, und wir werden das in keiner Zahl verschweigen, die wir veröffentlichen.

Was existiert: eine lauffähige Anwendung mit Blindsignaturen, zwei getrennten Registern und öffentlichem Bulletin Board. Was fehlt: die Anbindung an den echten eID-Flow.

## Warum wir trotzdem anfangen

Weil der Deckel selbst das zweite Ziel ist.

Die Online-Ausweisfunktion wird nicht genutzt, weil es zu wenig Gründe gibt, sie zu nutzen. Alles, was es bisher gibt, ist Pflicht: Steuererklärung, Kfz-Zulassung, Rentenauskunft. Niemand richtet eine PIN ein aus Vorfreude auf ein Formular.

Seine Meinung zu sagen ist keine Pflicht. Es ist freiwillig, es wiederholt sich, man kann darüber reden, und man sieht sofort, was es bewirkt hat. Das ist der erste Grund, die eID einzurichten, der Spaß macht.

Und weiter: 21 Prozent haben die Funktion bereits aktiviert und nur die PIN vergessen — ein Schritt, kein Behördengang. Der kostenlose Rücksetzdienst des Bundes startet in der zweiten Jahreshälfte 2026 neu.

Wir sind also nicht nur Leidtragende der niedrigen Verbreitung. Wir sind ein Grund, sie zu ändern.

## Was uns selbst gefährlich werden kann

Die Kryptografie schützt die Auszählung. Sie schützt nicht die **Frage**.

Wer formuliert, wer die Antwortmöglichkeiten festlegt, wer den Zeitpunkt wählt und wer entscheidet, welche Fragen überhaupt gestellt werden, hat mehr Macht über das Ergebnis als jeder denkbare Manipulator — legal und unsichtbar. Eine Instanz, die groß genug wird, um politisch zu zählen, ist damit selbst eine Machtkonzentration. Es wäre absurd, dem Meinungsforschungsauftraggeber diese Macht zu nehmen, um sie uns selbst zu geben.

Wir haben dafür noch keine fertige Antwort. Wir halten die Frage für wichtiger als unser Wachstum, und wir werden sie beantworten, bevor die Instanz groß genug ist, dass sie zählt — nicht danach.

Zwei Dinge sagen wir schon jetzt zu: Wir machen kein Spiel aus dem Abstimmen. Keine Punkte, keine Serien, keine Belohnung für Menge — das erzeugt Klicks statt Meinungen und liefert jedem Kritiker die Munition frei Haus. Und wir werden nicht wachsen, indem wir die Fragen stellen, die am meisten aufregen. Das wäre exakt die Parteilichkeit, die wir anderen vorwerfen.

## Woran wir uns messen lassen

1. Läuft der vollständige Ablauf mit einem echten Ausweis?
2. Ist die Beteiligungsquote bei jedem Ergebnis sichtbar — auch bei einer schlechten?
3. Kann jemand außerhalb unseres Projekts das Ergebnis nachrechnen, ohne uns zu fragen?
4. Ist die Entscheidung, welche Fragen gestellt werden, aus unserer Hand?
5. Haben Menschen wegen uns ihre eID aktiviert?
