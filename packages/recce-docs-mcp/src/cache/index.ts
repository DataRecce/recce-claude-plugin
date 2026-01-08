// src/cache/index.ts
import * as fs from 'node:fs';
import * as path from 'node:path';
import type { CacheMetadata, CachedPage } from './types.js';

export * from './types.js';

export class Cache {
  private cacheDir: string;
  private metadataPath: string;
  private pagesDir: string;

  constructor(cacheDir: string) {
    this.cacheDir = cacheDir;
    this.metadataPath = path.join(cacheDir, 'metadata.json');
    this.pagesDir = path.join(cacheDir, 'pages');
  }

  exists(): boolean {
    return fs.existsSync(this.metadataPath);
  }

  isExpired(): boolean {
    if (!this.exists()) return true;

    const metadata = this.loadMetadata();
    const lastCrawl = new Date(metadata.lastCrawl);
    const now = new Date();
    const daysSince = (now.getTime() - lastCrawl.getTime()) / (1000 * 60 * 60 * 24);

    return daysSince > metadata.ttlDays;
  }

  loadMetadata(): CacheMetadata {
    const content = fs.readFileSync(this.metadataPath, 'utf-8');
    return JSON.parse(content);
  }

  saveMetadata(metadata: CacheMetadata): void {
    fs.mkdirSync(this.cacheDir, { recursive: true });
    fs.writeFileSync(this.metadataPath, JSON.stringify(metadata, null, 2));
  }

  loadPage(pagePath: string): CachedPage | null {
    const filename = this.pathToFilename(pagePath);
    const filepath = path.join(this.pagesDir, filename);

    if (!fs.existsSync(filepath)) return null;

    const content = fs.readFileSync(filepath, 'utf-8');
    return JSON.parse(content);
  }

  savePage(page: CachedPage): void {
    fs.mkdirSync(this.pagesDir, { recursive: true });
    const filename = this.pathToFilename(page.path);
    const filepath = path.join(this.pagesDir, filename);
    fs.writeFileSync(filepath, JSON.stringify(page, null, 2));
  }

  loadAllPages(): CachedPage[] {
    if (!fs.existsSync(this.pagesDir)) return [];

    const files = fs.readdirSync(this.pagesDir);
    return files
      .filter(f => f.endsWith('.json'))
      .map(f => {
        const content = fs.readFileSync(path.join(this.pagesDir, f), 'utf-8');
        return JSON.parse(content) as CachedPage;
      });
  }

  clear(): void {
    fs.rmSync(this.cacheDir, { recursive: true, force: true });
  }

  private pathToFilename(pagePath: string): string {
    return pagePath.replace(/^\//, '').replace(/\//g, '-') + '.json';
  }
}
