import { beforeEach, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ThemeToggle from "./ThemeToggle";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.dataset.theme = "dark";
});
test("switches both themes and persists the chosen preference", async () => {
  const user = userEvent.setup();
  render(<ThemeToggle />);
  await user.click(
    screen.getByRole("button", { name: "Switch to light mode" }),
  );
  expect(document.documentElement).toHaveAttribute("data-theme", "light");
  expect(localStorage.getItem("documind-theme")).toBe("light");
  await user.click(screen.getByRole("button", { name: "Switch to dark mode" }));
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  expect(localStorage.getItem("documind-theme")).toBe("dark");
});
test("theme remains usable when browser storage is unavailable", async () => {
  const blocked = vi
    .spyOn(Storage.prototype, "setItem")
    .mockImplementation(() => {
      throw new Error("blocked");
    });
  try {
    render(<ThemeToggle />);
    await userEvent.click(
      screen.getByRole("button", { name: "Switch to light mode" }),
    );
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  } finally {
    blocked.mockRestore();
  }
});
