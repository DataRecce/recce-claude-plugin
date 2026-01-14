import type { CacheMetadata, CachedPage } from './types.js';
export * from './types.js';
export declare class Cache {
    private cacheDir;
    private metadataPath;
    private pagesDir;
    constructor(cacheDir: string);
    exists(): boolean;
    isExpired(): boolean;
    loadMetadata(): CacheMetadata;
    saveMetadata(metadata: CacheMetadata): void;
    loadPage(pagePath: string): CachedPage | null;
    savePage(page: CachedPage): void;
    loadAllPages(): CachedPage[];
    clear(): void;
    private pathToFilename;
}
