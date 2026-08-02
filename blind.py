"""RSA-Blindsignaturen nach RFC 9474, Variante RSABSSA-SHA384-PSSZERO-Deterministic.

Zur Variante: RFC 9474 §5 unterscheidet PSS (Salt-Laenge 48) von PSSZERO
(Salt-Laenge 0) und Randomized (PrepareRandomize) von Deterministic
(PrepareIdentity). Diese Datei rechnet mit Salt-Laenge 0 und ohne Praeparation,
das ist PSSZERO-Deterministic - bis 2026-08-01 stand hier und in mehreren
Dokumenten faelschlich "PSS-Deterministic", eine andere Variante (EIP-T-008).

Warum diese Variante: sie ist als einzige deterministisch ueber den Token, und
ein Token muss sich im Board unter genau einer Signatur wiederfinden lassen.
RFC 9474 §5 knuepft sie an eine Bedingung, §7.3 nennt sie: Der Signierende darf
die Eingabe nicht raten koennen, sonst kann er mit einem boesartig erzeugten
Schluessel Rueckschluesse auf sie ziehen. Hier ist der Token 32 Byte aus
crypto.getRandomValues, im Browser erzeugt, bevor der Server ihn in irgendeiner
Form sieht - Bedingung (2) aus §7.3 ist erfuellt. Das ist keine Nebensache: der
Betreiber erzeugt den Signaturschluessel allein, der Fall aus §7.3 ist also
genau unser Angreifermodell und traegt nur wegen dieser Entropie.

DOKUMENTIERTE ABWEICHUNG von EIP-RFC-20260725-001 §4 ("niemals handgeschriebene
Krypto"): Fuer Python existiert keine gepruefte RFC-9474-Implementierung. Die
PyPI-Suche vom 2026-08-01 lieferte fuer blind-rsa-signatures, blind_signatures,
blindsig, rsa-blind-signatures, pyblindsig, rsabssa, blind-signature,
pyblind-rsa, blindrsa, py-blind-rsa und rfc9474 jeweils keine Distribution
(Vorbefund gleichen Inhalts vom 2026-07-25). Gepruefte Umsetzungen gibt es in
Rust (jedisct1/blind-rsa-signatures), Go (cloudflare/circl) und inzwischen in
TypeScript (@cloudflare/blindrsa-ts) - siehe EIP-T-079 fuer die Client-Seite.

Was daraus folgt, offen benannt:

  Zugekauft (geprueft):  SHA-384, die RSASSA-PSS-Verifikation und seit
                         EIP-T-093 die rohe RSA-Privatoperation kommen aus
                         `cryptography` / OpenSSL. Eine fertige Signatur ist
                         eine ganz gewoehnliche PSS-Signatur und laesst sich
                         von jedem Dritten mit Standardwerkzeug pruefen.
  Selbst geschrieben:    EMSA-PSS-ENCODE, MGF1 und die modulare Arithmetik des
                         Blindings. Im serverseitigen Stimmweg laeuft davon
                         seit EIP-T-093 nichts mehr: poll_service ruft
                         blind_sign(), und dessen Rechenkern liegt in
                         rsa_raw.private_op() bei OpenSSL. Die uebrigen
                         Schritte gehoeren dem Browser (static/blind.js); hier
                         bedienen sie testvektor() und die Angriffsdemos in
                         demo.py. Die Restschuld aus V-005 ist damit die
                         Browser-Haelfte (EIP-T-008), nicht mehr der Server.
  Nachgewiesen:          testvektor() rechnet jeden dieser Schritte gegen den
                         Testvektor aus RFC 9474 Anhang A.4 nach - Byte fuer
                         Byte, mit dem Blendfaktor aus dem RFC statt einem
                         eigenen. Das ist der staerkste Korrektheitsnachweis
                         ohne externen Audit; ein Audit ersetzt er nicht,
                         denn er prueft Korrektheit, nicht Seitenkanaele.

Fuer einen echten Betrieb ist diese Datei gegen eine auditierte Bibliothek zu
tauschen - die Schnittstelle (blind / blind_sign / finalize / verify) ist dafuer
absichtlich schmal, und der Testvektor bleibt danach als Regressionstest stehen.

Die Gegenstelle im Browser ist static/blind.js. Beide Seiten muessen bitgenau
dasselbe EMSA-PSS-ENCODE rechnen; blind_vektor.mjs haelt die JS-Seite gegen
denselben RFC-Vektor, /debug zeigt Signaturfehler zur Laufzeit.
"""

