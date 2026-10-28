import type { BackendBoard } from "@/lib/kanban";

const columnKeys = ["col-backlog", "col-discovery", "col-progress", "col-review", "col-done"];

const createBoard = (): BackendBoard => ({
  username: "user",
  boardId: 1,
  columns: columnKeys.map((key, position) => ({
    id: position + 1,
    key,
    title: key.replace("col-", ""),
    position,
    cardIds: key === "col-backlog" ? [1] : [],
  })),
  cards: {
    "1": { id: 1, title: "Seed card", details: "From the fake backend.", columnId: 1, position: 0 },
  },
});

// In-memory stand-in for the board and chat routes used by KanbanBoard.
export const installFakeBackend = () => {
  const board = createBoard();
  let nextCardId = 2;

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const { pathname } = new URL(String(input), "http://localhost");
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    const json = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });

    if (method === "GET" && pathname === "/api/board/user") {
      return json(board);
    }
    if (method === "GET" && pathname === "/api/ai/user/chat") {
      return json({ messages: [], pendingActions: [] });
    }

    const columnMatch = pathname.match(/^\/api\/board\/user\/columns\/([^/]+)(\/cards)?$/);
    const column = board.columns.find((c) => c.key === columnMatch?.[1]);
    if (column && method === "PATCH") {
      column.title = body.title;
      return json({ status: "ok" });
    }
    if (column && method === "POST") {
      const id = nextCardId++;
      board.cards[String(id)] = {
        id,
        title: body.title,
        details: body.details || "No details yet.",
        columnId: column.id,
        position: column.cardIds.length,
      };
      column.cardIds.push(id);
      return json({ id });
    }

    const cardMatch = pathname.match(/^\/api\/board\/user\/cards\/(\d+)$/);
    if (cardMatch && method === "DELETE") {
      const id = Number(cardMatch[1]);
      delete board.cards[String(id)];
      board.columns.forEach((c) => (c.cardIds = c.cardIds.filter((cardId) => cardId !== id)));
      return json({ status: "ok" });
    }

    return new Response("Not found", { status: 404 });
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};
