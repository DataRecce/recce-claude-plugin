// src/crawler/__tests__/crawler.test.ts
import { describe, it, expect } from 'vitest';
import { parseSitemap, extractContent, urlToPath } from '../index.js';

describe('Crawler utilities', () => {
  it('should parse sitemap XML', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://docs.reccehq.com/getting-started/</loc>
        <lastmod>2026-01-05</lastmod>
      </url>
      <url>
        <loc>https://docs.reccehq.com/ci-cd/</loc>
      </url>
    </urlset>`;

    const entries = parseSitemap(xml);
    expect(entries).toHaveLength(2);
    expect(entries[0]).toEqual({
      loc: 'https://docs.reccehq.com/getting-started/',
      lastmod: '2026-01-05'
    });
    expect(entries[1]).toEqual({
      loc: 'https://docs.reccehq.com/ci-cd/',
      lastmod: undefined
    });
  });

  it('should extract content from HTML', () => {
    const html = `
    <html>
      <head><title>Getting Started - Recce Docs</title></head>
      <body>
        <nav>Navigation</nav>
        <article>
          <h1>Getting Started</h1>
          <p>Welcome to Recce documentation.</p>
          <p>Learn how to use Recce for data validation.</p>
        </article>
        <footer>Footer</footer>
      </body>
    </html>`;

    const result = extractContent(html);
    expect(result.title).toBe('Getting Started');
    expect(result.content).toContain('Welcome to Recce');
    expect(result.content).not.toContain('Navigation');
    expect(result.snippet).toBe('Welcome to Recce documentation.');
  });

  it('should convert URL to path', () => {
    expect(urlToPath('https://docs.reccehq.com/getting-started/')).toBe('/getting-started');
    expect(urlToPath('https://docs.reccehq.com/ci-cd/github-actions/')).toBe('/ci-cd/github-actions');
    expect(urlToPath('https://docs.reccehq.com/')).toBe('/');
  });
});
