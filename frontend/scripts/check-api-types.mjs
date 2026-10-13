// Fails when src/lib/api-types.ts no longer matches backend/openapi.json (run `npm run gen:api`).
import { execFileSync } from "node:child_process";
import { readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const fresh = join(tmpdir(), `api-types-${process.pid}.ts`);
try {
  execFileSync(
    process.execPath,
    ["node_modules/openapi-typescript/bin/cli.js", "../backend/openapi.json", "-o", fresh],
    { stdio: "ignore" },
  );
  const committed = readFileSync("src/lib/api-types.ts", "utf8");
  if (committed !== readFileSync(fresh, "utf8")) {
    console.error("src/lib/api-types.ts is stale: run `npm run gen:api`.");
    process.exit(1);
  }
  console.log("src/lib/api-types.ts is up to date.");
} finally {
  rmSync(fresh, { force: true });
}
