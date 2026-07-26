"""RSA-Blindsignaturen nach RFC 9474, Variante RSABSSA-SHA384-PSS-Deterministic.

DOKUMENTIERTE ABWEICHUNG von EIP-RFC-20260725-001 §4 ("niemals handgeschriebene
Krypto"): Fuer Python existiert keine gepruefte RFC-9474-Implementierung. Die
PyPI-Suche am 2026-07-25 lieferte fuer blind-rsa-signatures, blind_signatures,
blindsig, rsa-blind-signatures und pyblindsig jeweils "No matching distribution
found". Gepruefte Umsetzungen gibt es in Rust (jedisct1/blind-rsa-signatures)
und Go (cloudflare/circl) - beide haetten eine fremde Toolchain in den Prototyp
gezogen.

Was daraus folgt, offen benannt:

  Zugekauft (geprueft):  SHA-384 und die RSASSA-PSS-Verifikation kommen aus
                         `cryptography` / OpenSSL. Eine fertige Signatur ist
                         eine ganz gewoehnliche PSS-Signatur und laesst sich
                         von jedem Dritten mit Standardwerkzeug pruefen.
  Selbst geschrieben:    EMSA-PSS-ENCODE, MGF1, die modulare Arithmetik des
                         Blindings und die rohe RSA-Signaturoperation.

Gegenueber dem Prototyp (textbook-Chaum, 1024 Bit, ohne Padding) ist das ein
deutlicher Fortschritt, aber es ersetzt keine auditierte Bibliothek. Fuer einen
echten Betrieb ist diese Datei gegen eine solche zu tauschen - die Schnittstelle
(blind / blind_sign / finalize / verify) ist dafuer absichtlich schmal.

Die Gegenstelle im Browser ist static/blind.js. Beide Seiten muessen bitgenau
dasselbe EMSA-PSS-ENCODE rechnen; selftest() prueft das fuer die Python-Seite,
/debug zeigt Signaturfehler zur Laufzeit.
"""

from __future__ import annotations

import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

HASH = hashes.SHA384
H_LEN = 48
KEY_BITS = 2048
SALT_LEN = 0  # Deterministic-Variante nach RFC 9474 §5


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
    """EMSA-PSS-ENCODE (RFC 8017 9.1.1) mit SHA-384 und Salt-Laenge 0."""
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


def blind(msg: bytes, n: int, e: int) -> tuple[bytes, int]:
    """Client: verblindet die Nachricht. Gibt (blinded_msg, blind_inv) zurueck.

    Nur der Rueckgabewert blinded_msg verlaesst den Client. blind_inv bleibt
    lokal - ohne ihn ist die Serversignatur wertlos, mit ihm ist sie nicht mehr
    auf die verblindete Form zurueckzufuehren (§6).
    """
    k = (n.bit_length() + 7) // 8
    encoded = emsa_pss_encode(msg, n.bit_length() - 1)
    m = os2ip(encoded)
    if m >= n:
        raise ValueError("Kodierte Nachricht groesser als der Modulus.")

    while True:
        r = secrets.randbelow(n - 2) + 2
        try:
            r_inv = pow(r, -1, n)
        except ValueError:
            continue  # r nicht invertierbar - neu ziehen
        z = (m * pow(r, e, n)) % n
        return i2osp(z, k), r_inv


def blind_sign(blinded_msg: bytes, n: int, d: int) -> bytes:
    """Server: signiert blind. Sieht nur die verblindete Form (§6 Phase A.4)."""
    k = (n.bit_length() + 7) // 8
    if len(blinded_msg) != k:
        raise ValueError("Verblindete Nachricht hat die falsche Laenge.")
    m = os2ip(blinded_msg)
    if m >= n:
        raise ValueError("Verblindete Nachricht groesser als der Modulus.")
    return i2osp(pow(m, d, n), k)


def finalize(blind_sig: bytes, blind_inv: int, n: int) -> bytes:
    """Client: entblindet die Signatur (§6 Phase B.5)."""
    k = (n.bit_length() + 7) // 8
    s = (os2ip(blind_sig) * blind_inv) % n
    return i2osp(s, k)


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


def selftest(bits: int = KEY_BITS) -> None:
    """Roundtrip Blind -> BlindSign -> Finalize -> Verify. Wirft bei Fehlschlag."""
    key = generate_key(bits)
    pub = key.public_key().public_numbers()
    n, e, d = pub.n, pub.e, key.private_numbers().d

    msg = secrets.token_bytes(32)
    blinded, inv = blind(msg, n, e)
    sig = finalize(blind_sign(blinded, n, d), inv, n)
    if not verify(key.public_key(), msg, sig):
        raise AssertionError("Blindsignatur-Roundtrip fehlgeschlagen.")
    if verify(key.public_key(), secrets.token_bytes(32), sig):
        raise AssertionError("Signatur gilt fuer eine fremde Nachricht.")


if __name__ == "__main__":
    selftest()
    print("blind.py selftest ok (RFC 9474, RSABSSA-SHA384-PSS-Deterministic)")
