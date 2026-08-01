// Stimme pruefen, ohne dem Server das Token zu zeigen (EIP-T-033, Baustein F).
//
// Bis hierher lief die Suche als GET /verify?token=... ueber den Server - und
// weil das Session-Cookie (path=/) an derselben Route mitfaehrt, lieferte, wer
// nach der Abstimmung angemeldet pruefte, dem Server Pseudonym und Token in
// einem Request. Genau die Zuordnung, die das Verfahren verhindern soll.
//
// Deshalb laeuft die Suche jetzt hier: Der Browser laedt das ganze Board
// (/api/board/{poll}, ohne Cookie) und sucht das Token lokal. Der Server
// erfaehrt nur, dass jemand das Board dieser Umfrage geladen hat - dieselbe
// Auskunft, die auch jeder unabhaengige Pruefer hinterlaesst.
//
// Das Token steht im URL-*Fragment* (#poll=...&token=...), nicht in den
// Query-Parametern: Das Fragment verlaesst den Browser nie, auch nicht als
// Referrer. Alte Beleg-Links mit ?token=... werden weiter verstanden - das
// Token ist dann zwar schon uebertragen (der Link stammt aus einem alten
// Beleg), aber die Seite schreibt die URL sofort auf die Fragment-Form um,
// damit sie nicht erneut wandert (Verlauf, Lesezeichen, erneutes Laden).

const form = document.getElementById("verify-form");
const pollSelect = document.getElementById("poll");
const tokenInput = document.getElementById("token");
const resultBox = document.getElementById("verify-result");

/** #poll=...&token=... oder (Altform) ?poll=...&token=... lesen. */
function readParams() {
  const fragment = new URLSearchParams(location.hash.replace(/^#/, ""));
  const query = new URLSearchParams(location.search);
  const poll = fragment.get("poll") || query.get("poll") || "";
  const token = fragment.get("token") || query.get("token") || "";
  // Altform sofort loswerden: Query raus, Fragment rein - ohne Neuladen.
  if (query.get("token")) {
    const ziel = `${location.pathname}#poll=${encodeURIComponent(poll)}&token=${encodeURIComponent(token)}`;
    history.replaceState(null, "", ziel);
  }
  return { poll, token };
}

function render(kind, html) {
  resultBox.className = `banner ${kind}`;
  resultBox.innerHTML = html;
  resultBox.classList.remove("hidden");
}

const escapeHtml = (s) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/** Sucht das Token in den veroeffentlichten Batches des Board-Exports. */
export function findVote(board, tokenHex) {
  for (const batch of board.batches || []) {
    for (const payload of batch.entries || []) {
      let entry;
      try {
        entry = JSON.parse(payload);
      } catch (_) {
        continue; // unlesbare Eintraege meldet die Nachweis-Seite, nicht diese Suche
      }
      if (entry.type === "VOTE" && entry.token === tokenHex) {
        return { choices: entry.choices || [], batch: batch.batch };
      }
    }
  }
  return null;
}

async function search(poll, token) {
  token = token.trim().toLowerCase();
  if (!poll || !token) return;
  // Fragment fortschreiben, damit die Suche einen teilbaren, serverfreien
  // Link hat - derselbe Link, den der Beleg-QR-Code traegt.
  history.replaceState(null, "",
    `${location.pathname}#poll=${encodeURIComponent(poll)}&token=${encodeURIComponent(token)}`);
  let board;
  try {
    // "omit": auch das Session-Cookie faehrt nicht mit - der Board-Abruf
    // gehoert zu Phase B und traegt keine Identitaet (EIP-T-033, F).
    const res = await fetch(`/api/board/${encodeURIComponent(poll)}`,
      { credentials: "omit", referrerPolicy: "no-referrer" });
    if (!res.ok) throw new Error(`Board nicht abrufbar (HTTP ${res.status}).`);
    board = await res.json();
  } catch (err) {
    render("err", `Das Board liess sich nicht laden. <small>${escapeHtml(String(err.message || err))}</small>`);
    return;
  }
  const found = findVote(board, token);
  if (found) {
    render("ok",
      `Token gefunden — so ist deine Stimme eingetragen: <strong>${found.choices.map(escapeHtml).join(", ")}</strong>`
      + `<small>Gefunden in Batch ${found.batch}. Genau das geht in die Auszählung ein, denn ausgezählt`
      + ` wird die öffentliche Liste — und gesucht hat dein Browser, nicht unser Server.</small>`);
  } else {
    render("err",
      `Zu diesem Token gibt es keinen veröffentlichten Eintrag in „${escapeHtml(poll)}“.`
      + `<small>Möglich ist: Die Stimme wartet noch auf ihre Veröffentlichung — Einträge erscheinen`
      + ` gebündelt, sobald genug Stimmen vorliegen, spätestens nach dem Zeitdeckel und in jedem Fall`
      + ` beim Ende der Umfrage; dein signierter Beleg bindet uns schon jetzt. Oder: damit wurde noch`
      + ` nicht abgestimmt, es gehört zu einer anderen Umfrage, oder beim Kopieren hat sich ein`
      + ` Zeichen verändert.</small>`);
  }
}

form.addEventListener("submit", (ev) => {
  ev.preventDefault();
  search(pollSelect.value, tokenInput.value);
});

const start = readParams();
if (start.poll) {
  for (const opt of pollSelect.options) {
    if (opt.value === start.poll) pollSelect.value = start.poll;
  }
}
if (start.token) {
  tokenInput.value = start.token;
  search(start.poll || pollSelect.value, start.token);
}
