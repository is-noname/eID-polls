// static/blind.js gegen den Testvektor aus RFC 9474 Anhang A.4.
//
//     node blind_vektor.mjs
//
// Warum das eine eigene Datei ist und nicht in ballot_test.mjs steht: dort ist
// der Server gestellt und die Signatur eine Attrappe - der Test prueft den
// Zustandsverlauf, nicht die Krypto. Hier laeuft es umgekehrt, es gibt keinen
// Server, sondern nur Zahlen aus dem RFC.
//
// Und warum es nicht browser_test.py ersetzt: browser_test zeigt, dass beide
// Seiten *miteinander* rechnen. Dieser Test zeigt, dass die JS-Seite mit dem
// RFC rechnet. Beide zusammen schliessen den Fall aus, dass Python und
// JavaScript denselben Fehler machen und sich deshalb einig sind (EIP-T-008).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { blindTokenMitFaktor, finalizeSignature, emsaPssEncode, hexToBytes, bytesToHex }
  from "./static/blind.js";

const hier = dirname(fileURLToPath(import.meta.url));
const v = JSON.parse(readFileSync(join(hier, "rfc9474_a4.json"), "utf8"));

const n = BigInt(`0x${v.n}`);
const inv = BigInt(`0x${v.inv}`);
const msg = hexToBytes(v.msg);

const fehler = [];
function pruefe(was, ist, soll) {
  if (ist !== soll) fehler.push(was);
  console.log(`[${ist === soll ? "  ok  " : " FEHL "}] ${was}`);
}

// PrepareIdentity: die Deterministic-Variante laesst die Nachricht in Ruhe.
pruefe("prepared_msg (PrepareIdentity)", v.prepared_msg, v.msg);

// bitLength(n) - 1 wie in blindTokenMitFaktor, siehe blind.py:emsa_pss_encode.
const encoded = await emsaPssEncode(msg, n.toString(2).length - 1);
pruefe("encoded_msg (EMSA-PSS-ENCODE, MGF1 mit SHA-384)", bytesToHex(encoded), v.encoded_msg);

// Der Vektor gibt den Kehrwert an; blindTokenMitFaktor erwartet den Faktor.
const r = modInverse(inv, n);
const geblendet = await blindTokenMitFaktor(msg, v.n, v.e, r);
assert.notEqual(geblendet, null, "Blendfaktor aus dem RFC ist nicht invertierbar - Rechenfehler.");
pruefe("blinded_msg (Blind)", geblendet.blindedHex, v.blinded_msg);
pruefe("inv (Blind)", BigInt(`0x${geblendet.inv}`).toString(16), inv.toString(16));

pruefe("sig (Finalize)", finalizeSignature(v.blind_sig, v.inv, v.n), v.sig);

// Kleiner eigener Kehrwert, damit der Test nicht von blind.js abhaengt, um
// blind.js zu pruefen.
function modInverse(a, m) {
  let [altR, rest] = [((a % m) + m) % m, m];
  let [altS, s] = [1n, 0n];
  while (rest !== 0n) {
    const q = altR / rest;
    [altR, rest] = [rest, altR - q * rest];
    [altS, s] = [s, altS - q * s];
  }
  assert.equal(altR, 1n, "nicht invertierbar");
  return ((altS % m) + m) % m;
}

console.log();
if (fehler.length) {
  console.log(`${fehler.length} Abweichung(en) vom RFC-Vektor: ${fehler.join(", ")}`);
  process.exit(1);
}
console.log("static/blind.js stimmt mit RFC 9474 A.4 ueberein (RSABSSA-SHA384-PSSZERO-Deterministic).");
