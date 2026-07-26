// QR-Code als Inline-SVG. Bewusst ohne Canvas und ohne Server: der Code
// enthaelt das Stimm-Token, es darf den Browser nicht verlassen.
import qrcode from "/static/vendor-qrcode.js";

const QUIET_ZONE = 4; // Module Rand, von der QR-Spezifikation gefordert

/** Erzeugt ein SVG mit dem QR-Code fuer text.
 *
 * Args:
 *   text: Inhalt des Codes.
 *   size: Kantenlaenge des SVG in px, Rand eingeschlossen.
 *   dark: Farbe der Module.
 *   light: Hintergrundfarbe, fuellt auch den Rand.
 */
export function qrSvg(text, { size = 168, dark = "#1a1a1a", light = "#fdfdf8" } = {}) {
  const qr = qrcode(0, "M"); // Typnummer 0 = Groesse automatisch nach Datenmenge
  qr.addData(text);
  qr.make();

  // In Modulen gerechnet und erst per viewBox skaliert: so bleibt der Rand
  // exakt 4 Module breit, unabhaengig davon wie gross der Code ausfaellt.
  const count = qr.getModuleCount();
  const span = count + 2 * QUIET_ZONE;
  let rects = "";
  for (let row = 0; row < count; row++) {
    for (let col = 0; col < count; col++) {
      if (!qr.isDark(row, col)) continue;
      rects += `<rect x="${col + QUIET_ZONE}" y="${row + QUIET_ZONE}" width="1" height="1"/>`;
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"`
    + ` viewBox="0 0 ${span} ${span}" shape-rendering="crispEdges"`
    + ` role="img" aria-label="QR-Code zum Prüfen der Stimme">`
    + `<rect width="${span}" height="${span}" fill="${light}"/>`
    + `<g fill="${dark}">${rects}</g></svg>`;
}
