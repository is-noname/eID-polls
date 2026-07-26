"""Authentifizierung hinter einer Schnittstelle - Stub jetzt, SAML-SP spaeter.

MC-RFC-20260725-001 §4/§5: Die App implementiert niemals eigene eID-Krypto. Sie
ist reiner SAML-Service-Provider und sieht ausschliesslich das Pseudonym
(Restricted Identification) aus der signierten Assertion des eID-Servers.

Genau das ist hier die Schnittstelle: `Authenticator.authenticate() -> pseudonym`.
Alles hinter ihr - Blindsignatur, Ledger, Board - kennt nur diesen einen String
und aendert sich nicht, wenn der Stub durch den echten SP ersetzt wird.

STAND 2026-07-25: Es laeuft `CodeAuthenticator`. AusweisApp, ein eID-Server
gegen Test-PKI und Test-Ausweise sind auf dieser Maschine nicht vorhanden
(geprueft). Statt eines frei gewaehlten Namens verlangt er einen Code aus einer
konfigurierten Liste - er ersetzt damit einen bereits gueltig geprueften
Ausweis, ist aber selbst keine Identitaetspruefung. Jede Oberflaeche, die ihn
benutzt, muss das sichtbar sagen (siehe base.html: Admin/Debug, nicht die
Teilnehmeransicht - EIP-T-014).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol

STUB_PREFIX = "STUB-NO-REAL-IDENTITY:"
DEFAULT_CODES = tuple(f"testperson{i}" for i in range(1, 101))


class Authenticator(Protocol):
    """Liefert ein dienste- und kartenspezifisches Pseudonym."""

    name: str
    is_real_identity: bool

    def authenticate(self, credential: str) -> str:
        """Gibt das Pseudonym zurueck oder wirft AuthError."""
        ...

    def sample_codes(self) -> list[str]:
        """Beispiel-Zugangsdaten fuer die Oberflaeche - leer, wo es keine gibt."""
        ...


class AuthError(Exception):
    """Authentifizierung fehlgeschlagen."""


def _load_codes() -> frozenset[str]:
    """Liste gueltiger Zugangscodes - Umfang der aktuellen Testrunde, keine
    Obergrenze des Verfahrens (EIP-T-012). Ueber Umgebungsvariable oder Datei
    austauschbar, ohne Codeaenderung.
    """
    file_path = os.environ.get("EIDPOLL_ACCESS_CODES_FILE")
    if file_path:
        raw = Path(file_path).read_text(encoding="utf-8").splitlines()
    else:
        env = os.environ.get("EIDPOLL_ACCESS_CODES")
        raw = env.split(",") if env else list(DEFAULT_CODES)
    return frozenset(code.strip().casefold() for code in raw if code.strip())


class CodeAuthenticator:
    """Akzeptiert nur Zugangscodes aus einer konfigurierten Liste.

    Ein Code steht fachlich fuer einen bereits gueltig geprueften Ausweis
    (RFC §6): derselbe Code ergibt immer dasselbe Pseudonym (damit ist der
    zweite Abstimmversuch aus Phase A heraus testbar), ein unbekannter Code
    wird abgewiesen.

    Das Praefix im Rueckgabewert ist Absicht: taucht es je in Logs oder Daten
    eines ernstgemeinten Betriebs auf, ist sofort erkennbar, dass dort keine
    echte Identitaet geprueft wurde.
    """

    name = "Zugangscode (Testbetrieb, keine echte Identitaetspruefung)"
    is_real_identity = False

    def __init__(self) -> None:
        self._codes = _load_codes()

    def authenticate(self, credential: str) -> str:
        credential = credential.strip()
        if not credential:
            raise AuthError("Bitte eine Ausweisnummer eingeben.")
        if credential.casefold() not in self._codes:
            raise AuthError("Diese Ausweisnummer ist nicht hinterlegt.")
        digest = hashlib.sha256(credential.casefold().encode()).hexdigest()[:32]
        return f"{STUB_PREFIX}{digest}"

    def sample_codes(self) -> list[str]:
        """Die ersten Codes zum Vorzeigen.

        Auf einer oeffentlichen Demo sind die Codes kein Geheimnis, sondern der
        Zugang: Ohne sie kann niemand den Ablauf durchspielen. Dass sie hier
        stehen, ist deshalb kein Leck - es ist die Ansage, dass diese Instanz
        keine Identitaeten prueft.
        """
        return sorted(self._codes, key=lambda c: (len(c), c))[:3]


class SamlEidAuthenticator:
    """Echter eID-Flow nach TR-03124 / TR-03130 (RFC §5). NOCH NICHT GEBAUT.

    Der Ablauf, den diese Klasse zu bedienen hat, wenn Test-PKI und
    Test-Ausweise verfuegbar sind:

      1. Vom eID-Server ein TC-Token erzeugen lassen.
      2. Den lokalen eID-Client anstossen:
         http://127.0.0.1:24727/eID-Client?tcTokenURL=<URL-zum-TC-Token>
      3. Die AusweisApp fuehrt das eID-Protokoll mit dem Chip gegen den
         eID-Server aus - nicht gegen diese App.
      4. Nach dem Redirect die SAML-Assertion beim eID-Server abholen, ihre
         Signatur pruefen und das Pseudonym extrahieren.

    Port 24727 ist reiner Anstoss-Kanal, keine Datenleitung. Diese App sieht
    niemals Ausweisdaten - nur das Pseudonym aus Schritt 4.
    """

    name = "eID (SAML-Service-Provider)"
    is_real_identity = True

    def sample_codes(self) -> list[str]:
        return []

    def authenticate(self, credential: str) -> str:
        raise NotImplementedError(
            "Echter eID-Flow nicht gebaut - erfordert eID-Server gegen Test-PKI "
            "und Test-Ausweise (RFC §5, §14 Schritt 1-2)."
        )
