import type { CachedPage } from '../cache/types.js';
export interface SearchResult {
    path: string;
    url: string;
    title: string;
    snippet: string;
    score: number;
}
export declare class SearchIndex {
    private index;
    private pages;
    constructor();
    buildIndex(pages: CachedPage[]): void;
    search(query: string, limit?: number): SearchResult[];
    serialize(): string;
    restore(serialized: string, pages: CachedPage[]): void;
    getPage(path: string): CachedPage | undefined;
    getAllPages(): CachedPage[];
}
