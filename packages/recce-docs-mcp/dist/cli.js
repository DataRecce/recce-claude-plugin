#!/usr/bin/env node
// src/cli.ts
/**
 * CLI entry point for the recce-docs-mcp MCP server.
 * Run with: npx recce-docs-mcp
 */
import { RecceDocsServer } from './server.js';
const server = new RecceDocsServer();
server.run().catch(console.error);
