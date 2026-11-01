// Applied before React renders to avoid a light flash. No network resources.
let theme = "dark";
try {
  if (localStorage.getItem("documind-theme") === "light") theme = "light";
} catch {
  /* Storage is optional. */
}
document.documentElement.dataset.theme = theme;
