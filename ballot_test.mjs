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
// Server ist gestellt, die Signatur ist eine Attrappe. Das zeigt erst
// browser_test.py gegen den echten Server.

import assert from "node:assert/strict";

// 2048-Bit-Modulus, einmal erzeugt und fest eingetragen. Das Blinding rechnet
// modular - fuer den Zustandsverlauf muss der Modulus die richtige Groesse
// haben, nicht zu einem echten Schluessel gehoeren.
const N_HEX =
  "be98c18a548855ee0a59394c998bcd3cfffee3c91ae219bdd4e8e96eff053bb2f59b5ee4e3d7a9abec3f502c0f7343cf"
  + "84ed7addd7b2db64c0d6385eaa4fd0512dedbe72640030fb00c0ac2a13fb2e7ae2de79bbb3ec1b5caf386d9b9abebf6"
  + "1ede86456e33d84b500870c9f34edc38756450f682a428e6979dbf5d5aef7aa5ed9dc16602d0d35eb61f3ab4be3f320"
  + "b0811225af0e689c4b24d5cfa703d830a08ff4f11c166758569f03659cef72332fdb1a9faf731a25b5d0d665903c671"
  + "2f9b5a325ded49d5db39db24d8c0d514a599390d08bbd1f61c443b68326bb0baf09e664078a20c71e09f64de442cb7f"
  + "040866ea034459891e2d1848970c019c4095";
const E_HEX = "10001";
const POLL = "nodetest";

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
    // Attrappe: irgendeine Zahl < n. Der Client entblindet sie unbesehen.
    return reply(200, { blind_sig: "42" });
  }
  if (url.startsWith("/api/vote/")) {
    voteCalls += 1;
    return voteHandler(body, reply);
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

const failed = results.filter(([ok]) => !ok);
for (const [ok, label] of results) console.log(`[${ok ? "  ok  " : " FEHL "}] ${label}`);
if (failed.length) {
  console.log(`\n${failed.length} fehlgeschlagen.`);
  process.exit(1);
}
console.log("\nStimmzettel-Flow bestanden.");
