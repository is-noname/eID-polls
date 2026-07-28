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

**Ein Ausweis, eine Stimme.** Authentifizierung über den Online-Ausweis. Keine Bots, keine Zweitaccounts, keine Mehrfachstimmen — keine Heuristik, die man umgehen kann. Wir sagen „ein Ausweis" und nicht „ein Mensch": Das Pseudonym hängt am Chip, nicht an der Person. Neuer Ausweis, neues Pseudonym. Und heute hindert uns nichts außer uns selbst daran, zusätzliche Tokens auszustellen — der Signaturschlüssel liegt bei uns allein. Bis die Schwellensignatur steht, ist das Disziplin, keine Schranke (§ 4).

**Trotzdem geheim.** Wir wissen, *dass* du abgestimmt hast, und wir wissen, *was* abgestimmt wurde. Was in deiner Stimme steht, sehen wir dabei nie: Sie wird blind signiert, bevor wir sie zu Gesicht bekommen. Das ist Mathematik.

Die beiden einander zuzuordnen ist eine andere Frage, und dort sind wir noch nicht fertig. Wer Anmeldung und Stimme beide entgegennimmt, sieht beide Vorgänge zu ihrer Zeit — das lässt sich nicht wegrechnen, sondern nur durch einen zweiten Beteiligten aufheben. Solange alles bei uns zusammenläuft, hängt deine Anonymität daran, dass wir nicht auswerten, was wir sehen könnten. Das ist Disziplin, keine Schranke (§ 4). Woran wir arbeiten, steht öffentlich: erst eine Speicherung, die die Reihenfolge nicht mehr hergibt, danach ein unabhängiger Dritter.

**Öffentlich nachzählbar.** Jede Stimme steht in einem öffentlichen Register. Jeder kann das Ergebnis nachrechnen und die eigene Stimme wiederfinden. Wir bitten niemanden, uns zu glauben.

## Warum das etwas ändert

Weil zum ersten Mal ein **Nenner** existiert.

„12.000 Leser haben abgestimmt" heißt nichts — von wie vielen? Und wie viele davon waren dieselbe Person?

„12.000 von M Berechtigten, jeder genau einmal, öffentlich nachgezählt" ist eine andere Art von Satz. Was darin steht, ist gezählt und nicht geschätzt: keine Stichprobe, keine Hochrechnung, kein Gewichtungsmodell.

Wir behaupten trotzdem nicht, dass diese Zahl unangreifbar ist. Ein Einwand bleibt, und er ist berechtigt: Wer bei uns abstimmt, hat sich dafür entschieden. Unsere Teilnehmenden sind nicht das Land. Diesen Einwand können wir nicht ausräumen, und wir versuchen es auch nicht — dafür müssten wir Daten über unsere Teilnehmenden erheben, die wir bewusst nicht erheben.

Was bleibt, gibt es trotzdem bisher nirgends: eine **untere Schranke**. Mindestens N verifizierte Menschen in diesem Land sagen X — jeder genau einmal, öffentlich nachzählbar. Dieser Satz gilt unabhängig davon, wer erschienen ist. Er ist bescheidener als „so denkt Deutschland", und er ist dafür wahr.

Gegen eine solche Zahl kann man sich entscheiden. Das ist legitim — wir leben in einer repräsentativen Demokratie, und niemand muss einer Mehrheit folgen. Aber man muss es dann **sichtbar** tun, und man muss es begründen. Genau das ist unser Ziel: nicht Bindung, sondern Begründungslast.

## Warum viele Seiten, ein Ergebnis

Identitätsprüfung macht eine Umfrage nicht repräsentativ. Wer teilnimmt, entscheidet weiter jeder selbst.

Deshalb ist unsere Instanz einbettbar: dieselbe Frage auf dem Boulevardportal, in der überregionalen Zeitung, beim Fachverband, im linken Blog — aber **ein gemeinsamer Topf**, in dem jeder Ausweis genau einmal liegt. Wer sein Publikum mobilisiert, holt sein Publikum, einmal. Das kann heute niemand, aus einem prinzipiellen Grund: Ohne Deduplizierung sind zwei Umfragen nicht zusammenführbar.

Damit wird die Teilnehmerschaft **breiter**, nicht neutral. Eine Summe gefärbter Publika ist keine Bevölkerung, und die Mischung entscheidet nicht die Bevölkerungsstruktur, sondern wer stärker mobilisiert. Wir behaupten also keinen Ausgleich der Verzerrung, sondern ihre Verbreiterung. Das ist weniger, aber wahr.

