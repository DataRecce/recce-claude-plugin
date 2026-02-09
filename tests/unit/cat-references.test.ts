/**
 * Validates that all !cat references in command files point to existing files.
 *
 * Claude Code commands use `!cat ${CLAUDE_PLUGIN_ROOT}/path` to include
 * skill content at runtime. This test catches broken references immediately
 * after a skill restructure.
 */
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const PLUGIN_ROOT = resolve(__dirname, "../../plugins/recce-quickstart");
const COMMANDS_DIR = join(PLUGIN_ROOT, "commands");

/** Parse all !cat references from a markdown file */
function parseCatReferences(content: string): string[] {
  // Match: !`cat ${CLAUDE_PLUGIN_ROOT}/path/to/file`
  const pattern = /!\`cat \$\{CLAUDE_PLUGIN_ROOT\}\/([^`]+)\`/g;
  const paths: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(content)) !== null) {
    paths.push(match[1]);
  }
  return paths;
}

/** Get all .md command files */
function getCommandFiles(): string[] {
  return readdirSync(COMMANDS_DIR)
    .filter((f) => f.endsWith(".md"))
    .map((f) => join(COMMANDS_DIR, f));
}

describe("cat-references", () => {
  const commandFiles = getCommandFiles();

  it("should find at least one command file", () => {
    expect(commandFiles.length).toBeGreaterThan(0);
  });

  for (const commandFile of commandFiles) {
    const fileName = commandFile.split("/").pop()!;
    const content = readFileSync(commandFile, "utf-8");
    const refs = parseCatReferences(content);

    if (refs.length === 0) continue;

    describe(fileName, () => {
      for (const ref of refs) {
        it(`!cat reference "${ref}" should exist`, () => {
          const fullPath = join(PLUGIN_ROOT, ref);
          expect(
            existsSync(fullPath),
            `Referenced file not found: ${fullPath}`,
          ).toBe(true);
        });

        it(`!cat reference "${ref}" should be non-empty`, () => {
          const fullPath = join(PLUGIN_ROOT, ref);
          if (!existsSync(fullPath)) return;
          const stat = statSync(fullPath);
          expect(stat.size, `Referenced file is empty: ${fullPath}`).toBeGreaterThan(0);
        });
      }
    });
  }
});
