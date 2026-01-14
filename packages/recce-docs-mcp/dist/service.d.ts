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
import { type CachedPage } from './cache/index.js';
import { type SearchResult } from './search/index.js';
export interface DocsServiceOptions {
    /** Directory for caching documentation. Required. */
    cacheDir: string;
    /** TTL in days before cache is considered stale. Default: 7 */
    ttlDays?: number;
    /** Base URL for documentation site. Default: https://docs.reccehq.com */
    docsBaseUrl?: string;
}
export interface PageContent {
    title: string;
    url: string;
    path: string;
    content: string;
    snippet: string;
}
export interface SyncStatus {
    status: 'up_to_date' | 'syncing' | 'synced' | 'error';
    totalPages: number;
    lastSync: string | null;
    nextCheck: string | null;
    error?: string;
}
export { SearchResult, CachedPage };
export declare class DocsService {
    private static instances;
    private cache;
    private searchIndex;
    private options;
    private isReady;
    private syncPromise;
    private constructor();
    /**
     * Get or create a DocsService instance for the given cache directory.
     * Uses singleton pattern to reuse instances across requests.
     */
    static getInstance(options: DocsServiceOptions): DocsService;
    /**
     * Reset all singleton instances. Useful for testing.
     */
    static resetInstances(): void;
    /**
     * Ensure the service is ready to serve requests.
     * Loads from cache if available, triggers background sync if expired.
     */
    ensureReady(): Promise<void>;
    /**
     * Search documentation for the given query.
     * Returns relevant page summaries with scores.
     */
    searchDocs(query: string, limit?: number): SearchResult[];
    /**
     * Get full content of a specific documentation page.
     * Returns null if page not found.
     */
    getPage(path: string): PageContent | null;
    /**
     * List all available documentation pages.
     */
    listPages(): Array<{
        path: string;
        title: string;
        url: string;
    }>;
    /**
     * Get current sync status.
     */
    getStatus(): SyncStatus;
    /**
     * Force synchronization of documentation cache.
     * @param force If true, re-crawl even if cache is valid
     */
    sync(force?: boolean): Promise<SyncStatus>;
    private performSync;
    private syncInBackground;
    private loadFromCache;
    private getNextCheckDate;
}