from __future__ import annotations

import json
import math
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import rsa_raw

VARIANTE = "RSABSSA-SHA384-PSSZERO-Deterministic"
HASH = hashes.SHA384
H_LEN = 48
SALT_LEN = 0  # PSSZERO nach RFC 9474 §5

# 3072 Bit, entschieden am 2026-08-01 (EIP-T-008). Die Basisidee setzt 3072 an,
# BSI TR-02102-1 empfiehlt fuer RSA mindestens 3000 Bit - und das Pitch-Papier
# beruft sich auf BSI-Vorgaben, darf also nicht darunter liegen. Gemessen kostet
# der Schritt von 2048 fast nichts: Schluesselerzeugung ~0,2 s, Blinding 1,3 ms,
# Signieren und Entblinden 82 ms statt 24 ms. Im Browser bleibt es billig, weil
# der oeffentliche Exponent 65537 nur 17 Bit hat. Der Wert gilt fuer neu
# angelegte Umfragen; laufende behalten ihren Schluessel, denn n kommt aus dem
# Schluessel und nicht aus dieser Konstanten.
KEY_BITS = 3072

_VEKTOR_DATEI = Path(__file__).with_name("rfc9474_a4.json")


def _digest(data: bytes) -> bytes:
    h = hashes.Hash(HASH())
    h.update(data)
    return h.finalize()


def i2osp(value: int, length: int) -> bytes:
    return value.to_bytes(length, "big")


def os2ip(data: bytes) -> int:
    return int.from_bytes(data, "big")


