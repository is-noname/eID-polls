// Verdrahtung der Umfrageseite: Der Stimmzettel-Flow steht in ballot.js, die
// Belegdarstellung in beleg.js, die Krypto in blind.js.
//
// Bis EIP-T-007 stand dieser Code inline in templates/poll.html. Dort war er
// nicht pruefbar: Was der Browser ausfuehrt, muss aus dem veroeffentlichten
// Stand nachvollziehbar sein (Paragraf 20), und das geht nur bei einer Datei,
// die unveraendert ausgeliefert wird. Die drei umfragespezifischen Werte
// kommen deshalb als *Daten* aus der Seite, nicht als eingesetzter Quelltext.
import { postJSON, toast, download } from "/static/app.js";
import { castBallot, loadState, pendingBallot, heldBallot } from "/static/ballot.js";
import { receiptPaper, receiptText, verifyUrl } from "/static/beleg.js";

const params = JSON.parse(document.getElementById("poll-params").textContent);
const POLL_ID = params.poll_id;
const N_HEX = params.n;
const E_HEX = params.e;

const stepVote = document.getElementById("step-vote");
const stepReceipt = document.getElementById("step-receipt");
const voteButton = document.getElementById("vote-button");

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
  if (full.token) {
    verifyLink.href = verifyUrl(POLL_ID, full.token);
    verifyLink.classList.remove("hidden");
  } else {
    verifyLink.classList.add("hidden");
  }
}

const authOpenButton = document.getElementById("auth-open-button");
if (authOpenButton) {
  const modalBackdrop = document.getElementById("auth-modal-backdrop");
  const credentialInput = document.getElementById("credential");
  const modalError = document.getElementById("auth-modal-error");
  const cancelButton = document.getElementById("auth-cancel-button");
  const confirmButton = document.getElementById("auth-confirm-button");

  const openModal = () => {
    modalError.textContent = "";
    credentialInput.value = "";
    modalBackdrop.classList.remove("hidden");
    credentialInput.focus();
  };
  const closeModal = () => modalBackdrop.classList.add("hidden");

  authOpenButton.addEventListener("click", openModal);

  cancelButton.addEventListener("click", async () => {
    closeModal();
    try { await postJSON("/api/auth/abort"); } catch (_) { /* Abbruch selbst darf nicht scheitern */ }
  });

  const submit = async () => {
    try {
      await postJSON("/api/auth", { credential: credentialInput.value });
      closeModal();
      location.reload();
    } catch (err) {
      modalError.textContent = err.message;
      toast(err.message, "err");
    }
  };
  confirmButton.addEventListener("click", submit);
  credentialInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submit();
    if (e.key === "Escape") cancelButton.click();
  });
}

voteButton.addEventListener("click", async () => {
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
    toast(err.message, "err");
  } finally {
    voteButton.disabled = false; // zweiter Versuch muss moeglich sein und abgewiesen werden
  }
});

document.getElementById("receipt-download").addEventListener("click", () => {
  const state = loadState(POLL_ID);
  if (!state || !state.voted) return;
  download(`beleg_${POLL_ID}.txt`, receiptText(POLL_ID, withToken(state)));
});

render();
