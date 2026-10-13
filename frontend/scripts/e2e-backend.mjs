// Starts the API for Playwright: fake AI, a throwaway e2e schema on the test database, port 8001.
// The database URL is read from backend/.env at runtime and never printed.
import { spawn, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const backend = resolve(import.meta.dirname, "../../backend");
const envFile = readFileSync(join(backend, ".env"), "utf8");
const testUrl = envFile.match(/^TEST_DATABASE_URL=(.+)$/m)?.[1]?.trim();
if (!testUrl) {
  console.error("TEST_DATABASE_URL is missing from backend/.env");
  process.exit(1);
}

const env = {
  ...process.env,
  // Search_path is session state, so use Neon's direct endpoint rather than its pooler.
  DATABASE_URL: testUrl.replace("-pooler.", "."),
  DATABASE_SCHEMA: "e2e_frontend",
  GEMINI_FAKE: "1",
  ENV: "test",
  CORS_ORIGINS: "http://localhost:3001",
  RATE_LIMIT_WRITES_PER_MIN: "600",
};
const python = join(
  backend,
  process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python",
);

const setup = spawnSync(python, ["-m", "app.cli.e2e_setup"], {
  cwd: backend,
  env,
  stdio: "inherit",
});
if (setup.status !== 0) process.exit(setup.status ?? 1);

const server = spawn(python, ["-m", "app.cli.serve", "--port", "8001"], {
  cwd: backend,
  env,
  stdio: "inherit",
});
const stop = () => server.kill();
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
server.on("exit", (code) => process.exit(code ?? 0));
