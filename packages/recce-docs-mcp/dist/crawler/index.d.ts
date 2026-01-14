import type { SitemapEntry, CrawlResult, CrawlOptions } from './types.js';
export * from './types.js';
export declare function parseSitemap(xml: string): SitemapEntry[];
export declare function extractContent(html: string): {
    title: string;
    content: string;
    snippet: string;
};
export declare function urlToPath(url: string): string;
export declare function fetchSitemap(baseUrl: string): Promise<SitemapEntry[]>;
export declare function crawlPage(url: string): Promise<CrawlResult>;
export declare function crawlAll(entries: SitemapEntry[], options?: CrawlOptions): Promise<CrawlResult[]>;
