// Verdrahtung der Umfrageseite: Der Stimmzettel-Flow steht in ballot.js, die
// Belegdarstellung in beleg.js, die Krypto in blind.js.
//
// Bis EIP-T-007 stand dieser Code inline in templates/poll.html. Dort war er
// nicht pruefbar: Was der Browser ausfuehrt, muss aus dem veroeffentlichten
// Stand nachvollziehbar sein (Paragraf 20), und das geht nur bei einer Datei,
// die unveraendert ausgeliefert wird. Die drei umfragespezifischen Werte
// kommen deshalb als *Daten* aus der Seite, nicht als eingesetzter Quelltext.
import { toast, download } from "/static/app.js";
import { castBallot, loadState, pendingBallot, heldBallot } from "/static/ballot.js";
import { receiptPaper, receiptText, verifyUrl } from "/static/beleg.js";

const params = JSON.parse(document.getElementById("poll-params").textContent);
const POLL_ID = params.poll_id;
const N_HEX = params.n;
const E_HEX = params.e;

const stepAuth = document.getElementById("step-auth");
const stepVote = document.getElementById("step-vote");
const stepReceipt = document.getElementById("step-receipt");
const voteButton = document.getElementById("vote-button");
const choiceRows = document.querySelector("#step-vote .rows");

/** EIP-T-100: Schritt 2 ist bis zur Anmeldung gesperrt - die Checkboxen tragen
 * dafuer schon `disabled`, aber ein Klick soll nicht ins Leere laufen, sondern
 * zu Schritt 1 zeigen. */
function redirectToAuth() {
  stepAuth.scrollIntoView({ behavior: "smooth", block: "center" });
  stepAuth.classList.add("flash");
  setTimeout(() => stepAuth.classList.remove("flash"), 1200);
  toast("Erst ausweisen, dann geht's hier weiter.", "err");
}

// mousedown statt click: ein `disabled` Checkbox unterdrueckt sein eigenes
// click-Ereignis vollstaendig, mousedown feuert aber trotzdem und laesst sich
// per preventDefault auch vorm Ankreuzen abfangen.
choiceRows.addEventListener("mousedown", (e) => {
  if (!stepVote.classList.contains("blocked")) return;
  e.preventDefault();
  redirectToAuth();
});

function render() {
  const state = loadState(POLL_ID);
  if (!state) return;
  pendingBallot(POLL_ID); // Berechtigung aus einem abgebrochenen Versuch uebernehmen
  if (state.voted) {
    stepVote.classList.add("done");
    voteButton.disabled = false; // zweiter Versuch muss moeglich sein und abgewiesen werden
    showReceipt(state);
  }
}

/** Ergaenzt den gespeicherten Beleg um das Token der laufenden Sitzung, falls vorhanden. */
function withToken(state) {
  if (state.token) return state;
  const held = heldBallot();
  return held ? { ...state, token: held.token } : state;
}

function showReceipt(state) {
  const full = withToken(state);
  stepReceipt.classList.remove("hidden");
  document.getElementById("receipt-body").replaceChildren(receiptPaper(POLL_ID, full));
  const verifyLink = document.getElementById("receipt-verify");
  const copyButton = document.getElementById("receipt-copy");
  if (full.token) {
    verifyLink.href = verifyUrl(POLL_ID, full.token);
    verifyLink.classList.remove("hidden");
    copyButton.classList.remove("hidden");
  } else {
    verifyLink.classList.add("hidden");
    copyButton.classList.add("hidden"); // ohne Token gibt es nichts zu kopieren
  }
}

// Schritt 1 braucht hier keinen Code mehr: Die Anmeldung verlaesst die Seite
// (EIP-T-095, /eid-sim/), laeuft ueber Formulare in den simulierten
// Fremdsystemen und kommt als Redirect mit gesetzter Sitzung zurueck. Das
// Modal, das bis dahin hier verdrahtet war, ist mitsamt seiner Fehlerausgabe
// entfallen - Fehler aus dem Flow stehen jetzt serverseitig auf der Seite.

voteButton.addEventListener("click", async () => {
  if (stepVote.classList.contains("blocked")) { redirectToAuth(); return; }

  const choices = [...document.querySelectorAll("input[name=choice]:checked")].map((c) => c.value);
  if (!choices.length) { toast("Bitte mindestens eine Option wählen.", "err"); return; }

  voteButton.disabled = true;
  try {
    const receipt = await castBallot(POLL_ID, N_HEX, E_HEX, choices);
    showReceipt(receipt);
    document.getElementById("participation").textContent = receipt.participation;
    toast("Stimme abgegeben.", "ok");
    stepVote.classList.add("done");
  } catch (err) {
    // Ein Serverfehler ist keine abgelehnte Stimme und darf auch nicht so
    // aussehen (EIP-T-080). Laenger stehen bleibt die Meldung, weil sie im
    // Gegensatz zu "Token verbraucht" nichts erklaert, was die abstimmende
    // Person selbst getan hat.
    toast(err.message, "err", err.serverfehler ? 12000 : 4500);
  } finally {
    voteButton.disabled = false; // zweiter Versuch muss moeglich sein und abgewiesen werden
  }
});

document.getElementById("receipt-download").addEventListener("click", () => {
  const state = loadState(POLL_ID);
  if (!state || !state.voted) return;
  download(`beleg_${POLL_ID}.txt`, receiptText(POLL_ID, withToken(state)));
});

// Token in die Zwischenablage (EIP-T-099). Wer am selben Rechner prueft, soll
// die 64 Zeichen nicht aus dem Kassenbon markieren muessen - dabei rutscht ein
// Zeilenumbruch mit, und die Suche endet in "kein Eintrag", also in der
// Meldung, die sonst den Betreiber belastet.
document.getElementById("receipt-copy").addEventListener("click", async () => {
  const token = withToken(loadState(POLL_ID) || {}).token;
  if (!token) { toast("Dieser Browser hat das Token nicht mehr — nur der gespeicherte Beleg.", "err"); return; }
  try {
    await navigator.clipboard.writeText(token);
    toast("Token kopiert. Es liegt jetzt in der Zwischenablage — wie eine Quittung behandeln.", "ok");
  } catch (_) {
    // Ohne sicheren Kontext oder ohne Erlaubnis gibt es keine Zwischenablage.
    // Dann bleibt das Token sichtbar auf dem Beleg stehen - der Weg von Hand.
    toast("Kopieren hat der Browser nicht erlaubt. Das Token steht auf dem Beleg.", "err");
  }
});

render();