Einbetten heißt nicht mitgestalten: Die Beteiligungsquote lässt sich nicht abschalten, und die Nutzungsbedingungen schließen bindende Abstimmungen aus (§ 9, § 16). Wir treten **ergänzend auf, nicht ersetzend** — wer eine eigene Umfrage betreibt, betreibt sie weiter. Unsere kommt daneben, als die Zahl, die auch außerhalb des eigenen Publikums zitierfähig ist.

Das Vollbild — eine Instanz, auf die sich alle einigen — ist ein Zielbild, kein Selbstläufer. Es setzt Reichweite voraus, die wir heute nicht haben.

## Wofür wir uns verbürgen

Jede Zusage hier hat einen Paragraphen im [[KODEX]], an dem sie prüfbar wird.

- **Wir fragen nur das Pseudonym ab.** Kein Name, kein Geburtsdatum, keine Adresse. Keine IP-Adressen in Logs, kein Tracking, keine Dienste Dritter. Wir könnten mehr, wir wollen nicht. (§ 1)
- **Frage, Nenner und Schwelle stehen vor dem Start öffentlich fest.** Nach Sicht der Zahlen ändern wir daran nichts. (§ 7)
- **Wir veröffentlichen die Beteiligungsquote immer mit** — auch wenn sie niedrig ist. Besonders dann. Wird die Schwelle verfehlt, erscheint kein Ergebnis. (§ 8)
- **Fehler melden wir selbst.** Betroffene Ergebnisse ziehen wir zurück, statt sie still zu korrigieren. (§ 10)
- **Wir schreiben keine eigene Ausweis-Kryptografie.** Niemals. Wir sind Nutzer zertifizierter Komponenten, nicht ihr Erfinder. (§ 3)
- **Wir veröffentlichen unseren Code.** Wer prüfen will, was in seinem Browser läuft, muss es prüfen können — deshalb ein Build, der sich aus dem offenen Stand nachbauen lässt. (§ 20)
- **Geldgeber stehen mit Betrag und Zeitraum öffentlich.** Kein Einfluss auf Fragen, keine Exklusivität, keine Werbung, kein Datenverkauf. (§ 13)
- **Wir sagen, was wir nicht können,** bevor jemand anders es findet. Wo eine Zusage nur unsere Disziplin ist, steht das dabei. (§ 4)

Diese Zusagen widersprechen sich real. Dafür gibt es eine feste Rangfolge: Wahlgeheimnis vor Ehrlichkeit vor Verifizierbarkeit vor Aussagekraft vor Reichweite. **Reichweite steht immer letzter.** „Sonst wachsen wir nicht" entscheidet bei uns keinen Konflikt.

## Was wir nicht sind

Der wichtigste Abschnitt des Dokuments. Ein Projekt, das mit Vertrauen wirbt, verliert es genau hier zuerst.

**Kein Volksentscheid.** Unsere Ergebnisse haben keine Rechtswirkung. Sie erzeugen Öffentlichkeit, sonst nichts.

**Kein Ersatz für Wahlen.** Es fehlen die Schutzmechanismen des Wahlrechts, vor allem einer: Wer neben dir steht, während du abstimmst, kann dich beeinflussen. Unsere individuelle Nachprüfbarkeit ist zugleich eine vorzeigbare Quittung. Das ist eine bewusste Architekturentscheidung — und sie schließt jeden Einsatz als Wahl aus (§ 16).

**Kein Ersatz für Meinungsforschung.** Institute liefern Zeitreihen und Untergruppenanalysen, die wir nicht liefern. Wir liefern eine Sache, die sie nicht liefern können. Andere Gattung, nicht bessere Version.

**Nicht repräsentativ im statistischen Sinn.** Wer teilnimmt, wählt sich selbst aus. Unsere mögliche Teilnehmerschaft ist zusätzlich jünger, männlicher, städtischer und höher gebildet als das Land — so ist die Online-Ausweisfunktion verteilt. Wir sagen deshalb nie „die Bevölkerung denkt X", sondern „von den Teilnehmenden — N von M Berechtigten — denken X" (§ 9).

## Wo wir stehen

Ehrlich: am Anfang, und mit einem harten Deckel über dem Kopf.

