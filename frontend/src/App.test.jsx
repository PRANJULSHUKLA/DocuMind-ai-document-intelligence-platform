import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";
import { getDocuments } from "./services/documentService";

vi.mock("./components/DocumentWorkspace", () => ({
  default: ({ document }) => <div>{document.filename}</div>,
}));

vi.mock("./services/documentService", () => ({
  getDocuments: vi.fn(),
  getDocumentStatus: vi.fn(),
  analyzeDocument: vi.fn(),
  generateWorkflow: vi.fn(),
}));

vi.mock("./components/UploadDocument", () => ({
  default: ({ onUploaded }) => (
    <button
      onClick={() =>
        onUploaded({
          file_id: "507f1f77bcf86cd799439011",
          filename: "new-contract.pdf",
          status: "completed",
        })
      }
    >
      Complete test upload
    </button>
  ),
}));

beforeEach(() => {
  getDocuments.mockReset().mockResolvedValue([]);
});

test("completed upload selects the document and refreshes the document library", async () => {
  const user = userEvent.setup();
  render(<App />);
  await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(1));
  await user.click(screen.getAllByRole("button", { name: "Documents" })[0]);
  await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(2));
  await user.click(
    screen.getByRole("button", { name: "Complete test upload" }),
  );
  await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(3));
  expect(screen.getAllByText("new-contract.pdf").length).toBeGreaterThan(0);
});

test("document-list failures give the user a visible error", async () => {
  getDocuments.mockRejectedValue(new Error("Backend unavailable"));
  render(<App />);
  expect(await screen.findByText("Backend unavailable")).toBeInTheDocument();
});

test("opening Documents refreshes uploads created from another workspace panel", async () => {
  const user = userEvent.setup();
  getDocuments
    .mockResolvedValueOnce([])
    .mockResolvedValue([
      {
        _id: "507f1f77bcf86cd799439011",
        filename: "collection-upload.pdf",
        status: "completed",
      },
    ]);
  render(<App />);
  await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(1));
  await user.click(screen.getAllByRole("button", { name: "Documents" })[0]);
  await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(2));
  expect(await screen.findByText("collection-upload.pdf")).toBeInTheDocument();
});

test("loading counts are unknown, never a verified zero or empty-library message", async () => {
  let resolve;
  getDocuments.mockReturnValue(
    new Promise((done) => {
      resolve = done;
    }),
  );
  render(<App />);
  expect(screen.getByLabelText("Total documents: loading")).toHaveTextContent(
    "—",
  );
  expect(screen.queryByText("Your workspace is ready")).not.toBeInTheDocument();
  resolve([]);
  expect(
    await screen.findByText("Your workspace is ready"),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Total documents: 0")).toBeInTheDocument();
});

test("a failed list hides zero metrics and empty states and supports a safe retry", async () => {
  getDocuments
    .mockRejectedValueOnce(new Error("Database unavailable"))
    .mockResolvedValue([]);
  const user = userEvent.setup();
  render(<App />);
  expect(
    await screen.findByText("Document library unavailable"),
  ).toBeInTheDocument();
  expect(
    screen.getByLabelText("Total documents: unavailable"),
  ).toHaveTextContent("—");
  expect(screen.queryByText("Your workspace is ready")).not.toBeInTheDocument();
  await user.click(
    screen.getByRole("button", { name: "Retry loading documents" }),
  );
  expect(
    await screen.findByText("Your workspace is ready"),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Total documents: 0")).toHaveTextContent("0");
});

test("a failed refresh retains visible documents but labels counts as unavailable", async () => {
  getDocuments
    .mockResolvedValueOnce([
      { _id: "a", filename: "retained.pdf", status: "completed" },
    ])
    .mockRejectedValueOnce(new Error("Offline"));
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText("retained.pdf");
  await user.click(
    screen.getByRole("button", { name: "Refresh", exact: true }),
  );
  await screen.findByText("Offline");
  expect(screen.getByText("retained.pdf")).toBeInTheDocument();
  expect(
    screen.getByLabelText("Total documents: unavailable"),
  ).toHaveTextContent("—");
  expect(screen.getByText(/Counts may be out of date/)).toBeInTheDocument();
});

test("authentication failure is distinguished from an empty workspace", async () => {
  getDocuments.mockRejectedValue({
    response: { status: 401, data: { detail: "Expired session" } },
  });
  render(<App />);
  expect(await screen.findByText(/Sign-in required/)).toBeInTheDocument();
  expect(screen.queryByText("Your workspace is ready")).not.toBeInTheDocument();
});
