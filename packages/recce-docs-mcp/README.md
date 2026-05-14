# @datarecce/docs-mcp

MCP server and library API for [Recce](https://datarecce.io) documentation. Lets LLM agents search and retrieve Recce docs through the Model Context Protocol.

## Use as an MCP server

Run directly with `npx`:

```bash
npx -y @datarecce/docs-mcp
```

### Claude Code

```bash
claude mcp add recce-docs -- npx -y @datarecce/docs-mcp
```

### Other MCP clients (Cursor, Windsurf, etc.)

Add to your MCP config:

```json
{
  "mcpServers": {
    "recce-docs": {
      "command": "npx",
      "args": ["-y", "@datarecce/docs-mcp"]
    }
  }
}
```

## Use as a library

```typescript
import { DocsService } from "@datarecce/docs-mcp";

const docs = DocsService.getInstance({ cacheDir: "/app/cache" });
await docs.ensureReady();
const results = docs.searchDocs("schema diff");
```

## Tools

| Tool | Description |
|------|-------------|
| `searchDocs` | Full-text search across Recce documentation |
| `getPage` | Fetch a specific documentation page by path |
| `listSections` | Enumerate top-level documentation sections |
| `syncDocs` | Refresh the local docs cache |

## Requirements

- Node.js >= 20

## License

Apache-2.0
