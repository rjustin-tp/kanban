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
      if (url === "/api/ai/chat" && method === "POST") {
        const currentBoard = boardFromApi;
        return Promise.resolve(
          makeJsonResponse(200, {
            assistantMessage: "No board changes needed.",
            appliedOperations: false,
            board: currentBoard,
          })
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

  it("debounces column rename into a single save", async () => {
    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "Queue");

    await waitFor(() => {
      const puts = fetchMock.mock.calls.filter(
        ([url, init]) => url === "/api/board" && init?.method === "PUT"
      );
      const finalPut = puts[puts.length - 1];
      expect(finalPut).toBeDefined();
      const payload = JSON.parse((finalPut![1]?.body as string) ?? "{}");
      expect(payload.columns[0].title).toBe("Queue");
    });

    const puts = fetchMock.mock.calls.filter(
      ([url, init]) => url === "/api/board" && init?.method === "PUT"
    );
    expect(puts.length).toBe(1);
  });

  it("does not send conversation field in chat requests", async () => {
    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");

    await userEvent.type(
      screen.getByPlaceholderText(/ask ai to update your board/i),
      "Hello"
    );
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      const chatCall = fetchMock.mock.calls.find(
        ([url, init]) => url === "/api/ai/chat" && init?.method === "POST"
      );
      expect(chatCall).toBeDefined();
      const payload = JSON.parse((chatCall![1]?.body as string) ?? "{}");
      expect(payload).toEqual({ message: "Hello" });
    });
  });

  it("sends chat message and renders assistant reply", async () => {
    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");

    const chatInput = screen.getByPlaceholderText(/ask ai to update your board/i);
    await userEvent.type(chatInput, "What should I focus on next?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText("What should I focus on next?")).toBeInTheDocument();
    expect(await screen.findByText("No board changes needed.")).toBeInTheDocument();

    expect(
      fetchMock.mock.calls.some(([url, init]) => {
        if (url !== "/api/ai/chat" || !init || init.method !== "POST") {
          return false;
        }
        const payload = JSON.parse((init.body as string) ?? "{}");
        return payload.message === "What should I focus on next?";
      })
    ).toBe(true);
  });

  it("applies board returned by ai chat response", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const boardFromApi = {
        ...initialData,
        columns: initialData.columns.map((column) =>
          column.id === "col-backlog" ? { ...column, title: "Loaded Backlog" } : column
        ),
      };
      if (url === "/api/board" && method === "GET") {
        return Promise.resolve(makeJsonResponse(200, boardFromApi));
      }
      if (url === "/api/board" && method === "PUT") {
        return Promise.resolve(
          makeJsonResponse(200, JSON.parse((init?.body as string) ?? "{}"))
        );
      }
      if (url === "/api/ai/chat" && method === "POST") {
        const updatedBoard = {
          ...boardFromApi,
          columns: boardFromApi.columns.map((column) =>
            column.id === "col-backlog" ? { ...column, title: "AI Backlog" } : column
          ),
        };
        return Promise.resolve(
          makeJsonResponse(200, {
            assistantMessage: "Updated your backlog title.",
            appliedOperations: true,
            board: updatedBoard,
          })
        );
      }
      return Promise.resolve(makeJsonResponse(404, { detail: "Not found" }));
    });

    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");

    await userEvent.type(
      screen.getByPlaceholderText(/ask ai to update your board/i),
      "Rename backlog"
    );
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByDisplayValue("AI Backlog")).toBeInTheDocument();
  });

  it("shows error when ai chat request fails", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const boardFromApi = {
        ...initialData,
        columns: initialData.columns.map((column) =>
          column.id === "col-backlog" ? { ...column, title: "Loaded Backlog" } : column
        ),
      };
      if (url === "/api/board" && method === "GET") {
        return Promise.resolve(makeJsonResponse(200, boardFromApi));
      }
      if (url === "/api/board" && method === "PUT") {
        return Promise.resolve(makeJsonResponse(200, boardFromApi));
      }
      if (url === "/api/ai/chat" && method === "POST") {
        return Promise.resolve(makeJsonResponse(502, { detail: "Invalid structured AI response." }));
      }
      return Promise.resolve(makeJsonResponse(404, { detail: "Not found" }));
    });

    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");

    await userEvent.type(screen.getByPlaceholderText(/ask ai to update your board/i), "Do something");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText(/ai request failed\. try again\./i)).toBeInTheDocument();
  });

  it("sends chat when pressing Enter in input", async () => {
    render(<KanbanBoard />);
    await screen.findByDisplayValue("Loaded Backlog");

    const chatInput = screen.getByPlaceholderText(/ask ai to update your board/i);
    await userEvent.type(chatInput, "Move card{enter}");

    expect(await screen.findByText("Move card")).toBeInTheDocument();
    expect(await screen.findByText("No board changes needed.")).toBeInTheDocument();
  });
});
