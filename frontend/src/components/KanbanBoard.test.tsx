import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { installFakeBackend } from "@/test/fakeBackend";

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

describe("KanbanBoard", () => {
  let fetchMock: ReturnType<typeof installFakeBackend>;

  beforeEach(() => {
    fetchMock = installFakeBackend();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the board loaded from the backend", async () => {
    render(<KanbanBoard username="user" />);
    expect(await screen.findByText("Seed card")).toBeInTheDocument();
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("renames a column and persists it", async () => {
    render(<KanbanBoard username="user" />);
    await screen.findByText("Seed card");
    const input = within(getFirstColumn()).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    await userEvent.tab();

    expect(input).toHaveValue("New Name");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/board/user/columns/col-backlog"),
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ title: "New Name" }) })
    );
  });

  it("adds and removes a card", async () => {
    render(<KanbanBoard username="user" />);
    await screen.findByText("Seed card");
    const column = getFirstColumn();
    await userEvent.click(within(column).getByRole("button", { name: /add a card/i }));
    await userEvent.type(within(column).getByPlaceholderText(/card title/i), "New card");
    await userEvent.type(within(column).getByPlaceholderText(/details/i), "Notes");
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(await within(column).findByText("New card")).toBeInTheDocument();

    await userEvent.click(within(column).getByRole("button", { name: /delete new card/i }));

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
  });

  it("shows the AI sidebar with send disabled until a message is typed", async () => {
    render(<KanbanBoard username="user" />);
    await screen.findByText("Seed card");
    const send = screen.getByRole("button", { name: /send/i });
    expect(send).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Message"), "hello");
    expect(send).toBeEnabled();
  });

  it("renders the AI sidebar after the columns so it lays out on the right", async () => {
    render(<KanbanBoard username="user" />);
    await screen.findByText("Seed card");
    const columns = screen.getAllByTestId(/column-/i);
    const sidebar = screen.getByRole("complementary");
    expect(
      columns[columns.length - 1].compareDocumentPosition(sidebar) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  });
});
