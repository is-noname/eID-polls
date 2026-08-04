// Beleg schreiben und wieder einlesen - gegen die echte Ausgabe (EIP-T-099).
//
//     node beleg_datei_test.mjs
//
// Der Punkt dieses Tests ist die Richtung: geprueft wird receiptText() gegen
// belegLesen(), nicht gegen einen hier abgeschriebenen Beispieltext. Ein
// abgeschriebener Text machte jede Umformulierung stillschweigend mit - und
// genau das ist der Fall, der weh tut: Wer vorige Woche gespeichert hat,
// bekaeme seine Datei diese Woche nicht mehr eingelesen, und zwar bei dem
// Schritt, der das ganze Verfahren rechtfertigt.
//
// static/beleg_datei.js kommt deshalb ohne Import aus dem Browser aus - kein
// DOM, kein Netz, keine Vendor-Datei. Es laesst sich hier unveraendert laden.

import assert from "node:assert/strict";
import {
  receiptText,
  belegLesen,
  tokenNormalisieren,
  tokenFormatOk,
  BelegFehler,
  TOKEN_LABEL,
} from "./static/beleg_datei.js";

const POLL = "testumfrage";
const TOKEN = "a1b2c3d4".repeat(8); // 64 Hex
const STATE = {
  leaf: "f".repeat(64),
  batch: 7,
  belegSig: "9".repeat(128),
  token: TOKEN,
};
const ORIGIN = "https://beispiel.invalid";

function fall(name, fn) {
  try {
    fn();
    console.log(`ok   ${name}`);
  } catch (err) {
    console.error(`FAIL ${name}: ${err.message}`);
    process.exitCode = 1;
  }
}

fall("Rundum: was receiptText schreibt, liest belegLesen zurueck", () => {
  const gelesen = belegLesen(receiptText(POLL, STATE, ORIGIN));
  assert.equal(gelesen.token, TOKEN);
  assert.equal(gelesen.poll, POLL);
});

fall("Rundum: auch mit Windows-Zeilenenden (Datei ging durch einen Editor)", () => {
  const text = receiptText(POLL, STATE, ORIGIN).replace(/\n/g, "\r\n");
  assert.equal(belegLesen(text).token, TOKEN);
});

fall("Rundum: fuehrende Leerzeile und angehaengter Rand stoeren nicht", () => {
  const text = `\n${receiptText(POLL, STATE, ORIGIN)}\n\n`;
  assert.equal(belegLesen(text).token, TOKEN);
});

fall("Blatt-Hash wird nicht mit dem Token verwechselt", () => {
  // Beide sind 64 Hex-Zeichen. Wer im Text nach "irgendwelchen 64 Hex" sucht,
  // findet zuerst das Blatt - und die Suche endete in "kein Eintrag", also in
  // der Auskunft, die sonst bedeutet: der Betreiber ist im Verzug.
  const gelesen = belegLesen(receiptText(POLL, STATE, ORIGIN));
  assert.equal(gelesen.token, TOKEN);
  assert.notEqual(gelesen.token, STATE.leaf);
});

fall("Beleg ohne Token nennt seinen Grund", () => {
  const ohne = { ...STATE, token: undefined };
  const text = receiptText(POLL, ohne, ORIGIN);
  assert.ok(text.includes(TOKEN_LABEL), "Label fehlt auch im tokenlosen Beleg nicht");
  assert.throws(() => belegLesen(text), (err) => err instanceof BelegFehler && err.grund === "ohne-token");
});

fall("Fremde Datei wird abgewiesen, nicht halb gedeutet", () => {
  assert.throws(() => belegLesen("Einkaufsliste\nMilch\nBrot\n"),
                (err) => err.grund === "kein-label");
  assert.throws(() => belegLesen("   \n\n"), (err) => err.grund === "leer");
  assert.throws(() => belegLesen(`${TOKEN_LABEL}  zu kurz`), (err) => err.grund === "kein-token");
});

fall("Token-Normalisierung: Zeilenumbruch und Grossschreibung fallen weg", () => {
  assert.equal(tokenNormalisieren(` ${TOKEN.toUpperCase()}\n`), TOKEN);
  assert.equal(tokenNormalisieren(`${TOKEN.slice(0, 32)}\n${TOKEN.slice(32)}`), TOKEN);
  assert.equal(tokenNormalisieren(null), "");
});

fall("Formatpruefung trennt Laenge und Zeichensatz von 'nicht gefunden'", () => {
  assert.ok(tokenFormatOk(TOKEN));
  assert.ok(!tokenFormatOk(TOKEN.slice(0, 63)));
  assert.ok(!tokenFormatOk(`${TOKEN.slice(0, 63)}z`));
  assert.ok(!tokenFormatOk(""));
});

if (!process.exitCode) console.log("beleg_datei_test.mjs: alle Faelle gruen");
