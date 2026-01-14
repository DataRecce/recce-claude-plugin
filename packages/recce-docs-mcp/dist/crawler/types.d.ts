export interface SitemapEntry {
    loc: string;
    lastmod?: string;
}
export interface CrawlResult {
    url: string;
    path: string;
    title: string;
    content: string;
    snippet: string;
    lastmod?: string;
}
export interface CrawlOptions {
    concurrency?: number;
    baseUrl?: string;
}
