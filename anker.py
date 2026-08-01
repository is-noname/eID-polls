"""Externe Zeitzeugen fuer die Batch-Root (EIP-ADR-20260801-002).

Die Batch-Kette aus EIP-ADR-20260728-001 macht Loeschen erkennbar - gegenueber
jedem, der die alte Root kennt. Gegenueber jemandem, der das Board zum ersten
Mal laedt, leistet sie nichts: Ein Betreiber mit Schreibzugriff rechnet
``merkle_root`` und ``batch_root`` fuer alle Batches neu, und danach ist die
Kette in sich stimmig. Genau das fuehrt die Angriffsdemo "Board umschreiben"
vor (demo.py).

Dagegen hilft eine Zeitaussage von aussen: Wer eine Root zu einem Zeitpunkt
bezeugen liess, kann sie nicht nachtraeglich durch eine andere ersetzen. Zwei
Zeugen, weil sie unterschiedlich versagen:

  rfc3161          Ein Zeitstempel-Token nach RFC 3161 von einer oeffentlichen
                   TSA. Antwort in Sekunden, pruefbar mit ``openssl ts -verify``
                   ohne einen weiteren Dienst zu befragen - aber eine zentrale
                   Stelle, die falsch datieren oder mit uns kooperieren koennte.
  opentimestamps   Derselbe Hash an die oeffentlichen OpenTimestamps-Kalender,
                   die ihn gebuendelt in eine Bitcoin-Transaktion schreiben.
                   Pruefbar gegen die Blockheader, ohne den Kalendern, uns oder
                   einer TSA zu glauben - aber erst nach Bestaetigung des
                   Blocks, und bis dahin ist der Beleg eine Zusage.

Was das **nicht** leistet: Split-View. Ein Betreiber, der von Anfang an zwei
Boards fuehrt, laesst beide Roots ehrlich datieren. Zur Aufdeckung von
Equivocation gehoert Aufzaehlbarkeit - irgendwer muss alle je veroeffentlichten
Roots nebeneinanderlegen koennen - und die entsteht erst durch Gegenzeichner
(EIP-T-036). Der Unterschied gehoert an jede Stelle, an der ein Anker angezeigt
wird (KODEX §4).

Bezeugt wird ``batch_root(n)``, das Kettenglied - nicht die Merkle-Root eines
einzelnen Batches. Wer das spaeteste Kettenglied datiert hat, hat alle
frueheren mitdatiert.

Beide Zeugen bekommen **dieselben Bytes**: die 32 Rohbytes der Root. Beide
Belege binden damit ``SHA256(bytes.fromhex(root))`` - bei RFC 3161 als
messageImprint, bei OpenTimestamps als Datei-Hash. Deshalb reicht ein einziger
Vergleich fuer beide (``erwarteter_hash``), und deshalb ist die Pruefdatei fuer
einen Dritten in beiden Faellen dieselbe.

Nichts davon ist selbstgeschrieben (KODEX §3): RFC 3161 laeuft ueber
``rfc3161-client`` (Sigstore), OpenTimestamps ueber die Referenzimplementierung
``opentimestamps-client``. Fehlt eine der beiden Bibliotheken, faellt genau
dieser Zeuge aus und die App laeuft weiter - ein Anker ist eine Zugabe an
Nachpruefbarkeit, keine Voraussetzung fuer eine Stimmabgabe.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

__all__ = [
    "AnkerNichtVerfuegbar",
    "OpenTimestampsZeuge",
    "Quittung",
    "Rfc3161Zeuge",
    "Zeitzeuge",
    "Zustand",
    "erwarteter_hash",
    "standard_zeugen",
]

# ausstehend      beauftragt, noch keine Antwort
# bezeugt         Beleg liegt vor, aber noch nicht endgueltig (OTS: Kalender-
#                 quittung ohne Bitcoin-Attestierung)
# endgueltig      Beleg liegt vor und ist vollstaendig
# fehlgeschlagen  nach mehreren Versuchen kein Beleg
Zustand = Literal["ausstehend", "bezeugt", "endgueltig", "fehlgeschlagen"]

# Voreinstellungen. Die TSA ist freetsa.org: kein Konto, keine Kosten,
# Zertifikat gueltig bis 2040. zeitstempel.dfn.de scheidet aus - dort ist
# kommerzielle Nutzung untersagt, und unsere Betriebsform ist offen
# (EIP-T-065).
FREETSA_URL = "https://freetsa.org/tsr"
FREETSA_CACERT = "https://freetsa.org/files/cacert.pem"
FREETSA_TSACERT = "https://freetsa.org/files/tsa.crt"
OTS_KALENDER = (
    "https://alice.btc.calendar.opentimestamps.org",
    "https://bob.btc.calendar.opentimestamps.org",
    "https://finney.calendar.eternitywall.com",
    "https://btc.calendar.catallaxy.com",
)


class AnkerNichtVerfuegbar(RuntimeError):
    """Der Zeuge kann nicht arbeiten - Bibliothek fehlt oder Dienst antwortet nicht.

    Bewusst dieselbe Ausnahme fuer beides: Fuer den Aufrufer ist der Unterschied
    zwischen "nicht installiert" und "nicht erreichbar" kein anderer Fall,
    sondern derselbe - dieser Batch hat gerade keinen Anker. Der Unterschied
    steht im Text und landet so im Debug-Modul.
    """


@dataclass(frozen=True)
class Quittung:
    """Was ein Zeuge zurueckgibt.

    ``endgueltig`` unterscheidet die OpenTimestamps-Kalenderquittung (eine
    Zusage) von der fertigen Bitcoin-Attestierung (eine Bezeugung). Ein Beleg,
    der nie aufgewertet wurde, ist keine Blockchain-Bezeugung, und die
    Oberflaeche darf ihn nicht als eine ausgeben.
    """

    beleg: bytes
    bezeugt_um: datetime | None
    endgueltig: bool
    # Was der Beleg sagt, wo er keine Uhrzeit hergibt - bei OpenTimestamps die
    # Bitcoin-Blockhoehe. Anzeigetext, keine zweite Datenquelle.
    hinweis: str | None = None

    @property
    def zustand(self) -> Zustand:
        return "endgueltig" if self.endgueltig else "bezeugt"


def erwarteter_hash(root: str) -> str:
    """Der Hash, den ein Beleg zu dieser Root binden muss.

    Beide Zeugen bekommen die Rohbytes der Root und hashen sie mit SHA-256 -
    RFC 3161 in den messageImprint, OpenTimestamps in den Datei-Hash. Der
    Vergleich in der Konsistenzpruefung laeuft deshalb gegen genau diesen Wert
    und nicht gegen die Root selbst.
    """
    return hashlib.sha256(bytes.fromhex(root)).hexdigest()


class Zeitzeuge(Protocol):
    """Ein externer Dienst, der einen Hash datiert.

    Die drei Methoden trennen bewusst, was verschieden schiefgehen kann:
    Beauftragen ist ein Netzaufruf, Aufwerten ist ein spaeterer Netzaufruf, und
    ``bezeugter_hash`` ist reine Belegverarbeitung ohne Netz - nur deshalb kann
    die Konsistenzpruefung (E6.1) auch dann laufen, wenn kein Dienst erreichbar
    ist.
    """

    name: str
    titel: str
    endung: str

    def beauftrage(self, root: str) -> Quittung: ...

    def werte_auf(self, beleg: bytes) -> Quittung | None: ...

    def bezeugter_hash(self, beleg: bytes) -> str | None: ...

    def pruefanleitung(self, basisname: str) -> list[str]: ...


class Rfc3161Zeuge:
    """Zeitstempel-Token nach RFC 3161 von einer oeffentlichen TSA.

    Endgueltig mit der ersten Antwort: Ein RFC-3161-Token ist fertig, wenn es
    ankommt. ``werte_auf`` hat hier nichts zu tun.
    """

    name = "rfc3161"
    titel = "RFC-3161-Zeitstempel"
    endung = "tsr"

    def __init__(self, url: str = FREETSA_URL, timeout: float = 20.0) -> None:
        self.url = url
        self.timeout = timeout

    def beauftrage(self, root: str) -> Quittung:
        import urllib.error
        import urllib.request

        builder, hash_algorithm, decode = self._lade()
        anfrage = (
            builder()
            .data(bytes.fromhex(root))
            .hash_algorithm(hash_algorithm.SHA256)
            # Nonce an: Ohne ihn koennte eine TSA (oder ein Zwischenstueck) eine
            # frueher erzeugte Antwort auf denselben Hash wiederverwenden.
            .nonce(nonce=True)
            .build()
        )
        req = urllib.request.Request(
            self.url,
            data=anfrage.as_bytes(),
            headers={"Content-Type": "application/timestamp-query"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as antwort:
                roh = antwort.read()
        except (urllib.error.URLError, OSError) as exc:
            raise AnkerNichtVerfuegbar(f"TSA {self.url} nicht erreichbar: {exc}") from exc

        token = decode(roh)
        # Der Beleg wird gegen die eigene Anfrage geprueft, bevor er
        # gespeichert wird: Ein Token, das einen anderen Hash traegt, ist kein
        # Anker fuer diese Root - und stillschweigend abgelegt waere er
        # schlimmer als keiner.
        imprint = token.tst_info.message_imprint.message.hex()
        if imprint != erwarteter_hash(root):
            raise AnkerNichtVerfuegbar(
                f"TSA hat einen anderen Hash bezeugt ({imprint[:16]}... statt "
                f"{erwarteter_hash(root)[:16]}...)"
            )
        return Quittung(beleg=roh, bezeugt_um=token.tst_info.gen_time, endgueltig=True)

    def werte_auf(self, beleg: bytes) -> Quittung | None:
        return None

    def bezeugter_hash(self, beleg: bytes) -> str | None:
        try:
            _, _, decode = self._lade()
            return str(decode(beleg).tst_info.message_imprint.message.hex())
        except Exception:
            # Ein unlesbarer Beleg ist selbst ein Befund, aber keiner, den diese
            # Methode entscheidet - sie sagt nur "kein Hash zu vergleichen".
            return None

    def pruefanleitung(self, basisname: str) -> list[str]:
        return [
            f"curl -sO {FREETSA_CACERT}",
            f"curl -sO {FREETSA_TSACERT}",
            f"openssl ts -verify -data {basisname}.root -in {basisname}.tsr "
            "-CAfile cacert.pem -untrusted tsa.crt",
        ]

    @staticmethod
    def _lade() -> tuple[object, object, object]:
        try:
            from rfc3161_client import (  # type: ignore[import-not-found]
                HashAlgorithm,
                TimestampRequestBuilder,
                decode_timestamp_response,
            )
        except ImportError as exc:
            raise AnkerNichtVerfuegbar(
                "Bibliothek 'rfc3161-client' fehlt (pip install -r requirements.txt)"
            ) from exc
        return TimestampRequestBuilder, HashAlgorithm, decode_timestamp_response


class OpenTimestampsZeuge:
    """OpenTimestamps: Kalenderquittung sofort, Bitcoin-Attestierung spaeter.

    Zwei Stufen, die auseinanderzuhalten sind. ``beauftrage`` liefert die
    Quittung der Kalender - eine Zusage, in einen Block zu kommen. Erst
    ``werte_auf`` holt die fertige Attestierung, sobald der Block bestaetigt
    ist; bis dahin gibt es nichts Neues und die Methode gibt ``None`` zurueck.
    """

    name = "opentimestamps"
    titel = "OpenTimestamps (Bitcoin)"
    endung = "ots"

    def __init__(
        self, kalender: tuple[str, ...] = OTS_KALENDER, timeout: float = 20.0
    ) -> None:
        self.kalender = kalender
        self.timeout = timeout

    def beauftrage(self, root: str) -> Quittung:
        ots = _OtsModule.laden()
        datei = ots.detached(bytes.fromhex(root))
        try:
            ots.cmds.create_timestamp(datei.timestamp, list(self.kalender), self._args())
        except Exception as exc:
            raise AnkerNichtVerfuegbar(f"OpenTimestamps-Kalender: {exc}") from exc
        if not datei.timestamp.attestations and not list(datei.timestamp.ops):
            raise AnkerNichtVerfuegbar("Kein Kalender hat geantwortet")
        return self._quittung(ots, datei)

    def werte_auf(self, beleg: bytes) -> Quittung | None:
        ots = _OtsModule.laden()
        datei = ots.lesen(beleg)
        try:
            veraendert = ots.cmds.upgrade_timestamp(datei.timestamp, self._args())
        except Exception as exc:
            raise AnkerNichtVerfuegbar(f"OpenTimestamps-Aufwertung: {exc}") from exc
        if not veraendert:
            return None
        return self._quittung(ots, datei)

    def bezeugter_hash(self, beleg: bytes) -> str | None:
        try:
            return str(_OtsModule.laden().lesen(beleg).file_digest.hex())
        except Exception:
            return None

    def pruefanleitung(self, basisname: str) -> list[str]:
        return [
            "pip install opentimestamps-client",
            f"ots verify {basisname}.root.ots",
            f"# fehlt die Bitcoin-Attestierung noch: ots upgrade {basisname}.root.ots",
        ]

    def _args(self) -> object:
        import argparse

        ots = _OtsModule.laden()
        return argparse.Namespace(
            calendar_urls=list(self.kalender),
            calendar_whitelist=set(self.kalender),
            whitelist=set(self.kalender),
            # m: wie viele Kalender antworten muessen. Zwei statt aller vier -
            # ein einzelner ausgefallener Kalender darf den Anker nicht
            # verhindern, ein einzelner erreichbarer ihn nicht allein tragen.
            m=min(2, len(self.kalender)),
            timeout=self.timeout,
            use_btc_wallet=False,
            setup_bitcoin=False,
            wait=False,
            wait_interval=5,
            verbosity=0,
            cache=ots.leerer_cache(),
        )

    def _quittung(self, ots: "_OtsModule", datei: object) -> Quittung:
        fertig = bool(ots.cmds.is_timestamp_complete(datei.timestamp, self._args()))
        hoehe = ots.block_hoehe(datei) if fertig else None
        return Quittung(
            beleg=ots.serialisieren(datei),
            # Keine Zeit: Die Attestierung nennt die Blockhoehe, nicht die Zeit.
            # Wer die Zeit will, prueft den Beleg gegen die Blockheader - genau
            # darum geht es bei diesem Zeugen. Eine Zeit von einem
            # Block-Explorer zu holen und sie hier hinzuschreiben, waere eine
            # dritte Vertrauensstelle, die niemand verlangt hat.
            bezeugt_um=None,
            endgueltig=fertig,
            hinweis=f"Bitcoin-Block {hoehe}" if hoehe is not None else None,
        )


class _OtsModule:
    """Die OpenTimestamps-Bibliothek hinter einer schmalen Flaeche.

    Der Import liegt hier und nicht oben im Modul, damit eine Instanz ohne die
    Bibliothek startet - und er liegt an *einer* Stelle, damit die Kenntnis
    ueber den Aufbau der Fremdbibliothek nicht durch die Zeugenklasse sickert.
    """

    _geladen: "_OtsModule | None" = None

    def __init__(self) -> None:
        try:
            import otsclient.cache  # type: ignore[import-not-found]
            import otsclient.cmds  # type: ignore[import-not-found]
            from opentimestamps.core.op import OpSHA256  # type: ignore[import-not-found]
            from opentimestamps.core.serialize import (  # type: ignore[import-not-found]
                BytesDeserializationContext,
                BytesSerializationContext,
            )
            from opentimestamps.core.timestamp import (  # type: ignore[import-not-found]
                DetachedTimestampFile,
                Timestamp,
            )
        except ImportError as exc:
            raise AnkerNichtVerfuegbar(
                "Bibliothek 'opentimestamps-client' fehlt (pip install -r requirements.txt)"
            ) from exc
        self.cmds = otsclient.cmds
        self._cache = otsclient.cache.TimestampCache
        self._op = OpSHA256
        self._ser = BytesSerializationContext
        self._deser = BytesDeserializationContext
        self._datei = DetachedTimestampFile
        self._stamp = Timestamp

    @classmethod
    def laden(cls) -> "_OtsModule":
        if cls._geladen is None:
            cls._geladen = cls()
        return cls._geladen

    def detached(self, rohbytes: bytes) -> object:
        return self._datei(self._op(), self._stamp(hashlib.sha256(rohbytes).digest()))

    def lesen(self, beleg: bytes) -> object:
        return self._datei.deserialize(self._deser(beleg))

    def serialisieren(self, datei: object) -> bytes:
        ctx = self._ser()
        datei.serialize(ctx)  # type: ignore[attr-defined]
        return bytes(ctx.getbytes())

    def leerer_cache(self) -> object:
        # Pfad None: kein Zwischenspeicher auf Platte. Der Cache spart
        # Kalenderabfragen bei vielen Dateien - wir werten je Batch einzeln auf.
        return self._cache(None)

    def block_hoehe(self, datei: object) -> int | None:
        """Die Blockhoehe der Bitcoin-Attestierung, wenn eine da ist."""
        from opentimestamps.core.notary import (  # type: ignore[import-not-found]
            BitcoinBlockHeaderAttestation,
        )

        hoehen = [
            att.height
            for _, att in datei.timestamp.all_attestations()  # type: ignore[attr-defined]
            if isinstance(att, BitcoinBlockHeaderAttestation)
        ]
        return min(hoehen) if hoehen else None


def standard_zeugen(
    tsa_url: str = FREETSA_URL, kalender: tuple[str, ...] = OTS_KALENDER
) -> tuple[Zeitzeuge, ...]:
    """Die beiden Zeugen aus EIP-ADR-20260801-002, E1 und E2."""
    return (Rfc3161Zeuge(tsa_url), OpenTimestampsZeuge(kalender))
