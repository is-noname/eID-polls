// Die Textform des Belegs: geschrieben beim Speichern, gelesen auf /verify.
//
// Erzeuger und Leser stehen bewusst in derselben Datei. Seit EIP-T-099 nimmt
// /verify die gespeicherte Beleg-Datei entgegen und holt Umfrage und Token
// daraus - damit ist die Zeile
//
//     Stimm-Token:  <64 Hex>
//
// keine Formulierung mehr, sondern eine SCHNITTSTELLE zwischen zwei Staenden
// der App: Wer heute speichert, prueft womoeglich in drei Wochen gegen eine
// neuere Version. Wird die Zeile umformuliert oder das Label geaendert, sind
// alle bereits gespeicherten Belege stumm - und zwar genau bei dem Schritt,
// der das ganze Verfahren rechtfertigt. Zulaessig ist Ergaenzen, nicht
// Umbenennen. Dasselbe gilt fuer "Umfrage:".
//
// beleg_datei_test.mjs haelt beide Seiten gegeneinander, und zwar gegen die
// echte Ausgabe von receiptText() - nicht gegen einen abgeschriebenen String,
// der die Aenderung stillschweigend mitmachen wuerde.
//
// Kein Netz, kein Speicher: Das Einlesen laeuft vollstaendig im Browser. Der
// Dateiinhalt wird nirgends hochgeladen und nirgends abgelegt (Vorgabe zu
// EIP-T-099: Datei-Annahme ja, zusaetzliche Speicherung nein).

/** Label der Token-Zeile. Aendern heisst: alte Belege werden unlesbar. */
export const TOKEN_LABEL = "Stimm-Token:";
/** Label der Umfrage-Zeile. Dieselbe Bindung wie bei TOKEN_LABEL. */
export const POLL_LABEL = "Umfrage:";

/** Text, der die Token-Zeile fuellt, wenn der Browser das Token vergessen hat. */
const OHNE_TOKEN = "nicht mehr in diesem Browser";

const HEX64 = /^[0-9a-f]{64}$/;

/** Beleg als Text - Inhalt identisch zum Kassenbon. */
export function receiptText(pollId, state, origin = location.origin) {
  const tokenLine = state.token
    ? `${TOKEN_LABEL}  ${state.token}`
    : `${TOKEN_LABEL}  ${OHNE_TOKEN} — nur noch in deinem gespeicherten Beleg.`;
  return [
    "DEIN BELEG — eID-Umfrage",
    `${POLL_LABEL}      ${pollId}`,
    `Blatt:        ${state.leaf}`,
    `Batch:        ${state.batch} (zugesagt)`,
    `Signatur:     ${state.belegSig}`,
    tokenLine,
    "",
    "Dein Eintrag erscheint mit Batch " + state.batch + " im öffentlichen Board —",
    "gebündelt mit anderen, spätestens nach dem Zeitdeckel, in jedem Fall beim",
    "Ende der Umfrage. Die Signatur bindet den Betreiber ab jetzt: Fehlt der",
    "Eintrag dann, ist dieser Beleg der Nachweis dafür.",
    "",
    "So prüfst du deine Stimme:",
    `  1. ${origin}/verify aufrufen`,
    "  2. Diese Datei dort ablegen — oder das Stimm-Token oben einfügen",
    "  3. Die angezeigte Auswahl muss deiner Stimme entsprechen",
    "",
    "Bewahre den Beleg wie eine Quittung auf: Wer das Stimm-Token hat, kann deine",
    "Stimme nachschlagen. Es ist zugleich der einzige Weg, sie selbst zu prüfen.",
  ].join("\n");
}

/** Raeumt eine Token-Eingabe auf: Grossschreibung, Rand- und Innenabstaende.
 *
 * Innenabstaende deshalb, weil der haeufigste Kopierfehler ein mitgenommener
 * Zeilenumbruch ist - der soll keine Fehlermeldung ausloesen, sondern
 * verschwinden.
 */
export function tokenNormalisieren(roh) {
  return String(roh ?? "").replace(/\s+/g, "").toLowerCase();
}

/** Sieht die Eingabe ueberhaupt wie ein Stimm-Token aus? */
export function tokenFormatOk(token) {
  return HEX64.test(token);
}

/** Fehler beim Lesen einer Beleg-Datei - die Meldung ist fuer die Oberflaeche. */
export class BelegFehler extends Error {
  constructor(message, grund) {
    super(message);
    this.name = "BelegFehler";
    this.grund = grund; // kurzer Schluessel fuer Meldung/Diagnose, nicht fuer Menschen
  }
}

/** Liest den Wert einer beschrifteten Zeile, sonst null. */
function feld(text, label) {
  for (const zeile of text.split(/\r?\n/)) {
    if (zeile.startsWith(label)) return zeile.slice(label.length).trim();
  }
  return null;
}

/** Holt Umfrage und Token aus dem Text einer Beleg-Datei.
 *
 * Gesucht wird ausschliesslich die beschriftete Zeile. Ein Streifzug nach
 * "irgendwelchen 64 Hex-Zeichen" waere bequemer und falsch: Der Blatt-Hash im
 * selben Beleg hat genau dieselbe Form, und eine Suche nach dem falschen Wert
 * endete in "kein Eintrag gefunden" - also in der Meldung, die sonst bedeutet,
 * dass der Betreiber die Stimme unterschlaegt.
 *
 * Wirft BelegFehler mit einer Meldung, die dem Menschen sagt, was mit der
 * Datei nicht stimmt.
 */
export function belegLesen(text) {
  if (!text || !text.trim()) {
    throw new BelegFehler("Die Datei ist leer.", "leer");
  }
  const rohToken = feld(text, TOKEN_LABEL);
  if (rohToken === null) {
    throw new BelegFehler(
      `In der Datei steht keine Zeile „${TOKEN_LABEL}“ — das sieht nicht nach einem Beleg dieser App aus.`,
      "kein-label");
  }
  if (rohToken.startsWith(OHNE_TOKEN)) {
    throw new BelegFehler(
      "Dieser Beleg enthält kein Stimm-Token: Er wurde gespeichert, nachdem der Browser es bereits "
      + "vergessen hatte. Ohne Token lässt sich die Stimme nicht wiederfinden — das ist der Preis "
      + "dafür, dass nichts sie mit diesem Gerät verbindet.",
      "ohne-token");
  }
  const token = tokenNormalisieren(rohToken);
  if (!tokenFormatOk(token)) {
    throw new BelegFehler(
      "Die Zeile „" + TOKEN_LABEL + "“ enthält kein gültiges Token — erwartet werden 64 Zeichen aus "
      + "Ziffern und den Buchstaben a bis f.",
      "kein-token");
  }
  return { poll: feld(text, POLL_LABEL) || "", token };
}
