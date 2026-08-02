"""Die rohe RSA-Privatoperation, gerechnet von OpenSSL statt von Python.

Warum es diese Datei gibt (EIP-T-093, KODEX § 3): Im serverseitigen Stimmweg
lief genau ein selbst geschriebener Krypto-Schritt, das `pow(m, d, n)` in
blind_sign(). CPythons pow() rechnet weder in konstanter Zeit noch mit
Base-Blinding - damit stand die Signieroperation im Grundsatz fuer
Timing-Angriffe offen (Brumley/Boneh 2003 zeigt das ueber Netzgrenzen hinweg).
Betroffen war nicht irgendein Schluessel, sondern der Signaturschluessel der
Umfrage: wer ihn hat, stellt beliebig viele Stimmzettel aus.

OpenSSL blendet RSA-Privatoperationen intern ab und rechnet sie ueber die CRT
mit konstanter Zeit. Diese Datei erreicht sie ueber ctypes-Bindungen an
libcrypto - `EVP_PKEY_decrypt` mit RSA_NO_PADDING liefert m^d mod n, also genau
die Operation aus RFC 9474 §4.3 Schritt 2.

Zur Wahl der Funktion: RSA_private_encrypt() waere der kuerzere Weg, ist in
OpenSSL 3 aber deprecated und umgeht die Provider-Schicht. EVP_PKEY_decrypt ist
der unterstuetzte Weg und rechnet dasselbe.

Was das *nicht* heisst: Die Bindung ist kein Audit. Sie tauscht eigene Krypto
gegen zugekaufte - der Bindungscode hier ist zu pruefen, aber er ist Glue und
keine Krypto. Und sie haertet allein die Signieroperation; ueber das
Zeitverhalten des uebrigen Anfragewegs sagt sie nichts.

Faellt libcrypto aus, wirft dieses Modul. Es gibt bewusst **keinen Rueckfall
auf pow()**: ein stiller Rueckfall waere die ungehaertete Operation unter dem
Namen der gehaerteten, und niemand wuerde es merken. Der Aufrufer meldet den
Ausfall ans Debug-Modul und weist ab.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import threading

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# RFC 8017 rohe Operation, ohne jede Kodierung: openssl/rsa.h
RSA_NO_PADDING = 3

_lock = threading.Lock()
_lib: ctypes.CDLL | None = None
_ladefehler: str | None = None


class OpenSSLNichtVerfuegbar(RuntimeError):
    """libcrypto fehlt, ist zu alt oder die Signieroperation schlug fehl.

    Eigene Klasse, damit der Aufrufer sie von einer ungueltigen Anfrage
    (ValueError) unterscheiden kann: das eine ist ein Betriebsfehler des
    Servers, das andere eine Abweisung des Clients.
    """


def _bind(lib: ctypes.CDLL) -> None:
    """Signaturen setzen. Ohne restype gaebe ctypes Zeiger als int zurueck und
    schnitte sie auf 32 Bit ab - das ist der klassische Absturz in solchen
    Bindungen und faellt erst auf Maschinen mit hohen Adressen auf."""
    p, i, sz = ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t

    lib.BIO_new_mem_buf.restype = p
    lib.BIO_new_mem_buf.argtypes = [p, i]
    lib.BIO_free.argtypes = [p]

    lib.PEM_read_bio_PrivateKey.restype = p
    lib.PEM_read_bio_PrivateKey.argtypes = [p, p, p, p]
    lib.EVP_PKEY_free.argtypes = [p]
    lib.EVP_PKEY_get_size.restype = i
    lib.EVP_PKEY_get_size.argtypes = [p]

    lib.EVP_PKEY_CTX_new_from_pkey.restype = p
    lib.EVP_PKEY_CTX_new_from_pkey.argtypes = [p, p, p]
    lib.EVP_PKEY_CTX_free.argtypes = [p]
    lib.EVP_PKEY_decrypt_init.restype = i
    lib.EVP_PKEY_decrypt_init.argtypes = [p]
    lib.EVP_PKEY_CTX_set_rsa_padding.restype = i
    lib.EVP_PKEY_CTX_set_rsa_padding.argtypes = [p, i]
    lib.EVP_PKEY_decrypt.restype = i
    lib.EVP_PKEY_decrypt.argtypes = [p, p, ctypes.POINTER(sz), p, sz]

    lib.ERR_get_error.restype = ctypes.c_ulong
    lib.ERR_error_string_n.argtypes = [ctypes.c_ulong, p, sz]


def _laden() -> ctypes.CDLL:
    global _lib, _ladefehler
    with _lock:
        if _lib is not None:
            return _lib
        if _ladefehler is not None:
            raise OpenSSLNichtVerfuegbar(_ladefehler)
        try:
            pfad = ctypes.util.find_library("crypto")
            if pfad is None:
                raise OSError("find_library('crypto') findet keine libcrypto.")
            lib = ctypes.CDLL(pfad)
            # EVP_PKEY_CTX_new_from_pkey und EVP_PKEY_get_size gibt es erst ab
            # OpenSSL 3.0. Das Fehlen faellt hier auf und nicht mitten in einer
            # Signieranfrage.
            _bind(lib)
        except (OSError, AttributeError) as exc:
            _ladefehler = (
                f"OpenSSL (libcrypto, mindestens 3.0) ist nicht nutzbar: {exc}. "
                "Ohne sie wird die RSA-Privatoperation nicht gehaertet gerechnet, "
                "und es werden deshalb keine Stimm-Token ausgegeben."
            )
            raise OpenSSLNichtVerfuegbar(_ladefehler) from exc
        _lib = lib
        return lib


def _fehlertext(lib: ctypes.CDLL) -> str:
    puffer = ctypes.create_string_buffer(256)
    code = lib.ERR_get_error()
    if not code:
        return "kein OpenSSL-Fehlercode gesetzt"
    lib.ERR_error_string_n(code, puffer, len(puffer))
    return puffer.value.decode("utf-8", "replace")


def private_op(key: rsa.RSAPrivateKey, data: bytes) -> bytes:
    """m^d mod n, gerechnet von OpenSSL. data und Rueckgabe sind k Byte lang.

    Args:
        key: Der private Schluessel. Wird als PKCS8-PEM an libcrypto gereicht -
            der Umweg kostet einen Parse je Aufruf und erspart es, d, p und q
            einzeln durch ctypes zu tragen. Der Schluessel liegt ohnehin schon
            als PEM in der config-Tabelle; hier entsteht keine Kopie, die es
            nicht schon gaebe.
        data: Die verblindete Nachricht, bereits auf Laenge und Bereich
            geprueft.

    Raises:
        OpenSSLNichtVerfuegbar: libcrypto fehlt oder die Operation schlug fehl.
    """
    lib = _laden()

    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    bio = pkey = ctx = None
    try:
        bio = lib.BIO_new_mem_buf(pem, len(pem))
        if not bio:
            raise OpenSSLNichtVerfuegbar(f"BIO_new_mem_buf: {_fehlertext(lib)}")
        pkey = lib.PEM_read_bio_PrivateKey(bio, None, None, None)
        if not pkey:
            raise OpenSSLNichtVerfuegbar(f"PEM_read_bio_PrivateKey: {_fehlertext(lib)}")

        k = lib.EVP_PKEY_get_size(pkey)
        if k <= 0:
            raise OpenSSLNichtVerfuegbar(f"EVP_PKEY_get_size: {_fehlertext(lib)}")
        if len(data) != k:
            raise OpenSSLNichtVerfuegbar(
                f"Eingabe ist {len(data)} Byte, der Modulus {k} Byte."
            )

        ctx = lib.EVP_PKEY_CTX_new_from_pkey(None, pkey, None)
        if not ctx:
            raise OpenSSLNichtVerfuegbar(f"EVP_PKEY_CTX_new_from_pkey: {_fehlertext(lib)}")
        if lib.EVP_PKEY_decrypt_init(ctx) != 1:
            raise OpenSSLNichtVerfuegbar(f"EVP_PKEY_decrypt_init: {_fehlertext(lib)}")
        # Ohne diesen Schritt wuerde OpenSSL PKCS#1-Padding erwarten und die
        # Rechnung als ungueltiges Chiffrat verwerfen.
        if lib.EVP_PKEY_CTX_set_rsa_padding(ctx, RSA_NO_PADDING) != 1:
            raise OpenSSLNichtVerfuegbar(f"RSA_NO_PADDING: {_fehlertext(lib)}")

        aus = ctypes.create_string_buffer(k)
        laenge = ctypes.c_size_t(k)
        if lib.EVP_PKEY_decrypt(ctx, aus, ctypes.byref(laenge), data, len(data)) != 1:
            raise OpenSSLNichtVerfuegbar(f"EVP_PKEY_decrypt: {_fehlertext(lib)}")
        # NO_PADDING liefert die volle Modulusbreite; die Linksauffuellung ist
        # eine Zusicherung fuer den Fall, dass eine Provider-Umsetzung fuehrende
        # Nullen abschneidet.
        return aus.raw[: laenge.value].rjust(k, b"\x00")
    finally:
        if ctx:
            lib.EVP_PKEY_CTX_free(ctx)
        if pkey:
            lib.EVP_PKEY_free(pkey)
        if bio:
            lib.BIO_free(bio)


def verfuegbar() -> tuple[bool, str]:
    """Fuer Startpruefung und Debug-Modul: laeuft die Bindung? Wirft nicht."""
    try:
        _laden()
    except OpenSSLNichtVerfuegbar as exc:
        return False, str(exc)
    return True, "OpenSSL-Privatoperation (EVP_PKEY_decrypt, RSA_NO_PADDING) nutzbar."
