// src/index.ts
/**
 * @datarecce/docs-mcp - Recce Documentation Service
 *
 * This package provides two entry points:
 *
 * 1. **Library API** (this file): For direct integration in Node.js/serverless environments
 *    ```typescript
 *    import { DocsService } from '@datarecce/docs-mcp';
 *
 *    const docs = DocsService.getInstance({ cacheDir: '/app/cache' });
 *    await docs.ensureReady();
 *    const results = docs.searchDocs('schema diff');
 *    ```
 *
 * 2. **MCP Server CLI**: For Claude Code and other MCP clients
 *    ```bash
 *    npx recce-docs-mcp
 *    ```
 *
 * @module @datarecce/docs-mcp
 */
// Main service export
export { DocsService, } from './service.js';
// Export MCP server for advanced use cases
export { RecceDocsServer } from './server.js';
