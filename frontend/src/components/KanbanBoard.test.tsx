import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData } from "@/lib/kanban";

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];
const makeJsonResponse = (status: number, body: unknown): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("KanbanBoard", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    const boardFromApi = {
      ...initialData,
      columns: initialData.columns.map((column) =>
        column.id === "col-backlog" ? { ...column, title: "Loaded Backlog" } : column
      ),
    };

    fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/board" && method === "GET") {
        return Promise.resolve(makeJsonResponse(200, boardFromApi));
      }
      if (url === "/api/board" && method === "PUT") {
        return Promise.resolve(
          makeJsonResponse(200, JSON.parse((init?.body as string) ?? "{}"))
        );
      }
      return Promise.resolve(makeJsonResponse(404, { detail: "Not found" }));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders five columns", async () => {
    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("loads board data from backend", async () => {
    render(<KanbanBoard />);
    expect(await screen.findByDisplayValue("Loaded Backlog")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/board", { credentials: "include" });
  });

  it("shows an error when loading board data fails", async () => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValueOnce(makeJsonResponse(500, { detail: "Failed" }));

    render(<KanbanBoard />);

    expect(
      await screen.findByText(/could not load saved board data/i)
    ).toBeInTheDocument();
  });

  it("renames a column", async () => {
    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    expect(input).toHaveValue("New Name");

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url, init]) => {
          if (url !== "/api/board" || !init || init.method !== "PUT") {
            return false;
          }
          const payload = JSON.parse((init.body as string) ?? "{}");
          return payload.columns?.[0]?.title === "New Name";
        })
      ).toBe(true)
    );
  });

  it("adds and removes a card", async () => {
    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");
    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(within(column).getByText("New card")).toBeInTheDocument();

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
  });

  it("shows an error when saving board data fails", async () => {
    fetchMock.mockReset();
    const loadedBoard = {
      ...initialData,
      columns: initialData.columns.map((column) =>
        column.id === "col-backlog" ? { ...column, title: "Loaded Backlog" } : column
      ),
    };
    fetchMock
      .mockResolvedValueOnce(makeJsonResponse(200, loadedBoard))
      .mockResolvedValue(makeJsonResponse(500, { detail: "Failed" }));

    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");

    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");

    expect(
      await screen.findByText(/could not save board changes/i)
    ).toBeInTheDocument();
  });
});
