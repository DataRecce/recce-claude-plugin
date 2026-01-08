// src/crawler/index.ts
import * as cheerio from 'cheerio';
import TurndownService from 'turndown';
import type { SitemapEntry, CrawlResult, CrawlOptions } from './types.js';

export * from './types.js';

const turndown = new TurndownService({
  headingStyle: 'atx',
  codeBlockStyle: 'fenced'
});

export function parseSitemap(xml: string): SitemapEntry[] {
  const $ = cheerio.load(xml, { xmlMode: true });
  const entries: SitemapEntry[] = [];

  $('url').each((_, el) => {
    const loc = $(el).find('loc').text();
    const lastmod = $(el).find('lastmod').text() || undefined;
    entries.push({ loc, lastmod });
  });

  return entries;
}

export function extractContent(html: string): { title: string; content: string; snippet: string } {
  const $ = cheerio.load(html);

  // Remove navigation, footer, scripts, styles
  $('nav, footer, script, style, .md-sidebar, .md-header').remove();

  // Get title from h1 or page title
  const h1 = $('article h1, main h1, .md-content h1').first().text().trim();
  const pageTitle = $('title').text().split(' - ')[0].trim();
  const title = h1 || pageTitle || 'Untitled';

  // Get main content
  const article = $('article, main, .md-content').first();
  const contentHtml = article.length ? article.html() : $('body').html();
  const content = turndown.turndown(contentHtml || '');

  // Generate snippet from first paragraph
  const firstP = $('article p, main p, .md-content p').first().text().trim();
  const snippet = firstP.slice(0, 200) || content.slice(0, 200);

  return { title, content, snippet };
}

export function urlToPath(url: string): string {
  const urlObj = new URL(url);
  let path = urlObj.pathname;
  // Remove trailing slash except for root
  if (path !== '/' && path.endsWith('/')) {
    path = path.slice(0, -1);
  }
  return path;
}

export async function fetchSitemap(baseUrl: string): Promise<SitemapEntry[]> {
  const sitemapUrl = `${baseUrl}/sitemap.xml`;
  const response = await fetch(sitemapUrl);
  if (!response.ok) {
    throw new Error(`Failed to fetch sitemap: ${response.status}`);
  }
  const xml = await response.text();
  return parseSitemap(xml);
}

export async function crawlPage(url: string): Promise<CrawlResult> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch page ${url}: ${response.status}`);
  }
  const html = await response.text();
  const { title, content, snippet } = extractContent(html);
  const path = urlToPath(url);

  return { url, path, title, content, snippet };
}

export async function crawlAll(
  entries: SitemapEntry[],
  options: CrawlOptions = {}
): Promise<CrawlResult[]> {
  const { concurrency = 5 } = options;
  const results: CrawlResult[] = [];

  // Simple concurrency control
  for (let i = 0; i < entries.length; i += concurrency) {
    const batch = entries.slice(i, i + concurrency);
    const batchResults = await Promise.all(
      batch.map(async (entry): Promise<CrawlResult | null> => {
        try {
          const result = await crawlPage(entry.loc);
          return { ...result, lastmod: entry.lastmod };
        } catch (error) {
          console.error(`Failed to crawl ${entry.loc}:`, error);
          return null;
        }
      })
    );
    results.push(...batchResults.filter((r): r is CrawlResult => r !== null));
  }

  return results;
}
