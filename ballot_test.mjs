// Stimmzettel-Flow ohne Browser: static/ballot.js gegen einen gestellten Server.
//
//     node ballot_test.mjs
//
// Geprueft wird der Zustandsverlauf um EIP-ADR-20260725-002: Die Berechtigung
// entsteht erst beim Abstimmen, und bricht die Abgabe danach ab, ist sie im
// Eligibility-Ledger verbraucht, waehrend die Stimme nicht steht. Genau dann
// muss der naechste Versuch dieselbe Berechtigung wiederverwenden - der Server
// gibt keine zweite aus und kann das auch nicht.
//
// Was hier NICHT geprueft wird: ob blind.js bitgleich zu blind.py rechnet. Der
// Server ist gestellt. Das zeigt erst browser_test.py gegen den echten Server.

import assert from "node:assert/strict";

// Ein echtes Schluesselpaar, je Lauf frisch. Bis EIP-T-080 stand hier ein
// blosser Modulus und der gestellte Server antwortete mit "42" - eine
// Attrappe, die genuegte, solange der Client die Signatur ungeprueft
// weiterreichte. Seit Finalize sie prueft, muss der gestellte Server auch
// wirklich signieren, sonst prueft dieser Test nur noch den Fehlerfall.
const paar = await crypto.subtle.generateKey(
  { name: "RSA-PSS", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-384" },
  true,
  ["sign", "verify"],
);
const jwk = await crypto.subtle.exportKey("jwk", paar.privateKey);
const alsZahl = (b64u) => BigInt(`0x${Buffer.from(b64u, "base64url").toString("hex")}`);
const N = alsZahl(jwk.n);
const D = alsZahl(jwk.d);
const N_HEX = N.toString(16);
const E_HEX = "10001";
const POLL = "nodetest";

function modPow(base, exponent, modulus) {
  let result = 1n;
  let b = base % modulus;
  let e = exponent;
  while (e > 0n) {
    if (e & 1n) result = (result * b) % modulus;
    b = (b * b) % modulus;
    e >>= 1n;
  }
  return result;
}

/** Die Serverseite von Phase A: rohe RSA-Operation auf der verblindeten Form. */
function blindSign(blindedHex) {
  return modPow(BigInt(`0x${blindedHex}`), D, N).toString(16);
}

// --- gestellte Browser-Umgebung
const store = new Map();
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
  clear: () => store.clear(),
};

// --- gestellter Server
let tokenCalls = 0;
let voteCalls = 0;
let voteHandler = null; // (body) -> Antwort, oder wirft fuer "Netz weg"
let tokenHandler = null; // dasselbe fuer Phase A; null = Standardantwort
const tokenBodies = []; // was der Client jeweils verblindet geschickt hat
let meldungen = 0; // Meldungen an /api/melde/signatur (EIP-T-080)

globalThis.fetch = async (url, options) => {
  const body = JSON.parse(options.body || "{}");
  const reply = (status, data) => ({
    ok: status < 400,
    status,
    json: async () => data,
  });

  if (url.startsWith("/api/token/")) {
    tokenCalls += 1;
    tokenBodies.push(body);
    if (tokenHandler) return tokenHandler(body, reply);
    return reply(200, { blind_sig: blindSign(body.blinded) });
  }
  if (url.startsWith("/api/vote/")) {
    voteCalls += 1;
    return voteHandler(body, reply);
  }
  if (url.startsWith("/api/melde/signatur/")) {
    meldungen += 1;
    return reply(200, { ok: true });
  }
  throw new Error(`unerwarteter Aufruf: ${url}`);
};

const ballot = await import("./static/ballot.js");
const state = () => JSON.parse(store.get(`eidpoll:${POLL}`) || "null");

const results = [];
function check(label, fn) {
  try {
    fn();
    results.push([true, label]);
  } catch (err) {
    results.push([false, `${label} - ${err.message}`]);
  }
}

// --- Fall 1: Abgabe bricht nach der Signatur ab (Netz weg)
voteHandler = () => { throw new TypeError("fetch failed"); };
let firstError = null;
try {
  await ballot.castBallot(POLL, N_HEX, E_HEX, ["Ja"]);
} catch (err) {
  firstError = err;
}
const midway = state();

check("Abbruch wird nach oben gemeldet", () => assert.ok(firstError));
check("ADR-002: Berechtigung gesichert, Stimme steht nicht", () => {
  assert.ok(midway, "kein Zustand gespeichert");
  assert.match(midway.token, /^[0-9a-f]{64}$/);
  assert.ok(midway.sig, "keine Signatur gesichert");
  assert.ok(!midway.voted, "faelschlich als abgestimmt vermerkt");
});
check("genau eine Berechtigung angefordert", () => assert.equal(tokenCalls, 1));

