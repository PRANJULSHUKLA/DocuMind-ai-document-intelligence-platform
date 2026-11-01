import { useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "./ui";

export default function ThemeToggle() {
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || "dark",
  );
  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("documind-theme", next);
    } catch {
      /* Theme remains usable when storage is blocked. */
    }
    setTheme(next);
  }
  return (
    <Button
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className="theme-toggle"
    >
      {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      <span className="sr-only">Change appearance</span>
    </Button>
  );
}
