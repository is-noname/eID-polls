"""Misst das Zeitverhalten der Signieroperation - lokal und ueber HTTP.

Zu EIP-T-093. Die Haertung von blind_sign() (rsa_raw, OpenSSL statt pow) ist
ohne Messung eine Behauptung: dass OpenSSL abblendet, steht in seiner
Dokumentation und nicht in unserem Prozess. Dieses Skript stellt beide Wege
nebeneinander und fragt genau eine Sache:

    Laesst sich aus der Laufzeit ablesen, *welche* Nachricht signiert wurde?

Gemessen wird deshalb nicht die mittlere Dauer - die ist fuer einen Angreifer
wertlos -, sondern der Unterschied zwischen festen Eingabeklassen:

    klein     m = 2, weit unterhalb des Modulus
    typisch A m = fester Zufallswert
    typisch B m = anderer fester Zufallswert

Daraus werden zwei Fragen beantwortet, die verschieden schwer sind:

    klein vs typisch A   Faellt eine extreme Eingabe auf? Grobe Probe.
    typisch A vs B       Lassen sich zwei gewoehnliche Nachrichten trennen?
                         Das ist der realistische Fall - eine verblindete
                         Nachricht sieht immer wie ein Zufallswert aus.

Bewusst *nicht* verwendet wird m = n-1, obwohl es als "dicht unter dem
Modulus" naheliegt: n-1 ist kongruent zu -1, seine Potenzen sind daher immer
1 oder n-1 und die Rechnung entartet. Sie lief bei der ersten Messung zu
diesem Ticket sechsmal schneller als eine gewoehnliche Eingabe und haette als
starker Seitenkanal missgedeutet werden koennen - gemessen war aber nur
Schulmathematik, nicht Montgomery-Reduktion.

Als Mass dient die Trennschaerfe AUC: die Wahrscheinlichkeit, dass eine
zufaellig gezogene Messung der einen Klasse ueber der der anderen liegt.

    0.50  ununterscheidbar - die Laufzeit verraet die Eingabe nicht
    1.00  perfekt trennbar - jede einzelne Messung verraet die Klasse

AUC ist hier aussagekraeftiger als Mittelwert und Streuung, weil sie gegen
Ausreisser und gegen die Grundlast des Rechners unempfindlich ist: eine
gleichmaessig langsamere Maschine verschiebt beide Klassen zugleich.

Was das Skript *nicht* zeigt: Es beweist keine Seitenkanalfreiheit. Ein
Nullbefund heisst "mit dieser Methode, auf dieser Maschine, in dieser Anzahl
nicht messbar" - nicht "nicht vorhanden". Ein echter Nachweis braucht
dudect/ctgrind und eine ruhige Maschine.

Aufruf:

    python3 messung_blind_sign.py                 # nur lokal
    python3 messung_blind_sign.py --http          # zusaetzlich ueber HTTP
    EIDPOLL_URL=http://127.0.0.1:8899 ...         # Server dafuer (frische DB)
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import statistics
import sys
import time
import urllib.error
import urllib.request

import auth
import blind
import rsa_raw

BASE = os.environ.get("EIDPOLL_URL", "http://127.0.0.1:8899")
POLL = "messung"


# ---------------------------------------------------------------------------
# Auswertung
# ---------------------------------------------------------------------------


def auc(a: list[float], b: list[float]) -> float:
    """Trennschaerfe zweier Messreihen ueber die Rangsumme (Mann-Whitney U/n1n2).

    Bindungen bekommen den mittleren Rang, sonst wuerde eine grobe Uhr
    kuenstliche Trennschaerfe erzeugen. Der Rueckgabewert wird auf >= 0.5
    gespiegelt: die Richtung des Unterschieds interessiert nicht, nur seine
    Ablesbarkeit.
    """
    zusammen = sorted([(x, 0) for x in a] + [(x, 1) for x in b])
    raenge: list[float] = [0.0] * len(zusammen)
    i = 0
    while i < len(zusammen):
        j = i
        while j + 1 < len(zusammen) and zusammen[j + 1][0] == zusammen[i][0]:
            j += 1
        mittel = (i + j) / 2 + 1
        for k in range(i, j + 1):
            raenge[k] = mittel
        i = j + 1

    rangsumme_a = sum(r for r, (_, klasse) in zip(raenge, zusammen) if klasse == 0)
    n1, n2 = len(a), len(b)
    u = rangsumme_a - n1 * (n1 + 1) / 2
    wert = u / (n1 * n2)
    return max(wert, 1 - wert)


def zeile(name: str, a: list[float], b: list[float], einheit: str) -> str:
    trenn = auc(a, b)
    urteil = "ununterscheidbar" if trenn < 0.55 else (
        "schwach trennbar" if trenn < 0.65 else "TRENNBAR")
    return (
        f"    {name:<24} "
        f"Median {statistics.median(a):9.1f} / {statistics.median(b):9.1f} {einheit}   "
        f"Streuung {statistics.pstdev(a):7.1f} / {statistics.pstdev(b):7.1f}   "
        f"AUC {trenn:.3f}  {urteil}"
    )


def messreihe(fn, eingabe: bytes, runden: int) -> list[float]:
    """Laufzeiten in Mikrosekunden. perf_counter_ns, weil die Operation im
    Millisekundenbereich liegt und eine Millisekundenuhr alles zu Bindungen
    zusammenzoege."""
    werte = []
    for _ in range(runden):
        start = time.perf_counter_ns()
        fn(eingabe)
        werte.append((time.perf_counter_ns() - start) / 1000)
    return werte


def verschraenkt(fn, klassen: dict[str, bytes], runden: int) -> dict[str, list[float]]:
    """Alle Klassen abwechselnd messen, nicht nacheinander.

    Nacheinander wuerde jede Drift der Maschine - Taktaenderung, ein anderer
    Prozess, Cache-Erwaermung - als Klassenunterschied erscheinen. Bei
    Verschraenkung trifft sie alle Klassen gleich.
    """
    werte: dict[str, list[float]] = {name: [] for name in klassen}
    for _ in range(runden):
        for name, eingabe in klassen.items():
            werte[name].extend(messreihe(fn, eingabe, 1))
    return werte


def bericht(name: str, werte: dict[str, list[float]], einheit: str) -> None:
    print(f"  {name}")
    print(zeile("klein vs typisch A", werte["klein"], werte["typisch A"], einheit))
    print(zeile("typisch A vs B", werte["typisch A"], werte["typisch B"], einheit))


# ---------------------------------------------------------------------------
# Lokal
# ---------------------------------------------------------------------------


def lokal(runden: int) -> None:
    key = blind.generate_key()
    zahlen = key.public_key().public_numbers()
    n, d = zahlen.n, key.private_numbers().d
    k = (n.bit_length() + 7) // 8

    klassen = klassen_bauen(n, k)

    def ungehaertet(data: bytes) -> bytes:
        # Der Weg vor EIP-T-093, hier nur noch als Vergleichsmassstab.
        return blind.i2osp(pow(blind.os2ip(data), d, n), k)

    def gehaertet(data: bytes) -> bytes:
        return rsa_raw.private_op(key, data)

    for eingabe in klassen.values():
        if ungehaertet(eingabe) != gehaertet(eingabe):
            raise AssertionError("Vergleichsmassstab und OpenSSL rechnen verschieden.")

    print(f"Lokal, {blind.KEY_BITS} Bit, {runden} Durchlaeufe je Klasse, verschraenkt gemessen.\n")

    roh = verschraenkt(ungehaertet, klassen, runden)
    bericht("pow(m, d, n) - der Weg vor EIP-T-093", roh, "us")
    neu = verschraenkt(gehaertet, klassen, runden)
    bericht("OpenSSL EVP_PKEY_decrypt - jetzt", neu, "us")

    # Nebenbefund, der in die Doku gehoert: die Haertung kostet nichts, sie
    # spart. OpenSSL rechnet ueber die CRT mit p und q, CPython mit dem vollen
    # Exponenten - das wiegt den PEM-Parse je Aufruf mehrfach auf.
    alt = statistics.median(roh["typisch A"])
    jetzt = statistics.median(neu["typisch A"])
    print(f"\n  Kosten der Haertung: {jetzt - alt:+.0f} us je Signatur "
          f"({alt / jetzt:.1f}-fach schneller trotz PEM-Parse je Aufruf)")


def klassen_bauen(n: int, k: int) -> dict[str, bytes]:
    """Die drei Eingabeklassen. Fest gezogen, damit jede Messung derselben
    Klasse wirklich dieselbe Nachricht signiert - sonst maesse man die
    Streuung ueber Nachrichten und nicht die Trennbarkeit von Klassen."""
    return {
        "klein": blind.i2osp(2, k),
        "typisch A": blind.i2osp(secrets.randbelow(n - 2) + 2, k),
        "typisch B": blind.i2osp(secrets.randbelow(n - 2) + 2, k),
    }


# ---------------------------------------------------------------------------
# Ueber HTTP
# ---------------------------------------------------------------------------


class Sitzung:
    """Minimaler HTTP-Client mit Cookie-Gedaechtnis - kein requests noetig."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.cookies: dict[str, str] = {}

    def post(self, pfad: str, daten: dict) -> tuple[int, dict]:
        rumpf = json.dumps(daten).encode()
        req = urllib.request.Request(
            self.base + pfad, data=rumpf, method="POST",
            headers={"Content-Type": "application/json",
                     "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items())},
        )
        try:
            with urllib.request.urlopen(req) as antwort:
                self._cookies_merken(antwort)
                return antwort.status, json.loads(antwort.read() or b"{}")
        except urllib.error.HTTPError as fehler:
            self._cookies_merken(fehler)
            try:
                return fehler.code, json.loads(fehler.read() or b"{}")
            except json.JSONDecodeError:
                return fehler.code, {}

    def _cookies_merken(self, antwort) -> None:
        for rohwert in antwort.headers.get_all("Set-Cookie") or []:
            paar = rohwert.split(";")[0]
            if "=" in paar:
                name, wert = paar.split("=", 1)
                self.cookies[name.strip()] = wert.strip()


def ueber_http(runden: int) -> None:
    admin = Sitzung(BASE)
    status, _ = admin.post("/api/admin/login", {"token": os.environ.get("EIDPOLL_ADMIN_TOKEN", "admin")})
    if status != 200:
        print(f"  Admin-Anmeldung fehlgeschlagen (HTTP {status}). Laeuft ein Server auf {BASE} "
              f"mit EIDPOLL_ADMIN_TOKEN?")
        return
    # Enthaltung ist Pflicht (KODEX §12) - auch fuer eine Umfrage, die nur
    # Messgroesse ist und nie ausgezaehlt wird.
    admin.post("/api/admin/create",
               {"poll_id": POLL, "question": "Messung zu EIP-T-093",
                "options": ["Ja", "Nein", "Enthaltung"]})

    # Der Stub akzeptiert nur hinterlegte Ausweisnummern (auth.CodeAuthenticator).
    # Dass die Berechtigung fuer diese Nummer laengst verbraucht ist, stoert
    # nicht - signiert wird trotzdem, siehe unten.
    codes = auth.CodeAuthenticator().sample_codes()
    if not codes:
        print("  Keine Zugangscodes konfiguriert - HTTP-Messung entfaellt.")
        return
    person = Sitzung(BASE)
    status, _ = person.post("/api/auth", {"credential": codes[0]})
    if status != 200:
        print(f"  Anmeldung fehlgeschlagen (HTTP {status}). Erwartet wurde der "
              f"Zugangscode-Stub; laeuft dort ein anderer Authenticator?")
        return

    pub = _pubkey(admin)
    if pub is None:
        print("  Oeffentlicher Umfrage-Schluessel nicht abrufbar - HTTP-Messung entfaellt.")
        return
    n = pub
    klassen = klassen_bauen(n, (n.bit_length() + 7) // 8)

    def anfrage(eingabe: bytes) -> None:
        person.post(f"/api/token/{POLL}", {"blinded": eingabe.hex()})

    # Der erste Aufruf verbraucht den Anspruch. Danach wird weiter voll
    # signiert - issue_blind_signature signiert *vor* dem Anspruch - und erst
    # anschliessend abgewiesen. Genau das macht die Messung ueberhaupt
    # moeglich: eine Identitaet, beliebig viele Signaturen.
    anfrage(klassen["klein"])

    werte: dict[str, list[float]] = {name: [] for name in klassen}
    for _ in range(runden):
        for name, eingabe in klassen.items():
            start = time.perf_counter_ns()
            anfrage(eingabe)
            werte[name].append((time.perf_counter_ns() - start) / 1000)

    print(f"\nUeber HTTP ({BASE}), {runden} Anfragen je Klasse, verschraenkt.")
    print("  Loopback, also der guenstigste Fall fuer einen Angreifer: kein Netzrauschen.")
    print("  Ein Nullbefund hier ist damit eine Obergrenze fuer den Fall ueber echtes Netz.\n")
    bericht("POST /api/token", werte, "us")


def _pubkey(admin: Sitzung) -> int | None:
    """Modulus der Umfrage aus dem Board holen."""
    try:
        with urllib.request.urlopen(f"{BASE}/api/board/{POLL}") as antwort:
            daten = json.loads(antwort.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None
    pem = _suche_pem(daten)
    if pem is None:
        return None
    from cryptography.hazmat.primitives import serialization
    return serialization.load_pem_public_key(pem.encode()).public_numbers().n


def _suche_pem(daten) -> str | None:
    """Der Board-Aufbau ist nicht Gegenstand dieser Messung - der Schluessel
    wird deshalb gesucht statt ueber einen festen Pfad gelesen. Aendert sich
    das Board, faellt hier nichts um."""
    if isinstance(daten, str):
        return daten if "BEGIN PUBLIC KEY" in daten else None
    if isinstance(daten, dict):
        daten = daten.values()
    if isinstance(daten, (list, tuple)) or hasattr(daten, "__iter__"):
        for teil in daten:
            treffer = _suche_pem(teil)
            if treffer:
                return treffer
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runden", type=int, default=300,
                        help="Durchlaeufe je Klasse (Vorgabe 300)")
    parser.add_argument("--http", action="store_true",
                        help=f"zusaetzlich ueber HTTP gegen {BASE} messen")
    args = parser.parse_args()

    ok, meldung = rsa_raw.verfuegbar()
    print(f"OpenSSL-Bindung: {meldung}\n")
    if not ok:
        sys.exit(1)

    lokal(args.runden)
    if args.http:
        ueber_http(max(50, args.runden // 3))
