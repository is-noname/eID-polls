// Der Beleg: Kassenbon, QR-Code und Textdatei zum Speichern.
//
// Reine Darstellung - kein Krypto, kein Netz, kein Speicher. Die Stimmabgabe
// selbst steht in ballot.js, das Zeichnen im DOM in templates/poll.html.
//
// Zustand ist immer der Beleg-Datensatz aus ballot.js:
//   { index, entryHash, token? }
// Ohne token stammt der Zustand aus einem Reload nach der Abgabe - dann traegt
// nur noch der gespeicherte Beleg den Bezug zur Stimme (EIP-T-011), und Textform
// wie Kassenbon sagen das ausdruecklich.

import { qrSvg } from "./qr.js";

/** Direktlink auf die Pruefseite, Token schon eingesetzt. */
export function verifyUrl(pollId, token, origin = location.origin) {
  return `${origin}/verify?poll=${encodeURIComponent(pollId)}&token=${encodeURIComponent(token)}`;
}

/** Beleg als Text - Inhalt identisch zum Kassenbon. */
export function receiptText(pollId, state, origin = location.origin) {
  const tokenLine = state.token
    ? `Stimm-Token:  ${state.token}`
    : "Stimm-Token:  nicht mehr in diesem Browser — nur noch in deinem gespeicherten Beleg.";
  return [
    "DEIN BELEG — eID-Umfrage",
    `Umfrage:      ${pollId}`,
    `Eintrag Nr.:  ${state.index}`,
    `Prüfsumme:    ${state.entryHash}`,
    tokenLine,
    "",
    "So prüfst du deine Stimme:",
    `  1. ${origin}/verify aufrufen`,
    "  2. Umfrage wählen und das Stimm-Token oben einfügen",
    "  3. Die angezeigte Auswahl muss deiner Stimme entsprechen",
    "",
    "Bewahre den Beleg wie eine Quittung auf: Wer das Stimm-Token hat, kann deine",
    "Stimme nachschlagen. Es ist zugleich der einzige Weg, sie selbst zu prüfen.",
  ].join("\n");
}

/** Baut den Beleg als Kassenbon (Design 1). Inhalt identisch zu receiptText(). */
export function receiptPaper(pollId, state, origin = location.origin) {
  const paper = document.createElement("div");
  paper.className = "receipt-paper";

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const row = (k, v) => {
    const r = el("div", "rc-row");
    r.append(el("span", "k", k), el("span", "v", v));
    return r;
  };

  paper.append(el("div", "rc-title", "DEIN BELEG"), el("div", "rc-sub", "eID-Umfrage"));
  paper.append(row("Umfrage", pollId));
  paper.append(row("Eintrag Nr.", String(state.index)));
  paper.append(el("div", "rc-divider"));
  paper.append(el("div", "rc-label", "Prüfsumme"), el("div", "rc-hex", state.entryHash));
  paper.append(el("div", "rc-divider"));

  paper.append(el("div", "rc-label", "Stimm-Token"));
  if (state.token) {
    const tokenValue = el("div", "rc-hex", state.token);
    tokenValue.id = "receipt-token"; // stabiler Hook fuer browser_test.py
    paper.append(tokenValue);
  } else {
    paper.append(el("div", "rc-text",
      "nicht mehr in diesem Browser — nur noch in deinem gespeicherten Beleg."));
  }

  paper.append(el("div", "rc-divider"));
  paper.append(el("div", "rc-label", "So prüfst du deine Stimme:"));
  const steps = el("ol", "rc-steps");
  for (const text of [
    `${origin}/verify aufrufen`,
    "Umfrage wählen und das Stimm-Token oben einfügen",
    "Die angezeigte Auswahl muss deiner Stimme entsprechen",
  ]) steps.append(el("li", null, text));
  paper.append(steps);

  // Der Code traegt Umfrage und Token, ersetzt also Schritt 1 und 2. Ohne
  // Token gibt es nichts zu verlinken - dann entfaellt er.
  if (state.token) {
    const qr = el("div", "rc-qr");
    qr.innerHTML = qrSvg(verifyUrl(pollId, state.token, origin));
    paper.append(qr, el("div", "rc-qr-caption", "oder diesen Code scannen"));
  }

  paper.append(el("div", "rc-note",
    "Bewahre den Beleg wie eine Quittung auf: Wer das Stimm-Token hat, kann deine "
    + "Stimme nachschlagen. Es ist zugleich der einzige Weg, sie selbst zu prüfen."));

  return paper;
}
