import { expect, test, type Locator, type Page } from "@playwright/test";

// Runs against the FastAPI backend with a fresh seeded database (see playwright.config.ts).
// Seed cards: 1-2 Backlog, 3 Discovery, 4-5 In Progress, 6 Review, 7-8 Done.
// At 1280px wide the Done column is past the right edge, so drags start from visible columns.

const signIn = async (page: Page) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="card-"]').first()).toBeVisible();
};

const startDrag = async (page: Page, source: Locator, target: Locator, offsetY: number) => {
  const sourceBox = await source.boundingBox();
  const targetBox = await target.boundingBox();
  if (!sourceBox || !targetBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }
  await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + offsetY, { steps: 12 });
};

test("loads the kanban board from the backend", async ({ page }) => {
  await signIn(page);
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
  await expect(page.getByText("Align roadmap themes")).toBeVisible();
});

test("adds a card and keeps it after reload", async ({ page }) => {
  await signIn(page);
  const firstColumn = page.getByTestId("column-col-backlog");
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("column-col-backlog").getByText("Playwright card")).toBeVisible();
});

test("moves a card between columns and keeps it after reload", async ({ page }) => {
  await signIn(page);
  const targetColumn = page.getByTestId("column-col-review");
  await startDrag(page, page.getByTestId("card-1"), targetColumn, 120);
  await page.mouse.up();
  await expect(targetColumn.getByTestId("card-1")).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("column-col-review").getByTestId("card-1")).toBeVisible();
});

test("moves a card in front of the top card of a multi-card column", async ({ page }) => {
  await signIn(page);
  const progress = page.getByTestId("column-col-progress");
  await startDrag(page, page.getByTestId("card-3"), page.getByTestId("card-4"), 10);
  await page.mouse.up();
  await expect(progress.locator('[data-testid^="card-"]').first()).toHaveAttribute(
    "data-testid",
    "card-3"
  );

  await page.reload();
  await expect(
    page.getByTestId("column-col-progress").locator('[data-testid^="card-"]').first()
  ).toHaveAttribute("data-testid", "card-3");
});

test("highlights target column during drag", async ({ page }) => {
  await signIn(page);
  const targetColumn = page.getByTestId("column-col-discovery");
  await startDrag(page, page.getByTestId("card-3"), targetColumn, 120);
  await expect(targetColumn).toHaveClass(/ring-2/);
  await page.mouse.up();
});

test("logs out back to sign in screen", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});
