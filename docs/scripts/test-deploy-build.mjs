import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const docsRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dockerfile = readFileSync(path.join(docsRoot, "Dockerfile-deploy"), "utf8");
const deployRun = dockerfile.match(
  /^RUN git config --global --add safe\.directory \/app[\s\S]*?(?=\n\n)/m,
)?.[0];
assert.ok(deployRun, "locate the actual multi-version Docker build command");

for (const detached of [true, false]) {
  test(`restore current source and shared MDX component (${detached ? "detached HEAD" : "branch"})`, () => {
    const root = mkdtempSync(path.join(tmpdir(), "dbgpt-docs-deploy-"));
    const app = path.join(root, "app");
    const build = path.join(root, "app-build");
    const bin = path.join(root, "bin");
    const film = 'export default function ProductFilm() { return null; }\n';
    const write = (file, text) => {
      mkdirSync(path.dirname(file), { recursive: true });
      writeFileSync(file, text);
    };
    const git = (...args) => execFileSync("git", ["-C", app, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
    try {
      mkdirSync(app, { recursive: true });
      mkdirSync(bin, { recursive: true });
      git("init", "--initial-branch=current");
      git("config", "user.name", "Docs regression test");
      git("config", "user.email", "docs-test@example.invalid");
      for (const version of ["v0.8.2", "v0.8.3"]) {
        write(path.join(app, "docs/docs/overview.mdx"), `# ${version}\n`);
        write(path.join(app, "docs/sidebars.js"), "module.exports = {};\n");
        write(path.join(app, "docs/static/marker.txt"), version);
        write(path.join(app, "docs/src/marker.txt"), version);
        git("add", ".");
        git("commit", "-m", version);
        execFileSync("git", ["-C", app, "tag", "-a", version, "-m", version], {
          env: { ...process.env, GIT_COMMITTER_DATE: version === "v0.8.2" ? "2026-01-01T00:00:00Z" : "2026-01-02T00:00:00Z" },
        });
      }
      write(path.join(app, "docs/docs/overview.mdx"), '# current\nimport ProductFilm from "@site/src/components/mdx/ProductFilm";\n');
      write(path.join(app, "docs/src/components/mdx/ProductFilm.js"), film);
      write(path.join(app, "docs/src/marker.txt"), "current");
      git("add", ".");
      git("commit", "-m", "current docs and product film");
      const currentCommit = git("rev-parse", "HEAD");
      if (detached) git("checkout", "--detach", currentCommit);
      // app-build translations remain current while /app checks out old tags.
      write(path.join(build, "docs/src/components/mdx/ProductFilm.js"), film);
      write(path.join(build, "docs/i18n/zh-CN/docusaurus-plugin-content-docs/current/overview.mdx"),
        'import ProductFilm from "@site/src/components/mdx/ProductFilm";\n# 中文\n');
      // Stub only npm; execute the real checkout/copy shell logic from Dockerfile.
      write(path.join(bin, "npm"), "#!/usr/bin/env node\n" + String.raw`
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const args = process.argv.slice(2);
const component = path.join(process.cwd(), "src/components/mdx/ProductFilm.js");
assert.equal(fs.readFileSync(component, "utf8"), process.env.EXPECTED_FILM);
if (args[1] === "docusaurus") {
  const version = args.at(-1);
  assert.equal(fs.readFileSync("docs/overview.mdx", "utf8"), "# " + version + "\n");
  fs.mkdirSync(path.join("versioned_docs", version), { recursive: true });
  fs.writeFileSync(path.join("versioned_docs", version, "checked.txt"), version);
} else if (args[1] === "build") {
  assert.equal(fs.readFileSync("src/marker.txt", "utf8"), "current");
  assert.ok(fs.readFileSync("docs/overview.mdx", "utf8").startsWith("# current"));
  for (const version of ["v0.8.2", "v0.8.3"]) {
    assert.equal(fs.readFileSync(path.join("versioned_docs", version, "checked.txt"), "utf8"), version);
  }
  fs.mkdirSync("build", { recursive: true });
} else {
  throw new Error("Unexpected npm call: " + args.join(" "));
}
`);
      // macOS has no tac; this adapter preserves the Docker shell's line reversal.
      write(path.join(bin, "tac"), "#!/usr/bin/env node\n" + String.raw`
const fs = require("node:fs");
const text = fs.readFileSync(0, "utf8");
const lines = text.trimEnd().split("\n");
process.stdout.write(lines.reverse().join("\n") + "\n");
`);
      execFileSync("chmod", ["+x", path.join(bin, "npm"), path.join(bin, "tac")]);
      const replacements = {
        "/app-build": build,
        "/app": app,
        "/tmp/ProductFilm.js": path.join(root, "ProductFilm.js"),
      };
      const command = deployRun.slice(4)
        .replace("git config --global --add safe.directory /app &&", "true &&")
        .replace(/\/app-build|\/app|\/tmp\/ProductFilm\.js/g, (match) => replacements[match]);
      execFileSync("/bin/sh", ["-c", command], {
        cwd: app,
        env: { ...process.env, PATH: bin + path.delimiter + process.env.PATH, NUM_VERSION: "2", EXPECTED_FILM: film },
        stdio: ["ignore", "pipe", "pipe"],
      });
      assert.equal(git("rev-parse", "HEAD"), currentCommit);
      assert.equal(readFileSync(path.join(build, "docs/src/components/mdx/ProductFilm.js"), "utf8"), film);
      assert.equal(readFileSync(path.join(build, "docs/build/versions.txt"), "utf8"), "v0.8.3\nv0.8.2\nlatest\n");
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
}