Rund **18 Prozent** der Erwachsenen haben die Online-Ausweisfunktion aktiviert *und* kennen ihre PIN. Das ist die reale Obergrenze der Beteiligung, nicht die Zahl der Ausweisinhaber. 80 Prozent Beteiligung sind ein Mehrjahresziel, kein Startzustand. Wir verschweigen das in keiner Zahl, die wir veröffentlichen.

Was existiert: eine lauffähige Anwendung mit Blindsignaturen, zwei getrennten Registern und öffentlichem Bulletin Board. Was fehlt: die Anbindung an den echten eID-Flow. Eine Speicherform, aus der sich die Eingangsreihenfolge nicht mehr zurückrechnen lässt — heute liegen beide Register in derselben Reihenfolge vor, und das allein genügt für eine Zuordnung. Und die Schwellensignatur, die aus „wir tun es nicht" ein „wir können es nicht" macht — bis dahin steht der Signaturschlüssel allein bei uns.

Beides ist Arbeit an derselben Stelle: Jede dieser Zusagen ruht heute auf uns. Wir halten sie, aber wir haben sie noch nicht aus der Hand gegeben.

## Warum wir trotzdem anfangen

Weil der Deckel selbst das zweite Ziel ist.

Die Online-Ausweisfunktion wird nicht genutzt, weil es zu wenig Gründe gibt, sie zu nutzen. Alles Bisherige ist Pflicht: Steuererklärung, Kfz-Zulassung, Rentenauskunft. Niemand richtet eine PIN ein aus Vorfreude auf ein Formular.

Seine Meinung zu sagen ist keine Pflicht. Es ist freiwillig, es wiederholt sich, man kann darüber reden, und man sieht, was es bewirkt hat. Der erste Grund für die eID, der Spaß macht.

Dazu: 21 Prozent haben die Funktion aktiviert und nur die PIN vergessen — ein Schritt, kein Behördengang. Der kostenlose Rücksetzdienst des Bundes startet in der zweiten Jahreshälfte 2026 neu.

Wir sind also nicht nur Leidtragende der niedrigen Verbreitung. Wir sind ein Grund, sie zu ändern.

## Was uns selbst gefährlich werden kann

Die Kryptografie schützt die Auszählung. Sie schützt nicht die **Frage**.

Wer formuliert, wer die Antworten festlegt, wer den Zeitpunkt wählt und wer entscheidet, welche Fragen überhaupt gestellt werden, hat mehr Macht über das Ergebnis als jeder denkbare Manipulator — legal und unsichtbar. Eine Instanz, die groß genug wird, um politisch zu zählen, ist damit selbst eine Machtkonzentration. Es wäre absurd, dem Meinungsforschungsauftraggeber diese Macht zu nehmen, um sie uns selbst zu geben.

Die endgültige Antwort ist die Übergabe an ein unabhängiges Gremium. Sie erfolgt, **bevor** die Instanz groß genug ist, um politisch zu zählen — nicht danach. Wer dieses Gremium trägt, ist der größte ungelöste Knoten des Projekts.

Bis dahin gilt: jede Frage neutral formuliert, immer mit Enthaltungsoption, und abgelehnte Fragevorschläge werden mitsamt Ablehnungsgrund veröffentlicht. Ohne das Abgelehnte bleibt Themenauswahl die eine Stellschraube, die niemand prüfen kann. (§ 12)

Zwei Dinge sagen wir schon jetzt zu: Wir machen kein Spiel aus dem Abstimmen — keine Punkte, keine Serien, keine Belohnung für Menge. Und wir wachsen nicht über die Fragen, die am meisten aufregen. Das wäre exakt die Parteilichkeit, die wir anderen vorwerfen. (§ 15)

## Woran wir uns messen lassen

Beantwortbar mit ja oder nein, nicht mit Absichtserklärungen:

1. Läuft der vollständige Ablauf mit einem echten Ausweis?
2. Trägt jedes veröffentlichte Ergebnis Quote und Nenner — auch das schlechte?
3. Hat jemand außerhalb des Projekts ein Ergebnis nachgerechnet, ohne uns zu fragen?
4. Liegt der Signaturschlüssel noch bei uns allein?
5. Nehmen noch immer wir allein Anmeldung und Stimme entgegen?
6. Entscheiden noch immer wir, welche Fragen gestellt werden?
7. Haben Menschen wegen uns ihre eID aktiviert?

Bei 4, 5 und 6 ist „ja" die schlechte Antwort. Alle drei stehen heute auf ja.
