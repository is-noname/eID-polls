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
 *
 * Eine bloss *abgeschickte* Anfrage (siehe openRequest) zaehlt hier nicht: Ohne
 * Signatur ist sie keine Berechtigung, mit der man abstimmen koennte.
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

/** Eine abgeschickte, aber unbeantwortete Token-Anfrage, oder null (EIP-T-070). */
function openRequest(pollId) {
  const state = loadState(pollId);
  if (state && state.token && state.blinded && state.inv && !state.sig && !state.voted) {
    return state;
  }
  return null;
}

/** Holt die Stimmberechtigung: Token erzeugen, verblinden, signieren lassen, entblinden.
 *
 * Gespeichert wird **zweimal**, und beide Male aus demselben Grund - der Weg
 * darf an keiner Stelle so abbrechen, dass die Berechtigung verbraucht ist und
 * niemand mehr etwas davon hat:
 *
 * 1. *Vor* dem Absenden Token, verblindete Form und Blinding-Faktor. Bricht die
 *    Antwort weg (Netz, Tab zu), hat der Server im Zweifel schon signiert und
 *    das Pseudonym als versorgt vermerkt. Nur wer dieselbe verblindete Anfrage
 *    noch einmal stellen kann, bekommt dann dieselbe Signatur wiederholt
 *    (EIP-T-070) - ein neu gewuerfeltes Token waere eine andere Anfrage und
 *    wuerde zu Recht abgewiesen.
 * 2. Nach dem Entblinden Token und fertige Signatur. Bricht der anschliessende
 *    Vote-Aufruf ab, ist die Berechtigung im Eligibility-Ledger verbraucht,
 *    waehrend die Stimme nicht steht (EIP-ADR-20260725-002).
 *
 * Der Blinding-Faktor liegt damit kurzzeitig im localStorage. Er ist kein
 * Geheimnis gegenueber dem Server - im Gegenteil, er ist genau das, was der
 * Server *nicht* hat und auch aus dem Speicher nicht bekommt; er verlaesst das
 * Geraet nicht. Mit dem Zustand nach Schritt 2 (Token im Klartext) steht er
 * ohnehin auf einer Stufe, und mit der Abgabe verschwindet beides (EIP-T-011).
 */
export async function obtainBallot(pollId, nHex, eHex) {
  let request = openRequest(pollId);
  if (!request) {
    const token = newToken();
    const { blindedHex, inv } = await blindToken(token, nHex, eHex);
    request = { token: bytesToHex(token), blinded: blindedHex, inv };
    saveState(pollId, request);
  }
  const { blind_sig } = await postJSON(`/api/token/${pollId}`, { blinded: request.blinded });
  const record = { token: request.token, sig: finalizeSignature(blind_sig, request.inv, nHex) };
  saveState(pollId, record);
  held = record;
  return record;
}

/** Gibt die Stimme ab. Berechtigung wird geholt, falls noch keine offene existiert.
 *
 * Rueckgabe: { leaf, batch, belegSig, token, participation } - der Inhalt des
 * Belegs (EIP-ADR-20260728-001, E4): Blatt-Hash des Eintrags, zugesagte
 * Batch-Nummer und die Ed25519-Signatur des Betreibers ueber diese Zusage.
 * Wirft die Fehlermeldung des Servers weiter (verbrauchtes Token, geschlossene
 * Umfrage, fehlende Berechtigung).
 */
export async function castBallot(pollId, nHex, eHex, choices) {
  const record = pendingBallot(pollId) || await obtainBallot(pollId, nHex, eHex);

  // Phase B ohne Sitzungskontext (EIP-T-033, Baustein F): Das Token ist die
  // ganze Berechtigung. "omit" haelt das eID-Session-Cookie aus dem Request,
  // "no-referrer" die Seite, von der er kommt - sonst empfinge der Server
  // Identitaet und Stimme im selben Request und die Trennung der Phasen
  // waere nur noch Behauptung. Kommt doch Kontext an, meldet der Server das
  // im Debug-Modul als Befund.
  const result = await postJSON(
    `/api/vote/${pollId}`,
    { token: record.token, sig: record.sig, choices },
    { credentials: "omit", referrerPolicy: "no-referrer" },
  );

  // Das Token verlaesst den Speicher, sobald es verbraucht ist - danach traegt
  // nur noch der Beleg den Bezug zur Stimme (EIP-T-011).
  const receipt = {
    voted: true,
    leaf: result.leaf_hash,
    batch: result.batch,
    belegSig: result.beleg_sig,
  };
  saveState(pollId, receipt);

  return { ...receipt, token: record.token, participation: result.participation };
}
