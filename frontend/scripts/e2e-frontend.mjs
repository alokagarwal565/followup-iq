// Builds and serves the frontend for Playwright against the E2E API (port 8001), in its own
// build directory so it never overwrites the normal .next output.
import { spawn, spawnSync } from "node:child_process";
import { resolve } from "node:path";

const frontend = resolve(import.meta.dirname, "..");
const env = {
  ...process.env,
  NEXT_PUBLIC_API_BASE_URL: "http://localhost:8001",
  NEXT_DIST_DIR: ".next-e2e",
};
const next = resolve(frontend, "node_modules/next/dist/bin/next");

const build = spawnSync(process.execPath, [next, "build"], {
  cwd: frontend,
  env,
  stdio: "inherit",
});
if (build.status !== 0) process.exit(build.status ?? 1);

const server = spawn(process.execPath, [next, "start", "-p", "3001"], {
  cwd: frontend,
  env,
  stdio: "inherit",
});
const stop = () => server.kill();
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
server.on("exit", (code) => process.exit(code ?? 0));
