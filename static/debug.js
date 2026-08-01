// Verdrahtung des Debug-Moduls. Bis EIP-T-007 inline in templates/debug.html
// (Paragraf 20 - siehe poll.js).
import { postJSON } from "/static/app.js";

document.getElementById("clear-button").addEventListener("click", async () => {
  await postJSON("/api/debug/clear");
  location.reload();
});

const box = document.getElementById("autorefresh");
box.checked = sessionStorage.getItem("debug-autorefresh") !== "off";
box.addEventListener("change", () => {
  sessionStorage.setItem("debug-autorefresh", box.checked ? "on" : "off");
});
setInterval(() => { if (box.checked) location.reload(); }, 3000);
