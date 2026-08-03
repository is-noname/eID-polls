// Verdrahtung der Betreiberseite. Bis EIP-T-007 inline in templates/admin.html
// - herausgezogen aus demselben Grund wie poll.js: Client-Code gehoert in eine
// Datei, die unveraendert ausgeliefert und deshalb von aussen gegen das
// Repository gehalten werden kann (Paragraf 20).
import { postJSON, toast } from "/static/app.js";

const login = document.getElementById("login-button");
if (login) {
  login.addEventListener("click", async () => {
    try {
      await postJSON("/api/admin/login", { token: document.getElementById("admin-token").value });
      location.reload();
    } catch (err) { toast(err.message, "err"); }
  });
}

const create = document.getElementById("create-button");
if (create) {
  create.addEventListener("click", async () => {
    const options = document.getElementById("options").value.split("\n").map((o) => o.trim()).filter(Boolean);
    try {
      await postJSON("/api/admin/create", {
        poll_id: document.getElementById("poll-id").value,
        question: document.getElementById("question").value,
        options,
        // Praeregistrierung nach KODEX § 7 (EIP-T-091). Der Wert eines
        // datetime-local-Feldes ist bereits ISO 8601 ohne Zone; leer heisst
        // "Vorgabe der Instanz" und wird serverseitig aufgeloest, nicht hier.
        laufzeit_ende: document.getElementById("laufzeit-ende").value,
        auswertungsplan_zusatz: document.getElementById("auswertungsplan-zusatz").value,
      });
      location.reload();
    } catch (err) { toast(err.message, "err"); }
  });

  document.querySelectorAll(".close-button").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Umfrage schließen? Danach keine Stimmen mehr.")) return;
      try {
        await postJSON(`/api/admin/close/${button.dataset.poll}`);
        location.reload();
      } catch (err) { toast(err.message, "err"); }
    });
  });

  const reset = document.getElementById("reset-button");
  if (reset) reset.addEventListener("click", async () => {
    try {
      const res = await postJSON(`/api/admin/reset/${document.getElementById("reset-poll").value}`, {
        credential: document.getElementById("reset-code").value,
      });
      toast(res.removed ? "Testzugang zurückgesetzt." : "Für diesen Code gab es keine Sperre.", res.removed ? "ok" : "err");
    } catch (err) { toast(err.message, "err"); }
  });

  const stuff = document.getElementById("stuff-button");
  if (stuff) stuff.addEventListener("click", async () => {
    try {
      await postJSON(`/api/admin/demo/stuff/${document.getElementById("demo-poll").value}`, {
        choice: document.getElementById("demo-choice").value,
      });
      toast("Stimme ohne Berechtigung eingeschleust — Board prüfen.", "err");
    } catch (err) { toast(err.message, "err"); }
  });

  const tamper = document.getElementById("tamper-button");
  if (tamper) tamper.addEventListener("click", async () => {
    try {
      await postJSON(`/api/admin/demo/tamper/${document.getElementById("demo-poll").value}`, {
        leaf: document.getElementById("demo-leaf").value,
        choice: document.getElementById("demo-choice").value,
      });
      toast("Board-Eintrag umgeschrieben — Kette prüfen.", "err");
    } catch (err) { toast(err.message, "err"); }
  });
}
