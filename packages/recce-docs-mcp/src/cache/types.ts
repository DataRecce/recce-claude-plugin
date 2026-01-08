// src/cache/types.ts
export interface PageMetadata {
  lastmod?: string;
  etag?: string;
}

export interface CacheMetadata {
  lastCrawl: string;
  ttlDays: number;
  pages: Record<string, PageMetadata>;
}

export interface CachedPage {
  path: string;
  url: string;
  title: string;
  content: string;
  snippet: string;
}
