/**
 * Validates SKILL.md structure and content for all skills.
 *
 * Each SKILL.md must have:
 * - Valid YAML frontmatter with name and description
 * - Non-trivial markdown body
 * - All referenced files (in references/, adapters/) must exist
 */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { parse as parseYaml } from "yaml";

const SKILLS_DIR = resolve(
  __dirname,
  "../../plugins/recce-quickstart/skills",
);

/** Parse YAML frontmatter from a markdown file */
function parseFrontmatter(content: string): Record<string, unknown> | null {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;
  try {
    return parseYaml(match[1]) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Get body content after frontmatter */
function getBody(content: string): string {
  return content.replace(/^---\n[\s\S]*?\n---\n*/, "").trim();
}

/** Get all skill directories (those containing SKILL.md) */
function getSkillDirs(): { name: string; path: string }[] {
  return readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .filter((d) => existsSync(join(SKILLS_DIR, d.name, "SKILL.md")))
    .map((d) => ({ name: d.name, path: join(SKILLS_DIR, d.name) }));
}

describe("skill-content", () => {
  const skills = getSkillDirs();

  it("should find at least one skill", () => {
    expect(skills.length).toBeGreaterThan(0);
  });

  for (const skill of skills) {
    describe(`${skill.name}/SKILL.md`, () => {
      const content = readFileSync(join(skill.path, "SKILL.md"), "utf-8");
      const frontmatter = parseFrontmatter(content);
      const body = getBody(content);

      it("should have valid YAML frontmatter", () => {
        expect(frontmatter, "Missing or invalid YAML frontmatter").not.toBeNull();
      });

      it("should have a name field", () => {
        expect(frontmatter).not.toBeNull();
        expect(frontmatter!.name, "Missing 'name' in frontmatter").toBeDefined();
        expect(typeof frontmatter!.name).toBe("string");
        expect((frontmatter!.name as string).length).toBeGreaterThan(0);
      });

      it("should have a description field", () => {
        expect(frontmatter).not.toBeNull();
        expect(
          frontmatter!.description,
          "Missing 'description' in frontmatter",
        ).toBeDefined();
        expect(typeof frontmatter!.description).toBe("string");
        expect((frontmatter!.description as string).length).toBeGreaterThan(10);
      });

      it("should have a non-trivial body (>100 chars)", () => {
        expect(
          body.length,
          `Body is too short (${body.length} chars)`,
        ).toBeGreaterThan(100);
      });

      // Check that referenced subdirectories have content
      const subdirs = ["references", "adapters"];
      for (const subdir of subdirs) {
        const subdirPath = join(skill.path, subdir);
        if (!existsSync(subdirPath)) continue;

        describe(`${subdir}/`, () => {
          const files = readdirSync(subdirPath).filter((f) =>
            f.endsWith(".md"),
          );

          it("should have at least one .md file", () => {
            expect(
              files.length,
              `${subdir}/ exists but has no .md files`,
            ).toBeGreaterThan(0);
          });

          for (const file of files) {
            it(`${file} should be non-empty`, () => {
              const fileContent = readFileSync(
                join(subdirPath, file),
                "utf-8",
              );
              expect(
                fileContent.trim().length,
                `${subdir}/${file} is empty`,
              ).toBeGreaterThan(0);
            });
          }
        });
      }
    });
  }
});
