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

// Seit EIP-T-099 nimmt die Seite zusaetzlich die gespeicherte Beleg-Datei
// entgegen. Auch das aendert an der Datenlage nichts: Gelesen wird die Datei
// im Browser (File.text()), sie wird nicht hochgeladen und nicht abgelegt -
// kein localStorage, kein Cookie, nichts auf dem Server. Nach einem Neuladen
// haelt der Browser wieder nichts, was Geraet und Stimme verbindet.
//
// Zum Debug-Modul: Fehlgeschlagene Dateien und unbrauchbare Token melden sich
// bewusst NICHT dorthin. Ein Ping ans Debug-Modul waere ein Request dieser
// Seite mit Sekundenstempel - also genau das Signal "hier prueft gerade
// jemand", das Baustein F entfernt hat; bei einem unbrauchbaren Token gaebe es
// sonst ueberhaupt keinen Request. Der Preis ist, dass der Betreiber nicht
// sieht, wie oft das Einlesen scheitert. Er ist bewusst bezahlt: Dies ist die
// Seite, auf der der Server am wenigsten erfahren soll.

import { belegLesen, tokenNormalisieren, tokenFormatOk } from "/static/beleg_datei.js";

const form = document.getElementById("verify-form");
const pollSelect = document.getElementById("poll");
const tokenInput = document.getElementById("token");
const resultBox = document.getElementById("verify-result");
const dropZone = document.getElementById("beleg-drop");
const fileInput = document.getElementById("beleg-file");
const pickButton = document.getElementById("beleg-pick");

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
  token = tokenNormalisieren(token);
  if (!poll || !token) return;
  // Format zuerst, Board danach (EIP-T-107). Ein Tippfehler kostete sonst
  // einen vollstaendigen Board-Download - auf dem Telefon Wartezeit fuer
  // nichts - und endete in der Meldung fuer "noch nicht veroeffentlicht",
  // also in der Auskunft, die sonst bedeutet: der Betreiber ist im Verzug.
  // Diese beiden Faelle duerfen nicht dieselbe Antwort bekommen.
  if (!tokenFormatOk(token)) {
    const grund = token.length !== 64
      ? `es sind ${token.length} statt 64 Zeichen`
      : "es stehen Zeichen darin, die in einem Token nicht vorkommen";
    render("err",
      `So kann ein Stimm-Token nicht aussehen — ${grund}.`
      + "<small>Erwartet werden 64 Zeichen aus Ziffern und den Buchstaben a bis f. Das Token steht"
      + " in deinem Beleg hinter „Stimm-Token:“. Leichter als abtippen: die gespeicherte"
      + " Beleg-Datei oben ablegen. Gesucht wurde noch nichts — dies ist keine Auskunft darüber,"
      + " ob deine Stimme im Board steht.</small>");
    return;
  }
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
      `Das Token ist gültig aufgebaut, aber in „${escapeHtml(poll)}“ steht dazu noch kein`
      + ` veröffentlichter Eintrag.`
      + `<small>Der wahrscheinlichste Grund: Die Stimme wartet auf ihre Veröffentlichung — Einträge`
      + ` erscheinen gebündelt, sobald genug Stimmen vorliegen, spätestens nach dem Zeitdeckel und in`
      + ` jedem Fall beim Ende der Umfrage; dein signierter Beleg bindet uns schon jetzt. Möglich ist`
      + ` auch: Der Beleg gehört zu einer anderen Umfrage — dann oben die richtige wählen. Oder beim`
      + ` Abtippen ist ein Zeichen vertauscht; das sieht von außen genauso aus, deshalb ist die`
      + ` Beleg-Datei der sicherere Weg.</small>`);
  }
}

form.addEventListener("submit", (ev) => {
  ev.preventDefault();
  search(pollSelect.value, tokenInput.value);
});

// --- Beleg-Datei einlesen (EIP-T-099)

/** Setzt die Umfrage, wenn es sie hier gibt. Gibt zurueck, ob das geklappt hat. */
function waehleUmfrage(pollId) {
  if (!pollId) return false;
  for (const opt of pollSelect.options) {
    if (opt.value === pollId) {
      pollSelect.value = pollId;
      return true;
    }
  }
  return false;
}

/** Liest eine abgelegte Datei, fuellt die Felder und sucht wie bei einem Beleg-Link. */
async function belegDateiUebernehmen(file) {
  if (!file) return;
  let text;
  try {
    text = await file.text();
  } catch (err) {
    render("err", `Die Datei liess sich nicht lesen. <small>${escapeHtml(String(err.message || err))}</small>`);
    return;
  }
  let beleg;
  try {
    beleg = belegLesen(text);
  } catch (err) {
    // Kein Board-Abruf: Was hier scheitert, scheitert an der Datei, und ein
    // Board-Download beantwortete die Frage nicht, sondern verzoegerte sie.
    render("err", `${escapeHtml(err.message)}<small>Du kannst das Token stattdessen unten von Hand`
      + ` einfügen — es steht im Beleg hinter „Stimm-Token:“.</small>`);
    return;
  }
  tokenInput.value = beleg.token;
  const passt = waehleUmfrage(beleg.poll);
  if (beleg.poll && !passt) {
    render("err",
      `Der Beleg gehört zur Umfrage „${escapeHtml(beleg.poll)}“ — die gibt es auf diesem Server nicht`
      + ` (mehr).<small>Das Token ist übernommen. Wähle unten die passende Umfrage, falls sie`
      + ` umbenannt wurde, und suche erneut.</small>`);
    return;
  }
  search(pollSelect.value, beleg.token);
}

if (dropZone) {
  pickButton.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    belegDateiUebernehmen(fileInput.files[0]);
    fileInput.value = ""; // dieselbe Datei soll ein zweites Mal ausloesen koennen
  });

  // Abgefangen wird auf der ganzen Seite, nicht nur auf der Flaeche: Wer
  // danebenzielt, wuerde den Beleg sonst im Browser geoeffnet bekommen - die
  // Seite waere weg, und mit ihr die Erklaerung, warum sie nichts uebertraegt.
  const zeigen = (an) => dropZone.classList.toggle("over", an);
  window.addEventListener("dragover", (ev) => { ev.preventDefault(); zeigen(true); });
  window.addEventListener("dragleave", (ev) => { if (!ev.relatedTarget) zeigen(false); });
  window.addEventListener("drop", (ev) => {
    ev.preventDefault();
    zeigen(false);
    belegDateiUebernehmen(ev.dataTransfer?.files?.[0]);
  });
}

const start = readParams();
waehleUmfrage(start.poll);
if (start.token) {
  tokenInput.value = start.token;
  search(start.poll || pollSelect.value, start.token);
}
