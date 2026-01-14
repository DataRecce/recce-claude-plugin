// src/cache/index.ts
import * as fs from 'node:fs';
import * as path from 'node:path';
export * from './types.js';
export class Cache {
    cacheDir;
    metadataPath;
    pagesDir;
    constructor(cacheDir) {
        this.cacheDir = cacheDir;
        this.metadataPath = path.join(cacheDir, 'metadata.json');
        this.pagesDir = path.join(cacheDir, 'pages');
    }
    exists() {
        return fs.existsSync(this.metadataPath);
    }
    isExpired() {
        if (!this.exists())
            return true;
        const metadata = this.loadMetadata();
        const lastCrawl = new Date(metadata.lastCrawl);
        const now = new Date();
        const daysSince = (now.getTime() - lastCrawl.getTime()) / (1000 * 60 * 60 * 24);
        return daysSince > metadata.ttlDays;
    }
    loadMetadata() {
        const content = fs.readFileSync(this.metadataPath, 'utf-8');
        return JSON.parse(content);
    }
    saveMetadata(metadata) {
        fs.mkdirSync(this.cacheDir, { recursive: true });
        fs.writeFileSync(this.metadataPath, JSON.stringify(metadata, null, 2));
    }
    loadPage(pagePath) {
        const filename = this.pathToFilename(pagePath);
        const filepath = path.join(this.pagesDir, filename);
        if (!fs.existsSync(filepath))
            return null;
        const content = fs.readFileSync(filepath, 'utf-8');
        return JSON.parse(content);
    }
    savePage(page) {
        fs.mkdirSync(this.pagesDir, { recursive: true });
        const filename = this.pathToFilename(page.path);
        const filepath = path.join(this.pagesDir, filename);
        fs.writeFileSync(filepath, JSON.stringify(page, null, 2));
    }
    loadAllPages() {
        if (!fs.existsSync(this.pagesDir))
            return [];
        const files = fs.readdirSync(this.pagesDir);
        return files
            .filter(f => f.endsWith('.json'))
            .map(f => {
            const content = fs.readFileSync(path.join(this.pagesDir, f), 'utf-8');
            return JSON.parse(content);
        });
    }
    clear() {
        fs.rmSync(this.cacheDir, { recursive: true, force: true });
    }
    pathToFilename(pagePath) {
        return pagePath.replace(/^\//, '').replace(/\//g, '-') + '.json';
    }
}
