// Theme vor dem ersten Paint setzen, sonst blitzt beim Umschalter Hell auf.
//
// Bewusst eine eigene Datei statt eines Inline-Blocks: Nur was unter /static
// liegt, wird Byte fuer Byte so ausgeliefert, wie es im Repository steht - und
// laesst sich von aussen dagegen halten (KODEX Paragraf 20, EIP-T-007). Ein
// Inline-Block steckt in der gerenderten Seite und ist dort mit nichts mehr
// vergleichbar.
try {
  if (localStorage.getItem("eidpoll:theme") !== "light") {
    document.documentElement.setAttribute("data-theme", "dark");
  }
} catch (e) {
  // localStorage gesperrt - dann eben Dunkel, die Voreinstellung.
  document.documentElement.setAttribute("data-theme", "dark");
}