def mgf1(seed: bytes, length: int) -> bytes:
    """MGF1 mit SHA-384 (RFC 8017 B.2.1)."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += _digest(seed + i2osp(counter, 4))
        counter += 1
    return bytes(out[:length])


def emsa_pss_encode(msg: bytes, em_bits: int) -> bytes:
    """EMSA-PSS-ENCODE (RFC 8017 9.1.1) mit SHA-384 und Salt-Laenge 0.

    em_bits ist bei den Aufrufern bit_len(n) - 1, wie RFC 8017 §8.1.1 es fuer
    RSASSA-PSS-SIGN vorschreibt. RFC 9474 §4.2 Schritt 1 schreibt bit_len(n);
    beide ergeben dieselbe Kodierung, solange das oberste Bit frei bleibt, und
    der Testvektor A.4 bestaetigt beide. Der Wert mit -1 ist der sichere, weil
    er die kodierte Nachricht garantiert unter den Modulus zwingt.
    """
    em_len = (em_bits + 7) // 8
    if em_len < H_LEN + SALT_LEN + 2:
        raise ValueError("Modulus zu klein fuer EMSA-PSS mit SHA-384.")

    m_hash = _digest(msg)
    salt = b""
    m_prime = b"\x00" * 8 + m_hash + salt
    h = _digest(m_prime)

    ps = b"\x00" * (em_len - SALT_LEN - H_LEN - 2)
    db = ps + b"\x01" + salt
    db_mask = mgf1(h, em_len - H_LEN - 1)
    masked_db = bytearray(a ^ b for a, b in zip(db, db_mask))

    # Die fuehrenden 8*em_len - em_bits Bits muessen null sein.
    unused_bits = 8 * em_len - em_bits
    if unused_bits:
        masked_db[0] &= 0xFF >> unused_bits

    return bytes(masked_db) + h + b"\xbc"


# ---------------------------------------------------------------------------
# Protokollschritte (RFC 9474 §4)
# ---------------------------------------------------------------------------


def blind(msg: bytes, n: int, e: int, r: int | None = None) -> tuple[bytes, int]:
    """Client: verblindet die Nachricht. Gibt (blinded_msg, blind_inv) zurueck.

    Nur der Rueckgabewert blinded_msg verlaesst den Client. blind_inv bleibt
    lokal - ohne ihn ist die Serversignatur wertlos, mit ihm ist sie nicht mehr
    auf die verblindete Form zurueckzufuehren (§6).

    r ist der Blendfaktor. Im Betrieb bleibt er None und wird hier gezogen; der
    Parameter existiert allein, damit testvektor() den Faktor aus RFC 9474 A.4
    einsetzen kann, ohne den Rechenweg zu duplizieren. Ein zweiter Rechenweg im
    Test wuerde die Implementierung gegen sich selbst pruefen.
    """
    k = (n.bit_length() + 7) // 8
    encoded = emsa_pss_encode(msg, n.bit_length() - 1)
    m = os2ip(encoded)
    if m >= n:
        raise ValueError("Kodierte Nachricht groesser als der Modulus.")
    # RFC 9474 §4.2 Schritte 4-5: teilerfremd, sonst "invalid input".
    if math.gcd(m, n) != 1:
        raise ValueError("Kodierte Nachricht ist nicht teilerfremd zum Modulus.")

    while True:
        # RFC 9474 §4.2: "The blinding factor r MUST be randomly chosen from a
        # uniform distribution." randbelow ist verzerrungsfrei; r = 1 waere
        # keine Verblindung und faellt deshalb weg.
        faktor = secrets.randbelow(n - 2) + 2 if r is None else r
        try:
            r_inv = pow(faktor, -1, n)
        except ValueError:
            if r is not None:
                raise ValueError("Vorgegebener Blendfaktor ist nicht invertierbar.") from None
            continue  # r nicht invertierbar - neu ziehen
        z = (m * pow(faktor, e, n)) % n
        return i2osp(z, k), r_inv


def blind_sign(blinded_msg: bytes, key: rsa.RSAPrivateKey) -> bytes:
    """Server: signiert blind. Sieht nur die verblindete Form (§6 Phase A.4).

    Die eigentliche Rechnung m^d mod n macht seit EIP-T-093 OpenSSL
    (rsa_raw.private_op), nicht mehr CPythons pow(): pow() rechnet ohne
    Base-Blinding und nicht in konstanter Zeit, und der Schluessel, um den es
    hier geht, stellt Stimmzettel aus. Was hier bleibt, sind Pruefungen und die
    Rueckrechnung - beides mit oeffentlichen Werten, also ohne Zeitgeheimnis.

    Der Schluessel kommt als Objekt statt als (n, d, e): d muss dafuer nicht
    mehr als Python-Ganzzahl durch den Aufrufer wandern.

    Raises:
        ValueError: Die verblindete Nachricht ist ungueltig - Abweisung.
        rsa_raw.OpenSSLNichtVerfuegbar: Der Server kann nicht gehaertet
            signieren. Kein Clientfehler; der Aufrufer meldet das ans
            Debug-Modul, statt ungehaertet weiterzurechnen.
    """
    zahlen = key.public_key().public_numbers()
    n, e = zahlen.n, zahlen.e
    k = (n.bit_length() + 7) // 8
    if len(blinded_msg) != k:
        raise ValueError("Verblindete Nachricht hat die falsche Laenge.")
    m = os2ip(blinded_msg)
    if m >= n:
        raise ValueError("Verblindete Nachricht groesser als der Modulus.")

    s = os2ip(rsa_raw.private_op(key, blinded_msg))

    # RFC 9474 §4.3 Schritte 3-4: die eigene Rechnung zurueckrechnen und
    # vergleichen. Faengt einen verrechneten Exponenten oder einen Bitfehler
    # ab, bevor eine unbrauchbare Signatur den Server verlaesst - unbemerkt
    # waere das fuer den Client eine abgewiesene Stimme ohne erkennbaren Grund.
    # Seit die Rechnung bei OpenSSL liegt, prueft dieser Schritt zusaetzlich die
    # ctypes-Bindung selbst: ein falsch uebergebener Puffer faellt hier auf.
    if pow(s, e, n) != m:
        raise ValueError("Signaturoperation fehlgeschlagen (Rueckrechnung stimmt nicht).")
    return i2osp(s, k)


def key_aus_zahlen(n: int, e: int, d: int) -> rsa.RSAPrivateKey:
    """Baut aus (n, e, d) einen Schluessel - fuer Testvektoren, nicht fuer den Betrieb.

    RFC 9474 Anhang A.4 gibt den Schluessel als d aus, ohne p und q; OpenSSL
    braucht die CRT-Anteile. rsa_recover_prime_factors() rechnet sie zurueck.
    Laeuft nur in testvektor(), nie im Stimmweg.
    """
    p, q = rsa.rsa_recover_prime_factors(n, e, d)
    return rsa.RSAPrivateNumbers(
        p=p,
        q=q,
        d=d,
        dmp1=rsa.rsa_crt_dmp1(d, p),
        dmq1=rsa.rsa_crt_dmq1(d, q),
        iqmp=rsa.rsa_crt_iqmp(p, q),
        public_numbers=rsa.RSAPublicNumbers(e, n),
    ).private_key()


def finalize(
    blind_sig: bytes,
    blind_inv: int,
    n: int,
    public_key: rsa.RSAPublicKey | None = None,
    msg: bytes | None = None,
) -> bytes:
    """Client: entblindet die Signatur (§6 Phase B.5).

    RFC 9474 §4.4 Schritt 5 verlangt, dass der Client das Ergebnis selbst
    prueft, statt es ungesehen weiterzureichen. Werden public_key und msg
    uebergeben, geschieht das hier und eine unbrauchbare Serverantwort faellt
    beim Client auf statt erst bei der Stimmabgabe. Ohne die beiden Argumente
    bleibt es bei der reinen Entblindung.

    Die Gegenstelle im Browser prueft seit EIP-T-080 ebenfalls
    (static/blind.js:finalizeGeprueft) - dort mit WebCrypto statt mit dieser
    Implementierung, damit nicht handgeschriebener Code handgeschriebenen Code
    bestaetigt.
    """
    k = (n.bit_length() + 7) // 8
    s = (os2ip(blind_sig) * blind_inv) % n
    sig = i2osp(s, k)
    if public_key is not None and msg is not None and not verify(public_key, msg, sig):
        raise ValueError("Entblindete Signatur ist ungueltig (RFC 9474 §4.4).")
    return sig


def verify(public_key: rsa.RSAPublicKey, msg: bytes, sig: bytes) -> bool:
    """Gewoehnliche RSASSA-PSS-Pruefung - hier kommt die gepruefte Bibliothek zum Zug."""
    try:
        public_key.verify(
            sig, msg, padding.PSS(mgf=padding.MGF1(HASH()), salt_length=SALT_LEN), HASH()
        )
        return True
    except (InvalidSignature, ValueError):
        return False


def generate_key(bits: int = KEY_BITS) -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=bits)


# ---------------------------------------------------------------------------
# Nachweise
# ---------------------------------------------------------------------------


def testvektor() -> list[str]:
    """Rechnet RFC 9474 Anhang A.4 nach. Rueckgabe: Liste der Abweichungen.

    Der Vektor liegt in rfc9474_a4.json, woertlich aus dem RFC. Geprueft wird
    jeder selbst geschriebene Schritt einzeln, damit eine Abweichung zeigt, wo
    sie sitzt - ein blosser Roundtrip wuerde auch dann gruen, wenn beide Seiten
    denselben Fehler machen. Der Modulus des Vektors hat 4096 Bit und hat mit
    KEY_BITS nichts zu tun.
    """
    vektor = json.loads(_VEKTOR_DATEI.read_text())
    n = int(vektor["n"], 16)
    e = int(vektor["e"], 16)
    d = int(vektor["d"], 16)
    msg = bytes.fromhex(vektor["msg"])
    inv = int(vektor["inv"], 16)
    k = (n.bit_length() + 7) // 8

    abweichungen: list[str] = []

    def gleich(was: str, ist: bytes, soll_hex: str) -> None:
        if ist != bytes.fromhex(soll_hex):
            abweichungen.append(was)

    # PrepareIdentity: die Deterministic-Variante laesst die Nachricht in Ruhe.
    if vektor["prepared_msg"] != vektor["msg"]:
        abweichungen.append("prepared_msg (PrepareIdentity)")

    gleich("encoded_msg (EMSA-PSS-ENCODE, MGF1)",
           emsa_pss_encode(msg, n.bit_length() - 1), vektor["encoded_msg"])

    # Der Vektor gibt den Kehrwert an; blind() erwartet den Faktor selbst.
    blinded, inv_ist = blind(msg, n, e, r=pow(inv, -1, n))
    gleich("blinded_msg (Blind)", blinded, vektor["blinded_msg"])
    if inv_ist != inv:
        abweichungen.append("inv (Blind)")

    # Seit EIP-T-093 laeuft BlindSign ueber OpenSSL. Der Vektor prueft damit
    # nicht mehr nur die Formel, sondern auch die ctypes-Bindung - gegen einen
    # 4096-Bit-Schluessel, den nicht wir erzeugt haben.
    gleich("blind_sig (BlindSign)",
           blind_sign(bytes.fromhex(vektor["blinded_msg"]), key_aus_zahlen(n, e, d)),
           vektor["blind_sig"])
    gleich("sig (Finalize)",
           finalize(bytes.fromhex(vektor["blind_sig"]), inv, n), vektor["sig"])

    if not verify(rsa.RSAPublicNumbers(e, n).public_key(), msg, bytes.fromhex(vektor["sig"])):
        abweichungen.append("verify (RSASSA-PSS-VERIFY gegen die Signatur des RFC)")
    if len(bytes.fromhex(vektor["sig"])) != k:
        abweichungen.append("Signaturlaenge")

    return abweichungen


def selftest(bits: int = KEY_BITS) -> None:
    """Testvektor plus Roundtrip mit frischem Schluessel. Wirft bei Fehlschlag."""
    abweichungen = testvektor()
    if abweichungen:
        raise AssertionError("RFC-9474-Testvektor A.4 verfehlt: " + ", ".join(abweichungen))

    key = generate_key(bits)
    pub = key.public_key().public_numbers()
    n, e = pub.n, pub.e

    msg = secrets.token_bytes(32)
    blinded, inv = blind(msg, n, e)
    sig = finalize(blind_sign(blinded, key), inv, n, key.public_key(), msg)
    if not verify(key.public_key(), msg, sig):
        raise AssertionError("Blindsignatur-Roundtrip fehlgeschlagen.")
    if verify(key.public_key(), secrets.token_bytes(32), sig):
        raise AssertionError("Signatur gilt fuer eine fremde Nachricht.")

    # Ohne OpenSSL muss blind_sign scheitern, nicht auf pow() zurueckfallen
    # (EIP-T-093). Ein stiller Rueckfall waere die ungehaertete Operation unter
    # dem Namen der gehaerteten - und dieser Test die einzige Stelle, an der er
    # auffiele.
    echt, ladefehler = rsa_raw._lib, rsa_raw._ladefehler
    rsa_raw._lib, rsa_raw._ladefehler = None, "Selbsttest: OpenSSL abgeklemmt."
    try:
        blind_sign(blinded, key)
    except rsa_raw.OpenSSLNichtVerfuegbar:
        pass
    else:
        raise AssertionError("blind_sign signiert ohne OpenSSL - stiller Rueckfall auf pow().")
    finally:
        rsa_raw._lib, rsa_raw._ladefehler = echt, ladefehler


if __name__ == "__main__":
    selftest()
    print(f"blind.py selftest ok - RFC 9474 Testvektor A.4 und Roundtrip ({VARIANTE}, {KEY_BITS} Bit)")
