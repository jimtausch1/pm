// Serves the static frontend build through the real FastAPI backend for Playwright.
import { spawn } from "node:child_process";
import { cpSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const backendDir = path.resolve(frontendDir, "../backend");
const staticDir = path.join(backendDir, "static/frontend");

rmSync(staticDir, { recursive: true, force: true });
cpSync(path.join(frontendDir, "out"), staticDir, { recursive: true });

const python = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
const server = spawn(
  python,
  ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "3101"],
  {
    cwd: backendDir,
    stdio: "inherit",
    env: { ...process.env, PM_DB_PATH: path.join(tmpdir(), `pm-e2e-${Date.now()}.db`) },
  }
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.kill(signal));
}
server.on("exit", (code) => process.exit(code ?? 0));
