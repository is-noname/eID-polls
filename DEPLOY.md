# Öffentlich stellen (Showcase)

Diese Anleitung bringt die App als **Vorführinstanz** ins Netz — etwas, das man verschicken und
jemandem zeigen kann. Sie macht sie nicht zu einem Werkzeug, mit dem man eine Abstimmung
durchführt, deren Ergebnis jemand ernst nimmt. Der Unterschied steht unten unter „Was fehlt".

## Warum nicht Netlify

Netlify (und Vercel) deployen statische Dateien plus kurzlebige Functions. Diese App ist ein
dauerhaft laufender Python-Prozess mit Datenbank und einem Signaturschlüssel, der zwischen zwei
Anfragen derselbe bleiben muss — Phase A signiert blind, Phase B prüft dieselbe Signatur. Auf einer
Function-Plattform gibt es diesen gemeinsamen Zustand nicht. Netlify scheidet damit nicht aus
Bequemlichkeit aus, sondern weil das Verfahren dort nicht funktionieren würde.

## Anbieter mit echtem Gratis-Tarif (Stand Juli 2026)

| Anbieter | Gratis? | Für diese App |
|---|---|---|
| **Render** | ja, dauerhaft | **Empfehlung.** 512 MB RAM, HTTPS, eigene Domain, Ruhezustand nach 15 min ohne Aufruf, 750 Instanzstunden/Monat, **keine persistente Platte** |
| Fly.io | nein | Gratis-Tarif abgeschafft, nur noch 2-Stunden-Test für neue Konten |
| Koyeb | nein | Nach der Übernahme durch Mistral AI für neue Nutzer geschlossen |
| Railway | nein | Nur noch Startguthaben, danach kostenpflichtig |
| Hugging Face Spaces | ja | Funktioniert per Docker, ist aber ein ML-Schaufenster — als Ort für ein Wahlverfahren erklärungsbedürftig |

Render ist damit der einzige Anbieter, der hier ohne Kreditkarte und ohne Zeitlimit trägt.

### Was der Gratis-Tarif kostet

**Kein dauerhafter Speicher.** Die SQLite-Datei liegt im Container-Dateisystem. Bei jedem Deploy und
nach jedem Ruhezustand ist sie weg — mit ihr alle Umfragen, Stimmen, Belege und der
Signaturschlüssel. Beim Start legt die App deshalb automatisch eine Demo-Umfrage an
(`config.py`), damit die Seite nie leer ist, und sagt im Banner, dass Daten nicht bleiben.

**Kaltstart.** Nach 15 Minuten ohne Aufruf schläft der Dienst; der nächste Besucher wartet etwa eine
halbe Minute. Vor einer Vorführung einmal die Seite aufrufen.

Wer Daten behalten will, braucht den kostenpflichtigen Tarif mit Platte (Render Starter, ab ca.
7 $/Monat) — die App selbst muss dafür nicht geändert werden, nur `EIDPOLL_DB` auf den
Platten-Pfad zeigen.

## Live

**<https://eid-poll.onrender.com>** — Vorführinstanz, Stand 2026-07-27. Admin-Token noch nicht
abgeholt (siehe Schritt 4 unten) — bis dahin ist `/admin` und `/debug` für den Betreiber selbst
gesperrt.

## Zugriffslogs

Der Startbefehl trägt `--no-access-log`, und das ist keine Geschmacksfrage: Uvicorn schreibt seinen
Zugriffslog nach stdout, der Hoster sammelt stdout, und zusammen mit `--forwarded-allow-ips` steht
dort die IP des Besuchers statt der des Proxys. `KODEX.md` § 1 verbietet vollständige IP-Adressen in
Zugriffslogs ausdrücklich. Wer den Startbefehl ändert, prüft das mit.

Was der Hoster **unabhängig davon** protokolliert — Loadbalancer, TLS-Endpunkt, DDoS-Schutz — liegt
außerhalb der App und ist damit nicht erledigt. Offen in `EIP-T-041`.

## Deploy auf Render