// --- Fall 2: naechster Versuch verwendet dieselbe Berechtigung
voteHandler = (_body, reply) =>
  reply(200, { leaf_hash: "abc123", batch: 7, beleg_sig: "ff00", participation: 3 });
const receipt = await ballot.castBallot(POLL, N_HEX, E_HEX, ["Ja"]);

check("keine zweite Berechtigung angefordert", () => assert.equal(tokenCalls, 1));
check("dasselbe Token wie vor dem Abbruch", () => assert.equal(receipt.token, midway.token));
check("Beleg enthaelt Blatt, Batch-Zusage und Signatur", () => {
  assert.equal(receipt.leaf, "abc123");
  assert.equal(receipt.batch, 7);
  assert.equal(receipt.belegSig, "ff00");
  assert.equal(receipt.participation, 3);
});
check("EIP-T-011: Token nach Abgabe aus dem Speicher entfernt", () => {
  const after = state();
  assert.ok(after.voted);
  assert.equal(after.leaf, "abc123");
  assert.ok(!after.token, "Token noch gespeichert");
  assert.ok(!after.sig, "Signatur noch gespeichert");
});

// --- Fall 3: zweiter Abstimmversuch, Token verbraucht
voteHandler = (_body, reply) => reply(400, { error: "Stimm-Token bereits verbraucht." });
let secondError = null;
try {
  await ballot.castBallot(POLL, N_HEX, E_HEX, ["Nein"]);
} catch (err) {
  secondError = err;
}
check("zweiter Versuch wird abgewiesen, nicht neu berechtigt", () => {
  assert.ok(secondError);
  assert.match(secondError.message, /verbraucht/);
  assert.equal(tokenCalls, 1, "hat eine neue Berechtigung angefordert");
});

// --- Fall 4: Reload nach Abbruch - der Zwischenstand kommt aus dem Speicher
store.clear();
ballot.resetSession();
const parked = { token: "ab".repeat(32), sig: "cd" };
store.set(`eidpoll:${POLL}`, JSON.stringify(parked));

check("Reload findet die geparkte Berechtigung", () => {
  const found = ballot.pendingBallot(POLL);
  assert.deepEqual(found, parked);
});

voteCalls = 0;
voteHandler = (body, reply) => {
  assert.equal(body.token, parked.token);
  return reply(200, { leaf_hash: "deadbeef", batch: 1, beleg_sig: "ff00", participation: 1 });
};
const afterReload = await ballot.castBallot(POLL, N_HEX, E_HEX, ["Ja"]);
check("Abgabe nach Reload nutzt die geparkte Berechtigung", () => {
  assert.equal(tokenCalls, 1, "hat eine neue Berechtigung angefordert");
  assert.equal(voteCalls, 1);
  assert.equal(afterReload.token, parked.token);
});

// --- Fall 5: gesperrter Speicher darf das Abstimmen nicht verhindern
ballot.resetSession();
const blocked = globalThis.localStorage;
globalThis.localStorage = {
  getItem() { throw new Error("Speicher gesperrt"); },
  setItem() { throw new Error("Speicher gesperrt"); },
};
check("gesperrter Speicher liefert keinen Zustand statt zu scheitern", () => {
  assert.equal(ballot.loadState(POLL), null);
  assert.equal(ballot.pendingBallot(POLL), null);
});
globalThis.localStorage = blocked;

// --- Fall 6: Antwort auf die Token-Anfrage geht verloren (EIP-T-070)
//
// Der Gegenpart zum Server-seitigen Wiederhol-Puffer: Damit der ueberhaupt
// greifen kann, muss der Client dieselbe verblindete Anfrage ein zweites Mal
// stellen koennen. Wuerfelte er neu, waere das fuer den Server eine andere
// Anfrage - zu Recht abgewiesen, und die Berechtigung waere verloren.
store.clear();
ballot.resetSession();
tokenCalls = 0;
tokenBodies.length = 0;
tokenHandler = () => { throw new TypeError("fetch failed"); };
let tokenError = null;
try {
  await ballot.castBallot(POLL, N_HEX, E_HEX, ["Ja"]);
} catch (err) {
  tokenError = err;
}
const angefragt = state();

