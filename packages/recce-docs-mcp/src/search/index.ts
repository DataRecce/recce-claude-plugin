// src/search/index.ts
import MiniSearch from 'minisearch';
import type { CachedPage } from '../cache/types.js';

export interface SearchResult {
  path: string;
  url: string;
  title: string;
  snippet: string;
  score: number;
}

export class SearchIndex {
  private index: MiniSearch<CachedPage>;
  private pages: Map<string, CachedPage> = new Map();

  constructor() {
    this.index = new MiniSearch<CachedPage>({
      fields: ['title', 'content', 'path'],
      storeFields: ['title', 'path', 'url', 'snippet'],
      searchOptions: {
        boost: { title: 2 },
        fuzzy: 0.2,
        prefix: true
      }
    });
  }

  buildIndex(pages: CachedPage[]): void {
    this.pages.clear();
    this.index.removeAll();

    const documents = pages.map((page, idx) => ({
      id: idx,
      ...page
    }));

    this.index.addAll(documents);

    for (const page of pages) {
      this.pages.set(page.path, page);
    }
  }

  search(query: string, limit: number = 5): SearchResult[] {
    const results = this.index.search(query);

    return results.slice(0, limit).map(result => ({
      path: result.path as string,
      url: result.url as string,
      title: result.title as string,
      snippet: result.snippet as string,
      score: result.score
    }));
  }

  serialize(): string {
    return JSON.stringify(this.index.toJSON());
  }

  restore(serialized: string, pages: CachedPage[]): void {
    this.index = MiniSearch.loadJSON(serialized, {
      fields: ['title', 'content', 'path'],
      storeFields: ['title', 'path', 'url', 'snippet'],
      searchOptions: {
        boost: { title: 2 },
        fuzzy: 0.2,
        prefix: true
      }
    });

    this.pages.clear();
    for (const page of pages) {
      this.pages.set(page.path, page);
    }
  }

  getPage(path: string): CachedPage | undefined {
    return this.pages.get(path);
  }

  getAllPages(): CachedPage[] {
    return Array.from(this.pages.values());
  }
}
