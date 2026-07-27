// Stimmzettel-Flow, Client-Seite - die Haelfte des Verfahrens, die das
// Wahlgeheimnis gegen den Betreiber traegt (MC-RFC-20260725-001 §6).
//
// Hier steht der ganze Weg einer Stimme: Token erzeugen, verblinden, signieren
// lassen, entblinden, abgeben - und der Zwischenstand, wenn die Abgabe dazwischen
// abbricht (EIP-ADR-20260725-002). Die Rechenschritte selbst liegen in blind.js,
// die DOM-Verdrahtung in templates/poll.html.
//
// Warum als eigene Datei und nicht im Template: Ein Pruefer soll den Krypto-Pfad
// lesen und pruefen koennen, ohne den ganzen Browser-Durchlauf zu fahren, und ein
// Build-Hash (EIP-T-007) muss die ganze Strecke abdecken - blind.js allein waere
// nur die Haelfte.
//
// Nichts davon darf auf den Server wandern: Der Server sieht das Token nur
// verblindet (Phase A) und spaeter Token samt fertiger Signatur (Phase B). Wer
// serverseitig "verblindet", hat kein Wahlgeheimnis, nur dessen Behauptung.

import { newToken, blindToken, finalizeSignature, bytesToHex } from "./blind.js";
import { postJSON } from "./app.js";

const storeKey = (pollId) => `eidpoll:${pollId}`;

// Token und Signatur der laufenden Sitzung. Nach der Abgabe stehen sie
// absichtlich nicht mehr im localStorage (EIP-T-011), werden hier aber weiter
// gehalten: fuer den Beleg und damit ein zweiter Abstimmversuch regulaer als
// "Token verbraucht" abgewiesen wird, statt eine neue Berechtigung anzufordern.
let held = null;

function storage() {
  try {
    return globalThis.localStorage || null;
  } catch (_) {
    return null; // gesperrter Speicher darf das Abstimmen nicht verhindern
  }
}

/** Liest den gespeicherten Zustand dieser Umfrage (Zwischenstand oder Beleg). */
export function loadState(pollId) {
  const store = storage();
  if (!store) return null;
  try {
    return JSON.parse(store.getItem(storeKey(pollId)) || "null");
  } catch (_) {
    return null;
  }
}

/** Schreibt den Zustand dieser Umfrage. */
export function saveState(pollId, state) {
  const store = storage();
  if (store) store.setItem(storeKey(pollId), JSON.stringify(state));
}

/** Token und Signatur der laufenden Sitzung, oder null. */
export function heldBallot() {
  return held;
}

/** Vergisst die Sitzung. Nur fuer Tests - im Browser erledigt das der Reload. */
export function resetSession() {
  held = null;
}

/** Unverbrauchte Stimmberechtigung aus einem abgebrochenen Versuch, oder null.
 *
 * Quelle ist entweder die laufende Sitzung oder der localStorage - nach einem
 * Reload existiert nur letzterer.
 */
export function pendingBallot(pollId) {
  if (held) return held;
  const state = loadState(pollId);
  if (state && state.token && state.sig && !state.voted) {
    held = { token: state.token, sig: state.sig };
    return held;
  }
  return null;
}

/** Holt die Stimmberechtigung: Token erzeugen, verblinden, signieren lassen, entblinden.
 *
 * Vor der Rueckgabe landen Token und Signatur im localStorage. Das ist der
 * einzige Grund, warum hier ueberhaupt noch etwas gespeichert wird: Bricht der
 * anschliessende Vote-Aufruf ab (Netz weg, Tab zu), ist die Berechtigung im
 * Eligibility-Ledger verbraucht, waehrend die Stimme nicht steht. Ohne diesen
 * Zwischenstand waere die Person raus - der Server gibt kein zweites Token aus
 * und kann das auch nicht (EIP-ADR-20260725-002).
 */
export async function obtainBallot(pollId, nHex, eHex) {
  const token = newToken();
  const { blindedHex, inv } = await blindToken(token, nHex, eHex);
  const { blind_sig } = await postJSON(`/api/token/${pollId}`, { blinded: blindedHex });
  const record = { token: bytesToHex(token), sig: finalizeSignature(blind_sig, inv, nHex) };
  saveState(pollId, record);
  held = record;
  return record;
}

/** Gibt die Stimme ab. Berechtigung wird geholt, falls noch keine offene existiert.
 *
 * Rueckgabe: { index, entryHash, token, participation } - der Inhalt des Belegs.
 * Wirft die Fehlermeldung des Servers weiter (verbrauchtes Token, geschlossene
 * Umfrage, fehlende Berechtigung).
 */
export async function castBallot(pollId, nHex, eHex, choices) {
  const record = pendingBallot(pollId) || await obtainBallot(pollId, nHex, eHex);

  const result = await postJSON(`/api/vote/${pollId}`, {
    token: record.token, sig: record.sig, choices,
  });

  // Das Token verlaesst den Speicher, sobald es verbraucht ist - danach traegt
  // nur noch der Beleg den Bezug zur Stimme (EIP-T-011).
  const receipt = { voted: true, index: result.board_index, entryHash: result.entry_hash };
  saveState(pollId, receipt);

  return { ...receipt, token: record.token, participation: result.participation };
}