1. Auf [render.com](https://render.com) mit dem GitHub-Konto anmelden.
2. **New → Blueprint**, Repo `is-noname/eID-polls` wählen, Branch `prototype`.
   Render liest `render.yaml` und legt den Dienst selbst an.
3. Deploy abwarten (erster Build ca. 2–3 Minuten). Die URL lautet dann etwa
   `https://eid-poll.onrender.com`.
4. **Admin-Token abholen:** Dashboard → Dienst → *Environment* → `EIDPOLL_ADMIN_TOKEN`.
   Render hat dort beim ersten Deploy einen Zufallswert erzeugt.

Ohne Blueprint geht es auch von Hand: *New → Web Service*, Repo verbinden, Runtime Python,
Build `pip install -r requirements.txt`, Start
`uvicorn web:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`,
und `EIDPOLL_PUBLIC=1` sowie ein eigenes `EIDPOLL_ADMIN_TOKEN` als Umgebungsvariablen setzen.

Für jede andere Plattform, die Container startet, liegt ein `Dockerfile` bei.

## Was `EIDPOLL_PUBLIC=1` ändert

Ein Schalter, damit der öffentliche Betrieb nicht davon abhängt, dass jemand an fünf Einstellungen
denkt (`config.py`):

- **Kein Standard-Admin-Token mehr.** Ohne gesetzte Variable erzeugt die App ein Zufallstoken und
  schreibt es einmal ins Startprotokoll. `admin` als Voreinstellung gibt es nur noch lokal.
- **Cookies nur über HTTPS** (`secure`-Flag).
- **Keine Shutdown-Route.** Der Beenden-Knopf ist lokales Komfort-Werkzeug; öffentlich wäre er eine
  Abschaltmöglichkeit für Fremde.
- **Niemand gilt als „lokal".** Hinter einem Reverse Proxy ist die Absender-IP die des Proxys —
  Rechte daran zu knüpfen hieße, dem Proxy zu vertrauen statt dem Bediener.
- **Fehlermeldungen ohne Innenleben.** Ausnahmetexte (Pfade, SQL) bleiben im Debug-Modul.
- **Demo-Banner für alle Besucher** und automatische Demo-Umfrage beim Start.
- **Angriffsdemos nicht verdrahtet.** `demo.py` schreibt an der Anwendung vorbei ins Board; wer
  das Admin-Token einer erreichbaren Instanz hat, könnte sie sonst zerschreiben. Für die
  Vorführinstanz ausdrücklich mit `EIDPOLL_DEMOS=1` einschalten (siehe *Vorführung*, Schritt 6).

## Umgebungsvariablen

| Variable | Standard | Zweck |
|---|---|---|
| `EIDPOLL_PUBLIC` | leer | `1` = öffentlicher Betrieb (siehe oben) |
| `EIDPOLL_ADMIN_TOKEN` | zufällig erzeugt | Zugang zu `/admin` und `/debug` |
| `EIDPOLL_DB` | `data/eidpoll.sqlite3` | Pfad der Datenbank (für persistente Platte) |
| `EIDPOLL_ACCESS_CODES` | `testperson1…100` | Gültige Zugangscodes, kommagetrennt |
| `EIDPOLL_ACCESS_CODES_FILE` | leer | Codes stattdessen aus einer Datei, eine Zeile je Code |
| `EIDPOLL_DEMOS` | an, außer bei `PUBLIC` | Angriffsdemos (`demo.py`) einhängen: Board umschreiben, Stimme einschleusen, Testzugang zurücksetzen |
| `EIDPOLL_SEED_DEMO` | an, wenn `PUBLIC` | Demo-Umfrage beim Start anlegen |
| `EIDPOLL_SEED_POLL_ID` / `_QUESTION` / `_OPTIONS` | `demo` / eID-Frage / `Ja,Nein,Unentschieden` | Inhalt der Demo-Umfrage |
| `PORT` | 8731 | Von der Plattform gesetzt |

## Vorführung

Die Instanz zeigt vor allem eines: dass „anonym" und „nachprüfbar" sich nicht ausschließen.
Ein Ablauf, der das trägt:

1. **Startseite → Umfrage öffnen.** Nur der Teilnahmezähler ist sichtbar, kein Zwischenstand (§7).
2. **Ausweisen** mit `testperson1`, **Stimmrecht abholen** — der aufklappbare Block zeigt, dass der
   Token im Browser entsteht und verblindet zum Server geht.
3. **Abstimmen**, **Beleg sichern**, unter *Stimme prüfen* den eigenen Eintrag im Board finden.
4. **Zweiter Versuch mit `testperson1`** — abgewiesen, obwohl der Server nicht weiß, wie diese
   Person gestimmt hat. Das ist der Kern des Verfahrens.
5. **Board öffnen:** Hash-Kette, Ledger-Abrechnung, Auszählung aus der geprüften Kette.
6. Mit Admin-Token: unter *Admin* die Demo-Knöpfe **Eintrag verfälschen** und **Stimme
   einschleusen** — das Board meldet sofort gebrochene Kette bzw. eine Abrechnung, die nicht
   aufgeht. Der Nachweis, dass die Prüfung nicht dekorativ ist.
   Öffentlich erscheinen diese Knöpfe nur mit `EIDPOLL_DEMOS=1`; ohne die Variable gibt es die
   Routen nicht, nicht bloß eine Abweisung.

## Was fehlt, bevor jemand ein Ergebnis ernst nehmen darf

Ehrlichkeitshalber und ohne Beschönigung:

- **Keine Identitätsprüfung.** `CodeAuthenticator` ersetzt den eID-Flow durch eine offene Codeliste.
  Wer die Codes kennt, kann so oft teilnehmen, wie es unverbrauchte gibt. Der echte SAML-Weg
  (`SamlEidAuthenticator`) ist nicht gebaut.
- **Der Betreiber hält den Signaturschlüssel allein.** Er kann sich beliebig viele gültige Token
  ausstellen. Sichtbar wird das nur über die Ledger-Abrechnung, und die zählt gegen eine Zahl, die
  derselbe Betreiber führt. Gegen ihn selbst schützt das Verfahren hier noch nicht.
- **Kein dauerhafter Speicher** auf dem Gratis-Tarif — ein Ergebnis, das ein Neustart löscht, ist
  kein Ergebnis.
- **Keine Rate-Begrenzung**, keine unabhängige Prüfstelle, kein Audit.
