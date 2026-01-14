// src/search/index.ts
import MiniSearch from 'minisearch';
export class SearchIndex {
    index;
    pages = new Map();
    constructor() {
        this.index = new MiniSearch({
            fields: ['title', 'content', 'path'],
            storeFields: ['title', 'path', 'url', 'snippet'],
            searchOptions: {
                boost: { title: 2 },
                fuzzy: 0.2,
                prefix: true
            }
        });
    }
    buildIndex(pages) {
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
    search(query, limit = 5) {
        const results = this.index.search(query);
        return results.slice(0, limit).map(result => ({
            path: result.path,
            url: result.url,
            title: result.title,
            snippet: result.snippet,
            score: result.score
        }));
    }
    serialize() {
        return JSON.stringify(this.index.toJSON());
    }
    restore(serialized, pages) {
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
    getPage(path) {
        return this.pages.get(path);
    }
    getAllPages() {
        return Array.from(this.pages.values());
    }
}
