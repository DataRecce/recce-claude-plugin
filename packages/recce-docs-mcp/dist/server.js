// src/server.ts
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { z } from 'zod';
import { Cache } from './cache/index.js';
import { SearchIndex } from './search/index.js';
import { fetchSitemap, crawlAll } from './crawler/index.js';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Use RECCE_DOCS_CACHE_DIR env var for container environments, fallback to package-relative cache
const CACHE_DIR = process.env.RECCE_DOCS_CACHE_DIR || path.join(__dirname, '..', 'cache');
const DOCS_BASE_URL = 'https://docs.reccehq.com';
const TTL_DAYS = 7;
// Helper to create a text content result
function textResult(text) {
    return {
        content: [{ type: 'text', text }]
    };
}
export class RecceDocsServer {
    server;
    cache;
    searchIndex;
    isReady = false;
    constructor() {
        this.cache = new Cache(CACHE_DIR);
        this.searchIndex = new SearchIndex();
        this.server = new McpServer({
            name: 'recce-docs',
            version: '0.1.0'
        });
        this.registerTools();
    }
    registerTools() {
        // Tool: syncDocs
        this.server.tool('syncDocs', 'Check and sync documentation cache. Auto-called on first use or when expired.', {
            force: z.boolean().optional().default(false).describe('Force re-crawl even if cache is valid')
        }, async (args) => {
            return await this.syncDocs(args.force);
        });
        // Tool: searchDocs
        this.server.tool('searchDocs', 'Search Recce documentation and return relevant page summaries.', {
            query: z.string().describe('Search keywords'),
            limit: z.number().optional().default(5).describe('Number of results to return')
        }, async (args) => {
            await this.ensureReady();
            const results = this.searchIndex.search(args.query, args.limit);
            return textResult(JSON.stringify({ results }, null, 2));
        });
        // Tool: getPage
        this.server.tool('getPage', 'Get the full content of a specific documentation page.', {
            path: z.string().describe('Page path, e.g., /getting-started')
        }, async (args) => {
            await this.ensureReady();
            const page = this.searchIndex.getPage(args.path);
            if (!page) {
                return textResult(JSON.stringify({ error: 'Page not found' }));
            }
            return textResult(JSON.stringify({
                title: page.title,
                url: page.url,
                content: page.content
            }, null, 2));
        });
        // Tool: listSections
        this.server.tool('listSections', 'List documentation structure for navigation.', {}, async () => {
            await this.ensureReady();
            const pages = this.searchIndex.getAllPages();
            const sections = this.buildSectionTree(pages);
            return textResult(JSON.stringify({ sections }, null, 2));
        });
    }
    async ensureReady() {
        if (this.isReady)
            return;
        if (!this.cache.exists()) {
            await this.syncDocs(false);
        }
        else {
            this.loadFromCache();
            if (this.cache.isExpired()) {
                // Background update, don't block
                this.syncDocs(false).catch(console.error);
            }
        }
        this.isReady = true;
    }
    loadFromCache() {
        const pages = this.cache.loadAllPages();
        this.searchIndex.buildIndex(pages);
    }
    async syncDocs(force) {
        const shouldCrawl = force || !this.cache.exists() || this.cache.isExpired();
        if (!shouldCrawl) {
            const metadata = this.cache.loadMetadata();
            return textResult(JSON.stringify({
                status: 'up_to_date',
                pagesUpdated: 0,
                totalPages: Object.keys(metadata.pages).length,
                lastSync: metadata.lastCrawl,
                nextCheck: this.getNextCheckDate(metadata.lastCrawl, metadata.ttlDays)
            }, null, 2));
        }
        console.error('recce-docs-mcp: crawling documentation...');
        const entries = await fetchSitemap(DOCS_BASE_URL);
        const results = await crawlAll(entries, { concurrency: 5 });
        // Save to cache
        this.cache.clear();
        const pagesMetadata = {};
        for (const result of results) {
            this.cache.savePage({
                path: result.path,
                url: result.url,
                title: result.title,
                content: result.content,
                snippet: result.snippet
            });
            pagesMetadata[result.path] = { lastmod: result.lastmod };
        }
        const now = new Date().toISOString();
        this.cache.saveMetadata({
            lastCrawl: now,
            ttlDays: TTL_DAYS,
            pages: pagesMetadata
        });
        // Rebuild index
        const pages = this.cache.loadAllPages();
        this.searchIndex.buildIndex(pages);
        this.isReady = true;
        console.error(`recce-docs-mcp: indexed ${results.length} pages`);
        return textResult(JSON.stringify({
            status: force ? 'updated' : 'created',
            pagesUpdated: results.length,
            totalPages: results.length,
            lastSync: now,
            nextCheck: this.getNextCheckDate(now, TTL_DAYS)
        }, null, 2));
    }
    getNextCheckDate(lastCrawl, ttlDays) {
        const date = new Date(lastCrawl);
        date.setDate(date.getDate() + ttlDays);
        return date.toISOString();
    }
    buildSectionTree(pages) {
        const tree = {};
        for (const page of pages) {
            const parts = page.path.split('/').filter(Boolean);
            let current = tree;
            for (let i = 0; i < parts.length; i++) {
                const part = parts[i];
                if (!current[part]) {
                    current[part] = { _pages: [] };
                }
                if (i === parts.length - 1) {
                    const node = current[part];
                    node._pages.push({ title: page.title, path: page.path, url: page.url });
                }
                current = current[part];
            }
        }
        return tree;
    }
    async run() {
        const transport = new StdioServerTransport();
        await this.server.connect(transport);
        console.error('recce-docs-mcp: server started');
    }
}