check("Abbruch in Phase A wird nach oben gemeldet", () => assert.ok(tokenError));
check("EIP-T-070: die abgeschickte Anfrage ist gesichert", () => {
  assert.ok(angefragt, "kein Zustand gespeichert");
  assert.match(angefragt.token, /^[0-9a-f]{64}$/);
  assert.ok(angefragt.blinded, "verblindete Form nicht gesichert");
  assert.ok(angefragt.inv, "Blinding-Faktor nicht gesichert");
  assert.ok(!angefragt.sig, "Signatur vorgetaeuscht");
});
check("EIP-T-070: eine unbeantwortete Anfrage ist keine Berechtigung", () => {
  ballot.resetSession();
  assert.equal(ballot.pendingBallot(POLL), null);
});

// Zweiter Anlauf nach Reload: derselbe Blinded-Wert, kein neues Token.
ballot.resetSession();
tokenHandler = null;
voteHandler = (_body, reply) =>
  reply(200, { leaf_hash: "beef", batch: 2, beleg_sig: "ab", participation: 1 });
const nachAbbruch = await ballot.castBallot(POLL, N_HEX, E_HEX, ["Ja"]);
check("EIP-T-070: der zweite Anlauf schickt dieselbe verblindete Anfrage", () => {
  assert.equal(tokenCalls, 2);
  assert.equal(tokenBodies[1].blinded, tokenBodies[0].blinded);
});
check("EIP-T-070: dasselbe Token wie vor dem Abbruch", () => {
  assert.equal(nachAbbruch.token, angefragt.token);
});

// --- Fall 7: der Server liefert eine unbrauchbare Signatur (EIP-T-080)
//
// Frueher fiel das erst bei der Stimmabgabe auf und sah dort aus wie ein
// abgelehnter Stimmzettel. Jetzt endet der Weg in Phase A - mit einem eigenen
// Fehlerbild, einer Meldung an den Betreiber und einer Berechtigung, die
// wiederholbar bleibt.
store.clear();
ballot.resetSession();
tokenCalls = 0;
voteCalls = 0;
meldungen = 0;
tokenBodies.length = 0;
tokenHandler = (body, reply) => {
  // Gueltig gerechnet, aber mit einem verdrehten Bit unterwegs verstuemmelt.
  const echt = BigInt(`0x${blindSign(body.blinded)}`);
  return reply(200, { blind_sig: (echt ^ 1n).toString(16) });
};
let sigError = null;
try {
  await ballot.castBallot(POLL, N_HEX, E_HEX, ["Ja"]);
} catch (err) {
  sigError = err;
}
const nachSigFehler = state();

check("ungueltige Serversignatur wird als solche erkannt", () => {
  assert.ok(sigError, "kein Fehler gemeldet");
  assert.equal(sigError.name, "ServersignaturUngueltig");
  assert.equal(sigError.serverfehler, true, "nicht als Serverfehler gekennzeichnet");
});
check("die Stimme wird gar nicht erst abgeschickt", () => assert.equal(voteCalls, 0));
check("der Betreiber erfaehrt davon (/api/melde/signatur)", () => assert.equal(meldungen, 1));
check("die Berechtigung bleibt wiederholbar (EIP-T-070)", () => {
  assert.ok(nachSigFehler, "kein Zustand gespeichert");
  assert.ok(nachSigFehler.blinded, "verblindete Form nicht gesichert");
  assert.ok(!nachSigFehler.sig, "unbrauchbare Signatur gespeichert");
  assert.ok(!nachSigFehler.voted);
});

// Derselbe Anlauf gegen einen wieder rechnenden Server geht durch.
ballot.resetSession();
tokenHandler = null;
voteHandler = (_body, reply) =>
  reply(200, { leaf_hash: "cafe", batch: 3, beleg_sig: "01", participation: 5 });
const nachReparatur = await ballot.castBallot(POLL, N_HEX, E_HEX, ["Ja"]);
check("nach dem Serverfehler geht derselbe Versuch durch", () => {
  assert.equal(nachReparatur.token, nachSigFehler.token);
  assert.equal(tokenBodies[1].blinded, tokenBodies[0].blinded);
  assert.equal(nachReparatur.leaf, "cafe");
});

const failed = results.filter(([ok]) => !ok);
for (const [ok, label] of results) console.log(`[${ok ? "  ok  " : " FEHL "}] ${label}`);
if (failed.length) {
  console.log(`\n${failed.length} fehlgeschlagen.`);
  process.exit(1);
}
console.log("\nStimmzettel-Flow bestanden.");
