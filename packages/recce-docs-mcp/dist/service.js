// src/service.ts
/**
 * DocsService - A singleton service for accessing Recce documentation.
 *
 * This service provides a direct API for searching and retrieving documentation,
 * suitable for use in serverless environments like Next.js API routes where
 * stdio-based MCP communication is not practical.
 *
 * @example
 * ```typescript
 * import { DocsService } from '@datarecce/docs-mcp';
 *
 * const docs = DocsService.getInstance({ cacheDir: '/app/cache' });
 * await docs.ensureReady();
 * const results = docs.searchDocs('schema diff', 5);
 * ```
 */
import { Cache } from './cache/index.js';
import { fetchSitemap, crawlAll } from './crawler/index.js';
import { SearchIndex } from './search/index.js';
const DOCS_BASE_URL = 'https://docs.reccehq.com';
const DEFAULT_TTL_DAYS = 7;
export class DocsService {
    static instances = new Map();
    cache;
    searchIndex;
    options;
    isReady = false;
    syncPromise = null;
    constructor(options) {
        this.options = {
            cacheDir: options.cacheDir,
            ttlDays: options.ttlDays ?? DEFAULT_TTL_DAYS,
            docsBaseUrl: options.docsBaseUrl ?? DOCS_BASE_URL,
        };
        this.cache = new Cache(this.options.cacheDir);
        this.searchIndex = new SearchIndex();
    }
    /**
     * Get or create a DocsService instance for the given cache directory.
     * Uses singleton pattern to reuse instances across requests.
     */
    static getInstance(options) {
        const key = options.cacheDir;
        let instance = DocsService.instances.get(key);
        if (!instance) {
            instance = new DocsService(options);
            DocsService.instances.set(key, instance);
        }
        return instance;
    }
    /**
     * Reset all singleton instances. Useful for testing.
     */
    static resetInstances() {
        DocsService.instances.clear();
    }
    /**
     * Ensure the service is ready to serve requests.
     * Loads from cache if available, triggers background sync if expired.
     */
    async ensureReady() {
        if (this.isReady)
            return;
        // If sync is already in progress, wait for it
        if (this.syncPromise) {
            await this.syncPromise;
            return;
        }
        if (!this.cache.exists()) {
            // No cache exists, must sync synchronously
            await this.sync(false);
        }
        else {
            // Load existing cache
            this.loadFromCache();
            this.isReady = true;
            // Trigger background refresh if expired
            if (this.cache.isExpired()) {
                this.syncInBackground();
            }
        }
    }
    /**
     * Search documentation for the given query.
     * Returns relevant page summaries with scores.
     */
    searchDocs(query, limit = 5) {
        if (!this.isReady) {
            throw new Error('DocsService not ready. Call ensureReady() first.');
        }
        return this.searchIndex.search(query, limit);
    }
    /**
     * Get full content of a specific documentation page.
     * Returns null if page not found.
     */
    getPage(path) {
        if (!this.isReady) {
            throw new Error('DocsService not ready. Call ensureReady() first.');
        }
        const page = this.searchIndex.getPage(path);
        if (!page)
            return null;
        return {
            title: page.title,
            url: page.url,
            path: page.path,
            content: page.content,
            snippet: page.snippet,
        };
    }
    /**
     * List all available documentation pages.
     */
    listPages() {
        if (!this.isReady) {
            throw new Error('DocsService not ready. Call ensureReady() first.');
        }
        return this.searchIndex.getAllPages().map((p) => ({
            path: p.path,
            title: p.title,
            url: p.url,
        }));
    }
    /**
     * Get current sync status.
     */
    getStatus() {
        if (!this.cache.exists()) {
            return {
                status: this.syncPromise ? 'syncing' : 'error',
                totalPages: 0,
                lastSync: null,
                nextCheck: null,
                error: this.syncPromise ? undefined : 'Cache not initialized',
            };
        }
        const metadata = this.cache.loadMetadata();
        const lastSync = metadata.lastCrawl;
        const nextCheck = this.getNextCheckDate(lastSync, metadata.ttlDays);
        return {
            status: this.syncPromise ? 'syncing' : 'up_to_date',
            totalPages: Object.keys(metadata.pages).length,
            lastSync,
            nextCheck,
        };
    }
    /**
     * Force synchronization of documentation cache.
     * @param force If true, re-crawl even if cache is valid
     */
    async sync(force = false) {
        const shouldCrawl = force || !this.cache.exists() || this.cache.isExpired();
        if (!shouldCrawl) {
            return this.getStatus();
        }
        // Prevent concurrent syncs
        if (this.syncPromise) {
            await this.syncPromise;
            return this.getStatus();
        }
        this.syncPromise = this.performSync();
        try {
            await this.syncPromise;
        }
        finally {
            this.syncPromise = null;
        }
        return this.getStatus();
    }
    async performSync() {
        console.error('[DocsService] Crawling documentation...');
        try {
            const entries = await fetchSitemap(this.options.docsBaseUrl);
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
                    snippet: result.snippet,
                });
                pagesMetadata[result.path] = { lastmod: result.lastmod };
            }
            const now = new Date().toISOString();
            this.cache.saveMetadata({
                lastCrawl: now,
                ttlDays: this.options.ttlDays,
                pages: pagesMetadata,
            });
            // Rebuild index
            const pages = this.cache.loadAllPages();
            this.searchIndex.buildIndex(pages);
            this.isReady = true;
            console.error(`[DocsService] Indexed ${results.length} pages`);
        }
        catch (error) {
            console.error('[DocsService] Sync failed:', error);
            throw error;
        }
    }
    syncInBackground() {
        this.sync(false).catch((error) => {
            console.error('[DocsService] Background sync failed:', error);
        });
    }
    loadFromCache() {
        const pages = this.cache.loadAllPages();
        this.searchIndex.buildIndex(pages);
    }
    getNextCheckDate(lastCrawl, ttlDays) {
        const date = new Date(lastCrawl);
        date.setDate(date.getDate() + ttlDays);
        return date.toISOString();
    }
}
