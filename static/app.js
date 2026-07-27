// Gemeinsame Helfer fuer alle Seiten. Die Krypto steht in blind.js.

export async function postJSON(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await response.json().catch(() => ({ error: "Antwort nicht lesbar." }));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

export function toast(message, kind = "ok", ms = 4500) {
  document.querySelectorAll(".toast").forEach((t) => t.remove());
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

export function download(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Die Verdrahtung haengt am Browser; ausserhalb (ballot_test.mjs unter Node)
// wird nur postJSON gebraucht.
if (typeof window !== "undefined") window.addEventListener("DOMContentLoaded", () => {
  // Hell ist die Voreinstellung; die Umschaltung merkt sich der Browser.
  // Gesetzt wird sie schon im <head>, damit beim Laden nichts aufblitzt.
  const theme = document.getElementById("theme-button");
  if (theme) {
    theme.addEventListener("click", () => {
      const dark = document.documentElement.getAttribute("data-theme") === "dark";
      if (dark) {
        document.documentElement.removeAttribute("data-theme");
      } else {
        document.documentElement.setAttribute("data-theme", "dark");
      }
      try {
        localStorage.setItem("eidpoll:theme", dark ? "light" : "dark");
      } catch (_) {
        /* gesperrter Speicher darf die Umschaltung nicht verhindern */
      }
    });
  }

  const quit = document.getElementById("quit-button");
  if (quit) {
    quit.addEventListener("click", async () => {
      if (!confirm("Server beenden?")) return;
      try {
        await postJSON("/api/shutdown");
      } catch (_) {
        /* Verbindung bricht beim Beenden ab - das ist der Normalfall */
      }
      document.body.innerHTML =
        '<div class="content"><div class="banner ok">Server beendet. Fenster kann geschlossen werden.</div></div>';
    });
  }
});
