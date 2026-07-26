// RSA-Blindsignatur, Client-Seite - RFC 9474 (RSABSSA-SHA384-PSS-Deterministic).
//
// Gegenstelle: app/blind.py. Beide Seiten muessen bitgenau dasselbe
// EMSA-PSS-ENCODE rechnen, sonst schlaegt die PSS-Pruefung beim Abstimmen fehl.
//
// Warum das hier im Browser laeuft und nicht auf dem Server: Der Stimm-Token
// entsteht lokal, wird lokal verblindet und lokal wieder entblindet. Der Server
// sieht nur die verblindete Form (Phase A) und spaeter Token + fertige Signatur
// (Phase B) - er kann beides nicht verketten. Verblindet der Server selbst, gibt
// es kein Wahlgeheimnis gegen den Betreiber, nur die Behauptung eines solchen
// (MC-RFC-20260725-001 §6, §10).
//
// Bekannte Grenze (§10, Helios-Problem): Dieser Code wird vom Betreiber
// ausgeliefert. Wer ihm nicht traut, muss die ausgelieferte Datei gegen den
// veroeffentlichten Stand pruefen.

const HASH = "SHA-384";
const H_LEN = 48;
const SALT_LEN = 0;

async function sha384(bytes) {
  const digest = await crypto.subtle.digest(HASH, bytes);
  return new Uint8Array(digest);
}

function concatBytes(...arrays) {
  const total = arrays.reduce((sum, a) => sum + a.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const a of arrays) {
    out.set(a, offset);
    offset += a.length;
  }
  return out;
}

function i2osp(value, length) {
  const out = new Uint8Array(length);
  let v = value;
  for (let i = length - 1; i >= 0; i -= 1) {
    out[i] = Number(v & 0xffn);
    v >>= 8n;
  }
  if (v !== 0n) throw new Error("Zahl passt nicht in die vorgegebene Laenge.");
  return out;
}

function os2ip(bytes) {
  let value = 0n;
  for (const byte of bytes) value = (value << 8n) | BigInt(byte);
  return value;
}

function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function hexToBytes(hex) {
  const clean = hex.length % 2 ? `0${hex}` : hex;
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i += 1) out[i] = parseInt(clean.substr(i * 2, 2), 16);
  return out;
}

// MGF1 mit SHA-384 (RFC 8017 B.2.1)
async function mgf1(seed, length) {
  const blocks = [];
  let produced = 0;
  for (let counter = 0; produced < length; counter += 1) {
    blocks.push(await sha384(concatBytes(seed, i2osp(BigInt(counter), 4))));
    produced += H_LEN;
  }
  return concatBytes(...blocks).slice(0, length);
}

// EMSA-PSS-ENCODE (RFC 8017 9.1.1), Salt-Laenge 0
async function emsaPssEncode(msg, emBits) {
  const emLen = Math.ceil(emBits / 8);
  if (emLen < H_LEN + SALT_LEN + 2) throw new Error("Modulus zu klein fuer EMSA-PSS.");

  const mHash = await sha384(msg);
  const mPrime = concatBytes(new Uint8Array(8), mHash);
  const h = await sha384(mPrime);

  const db = new Uint8Array(emLen - H_LEN - 1);
  db[db.length - 1] = 0x01; // PS aus Nullen, dann 0x01, dann leerer Salt

  const dbMask = await mgf1(h, emLen - H_LEN - 1);
  const maskedDb = new Uint8Array(db.length);
  for (let i = 0; i < db.length; i += 1) maskedDb[i] = db[i] ^ dbMask[i];

  const unusedBits = 8 * emLen - emBits;
  if (unusedBits > 0) maskedDb[0] &= 0xff >> unusedBits;

  return concatBytes(maskedDb, h, new Uint8Array([0xbc]));
}

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

function modInverse(a, m) {
  let [oldR, r] = [((a % m) + m) % m, m];
  let [oldS, s] = [1n, 0n];
  while (r !== 0n) {
    const q = oldR / r;
    [oldR, r] = [r, oldR - q * r];
    [oldS, s] = [s, oldS - q * s];
  }
  if (oldR !== 1n) return null; // nicht invertierbar
  return ((oldS % m) + m) % m;
}

function bitLength(value) {
  return value.toString(2).length;
}

/** Erzeugt lokal ein Stimm-Token (32 zufaellige Bytes). Verlaesst den Browser nie unverblindet. */
export function newToken() {
  return crypto.getRandomValues(new Uint8Array(32));
}

/** Verblindet das Token. Rueckgabe: { blindedHex, inv } - inv bleibt im Browser. */
export async function blindToken(token, nHex, eHex) {
  const n = BigInt(`0x${nHex}`);
  const e = BigInt(`0x${eHex}`);
  const k = Math.ceil(bitLength(n) / 8);

  const encoded = await emsaPssEncode(token, bitLength(n) - 1);
  const m = os2ip(encoded);
  if (m >= n) throw new Error("Kodierte Nachricht groesser als der Modulus.");

  for (let attempt = 0; attempt < 32; attempt += 1) {
    const rBytes = crypto.getRandomValues(new Uint8Array(k));
    const r = os2ip(rBytes) % n;
    if (r < 2n) continue;
    const rInv = modInverse(r, n);
    if (rInv === null) continue;
    const z = (m * modPow(r, e, n)) % n;
    return { blindedHex: bytesToHex(i2osp(z, k)), inv: rInv.toString(16) };
  }
  throw new Error("Kein brauchbarer Blinding-Faktor gefunden.");
}

/** Entblindet die Serversignatur. Ergebnis ist eine gewoehnliche RSASSA-PSS-Signatur. */
export function finalizeSignature(blindSigHex, invHex, nHex) {
  const n = BigInt(`0x${nHex}`);
  const k = Math.ceil(bitLength(n) / 8);
  const s = (os2ip(hexToBytes(blindSigHex)) * BigInt(`0x${invHex}`)) % n;
  return bytesToHex(i2osp(s, k));
}

export { bytesToHex, hexToBytes };
