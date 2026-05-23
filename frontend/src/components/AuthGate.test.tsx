import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthGate } from "@/components/AuthGate";

const makeJsonResponse = (status: number, body: unknown): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("AuthGate", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows login form when no active session exists", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeJsonResponse(401, { detail: "Not authenticated" }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AuthGate />);

    expect(await screen.findByRole("heading", { name: /sign in/i })).toBeVisible();
    expect(screen.getByLabelText(/username/i)).toBeVisible();
    expect(screen.getByLabelText(/password/i)).toBeVisible();
  });

  it("validates login form fields before submit", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeJsonResponse(401, { detail: "Not authenticated" }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AuthGate />);
    await screen.findByRole("heading", { name: /sign in/i });

    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByText(/username and password are required/i)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("transitions from login to board and back on logout", async () => {
    const boardPayload = {
      columns: [
        { id: "col-backlog", title: "Backlog", cardIds: ["card-1"] },
        { id: "col-discovery", title: "Discovery", cardIds: [] },
        { id: "col-progress", title: "In Progress", cardIds: [] },
        { id: "col-review", title: "Review", cardIds: [] },
        { id: "col-done", title: "Done", cardIds: [] },
      ],
      cards: {
        "card-1": { id: "card-1", title: "Task", details: "Details" },
      },
    };

    let authenticated = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url === "/api/auth/session" && method === "GET") {
        if (authenticated) {
          return Promise.resolve(makeJsonResponse(200, { authenticated: true, user: "user" }));
        }
        return Promise.resolve(
          makeJsonResponse(401, { detail: "Not authenticated" })
        );
      }
      if (url === "/api/auth/login" && method === "POST") {
        authenticated = true;
        return Promise.resolve(makeJsonResponse(200, { ok: true, user: "user" }));
      }
      if (url === "/api/board" && method === "GET") {
        return Promise.resolve(makeJsonResponse(200, boardPayload));
      }
      if (url === "/api/auth/logout" && method === "POST") {
        authenticated = false;
        return Promise.resolve(makeJsonResponse(200, { ok: true }));
      }
      return Promise.resolve(makeJsonResponse(404, { detail: "Not found" }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AuthGate />);
    await screen.findByRole("heading", { name: /sign in/i });

    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: /log out/i }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /sign in/i })).toBeVisible()
    );
  });
});
