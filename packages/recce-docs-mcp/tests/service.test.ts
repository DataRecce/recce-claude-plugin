// tests/service.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { DocsService } from '../src/service.js';

// Mock the crawler module to avoid network calls
vi.mock('../src/crawler/index.js', () => ({
  fetchSitemap: vi.fn().mockResolvedValue([
    { loc: 'https://docs.reccehq.com/getting-started', lastmod: '2024-01-01' },
    { loc: 'https://docs.reccehq.com/features/schema-diff', lastmod: '2024-01-02' },
  ]),
  crawlAll: vi.fn().mockResolvedValue([
    {
      url: 'https://docs.reccehq.com/getting-started',
      path: '/getting-started',
      title: 'Getting Started',
      content: 'Welcome to Recce. This guide will help you get started with data validation.',
      snippet: 'Welcome to Recce. This guide will help you get started.',
      lastmod: '2024-01-01',
    },
    {
      url: 'https://docs.reccehq.com/features/schema-diff',
      path: '/features/schema-diff',
      title: 'Schema Diff',
      content: 'Schema diff compares table schemas between base and current environments.',
      snippet: 'Schema diff compares table schemas between environments.',
      lastmod: '2024-01-02',
    },
  ]),
}));

const TEST_CACHE_DIR = path.join(__dirname, '.test-cache');

describe('DocsService', () => {
  beforeEach(() => {
    // Clean up test cache before each test
    if (fs.existsSync(TEST_CACHE_DIR)) {
      fs.rmSync(TEST_CACHE_DIR, { recursive: true, force: true });
    }
    // Reset singleton instances
    DocsService.resetInstances();
  });

  afterEach(() => {
    // Clean up test cache after each test
    if (fs.existsSync(TEST_CACHE_DIR)) {
      fs.rmSync(TEST_CACHE_DIR, { recursive: true, force: true });
    }
  });

  describe('getInstance', () => {
    it('returns the same instance for the same cache directory', () => {
      const instance1 = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      const instance2 = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      expect(instance1).toBe(instance2);
    });

    it('returns different instances for different cache directories', () => {
      const instance1 = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      const instance2 = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR + '-other' });
      expect(instance1).not.toBe(instance2);

      // Clean up the other cache dir
      if (fs.existsSync(TEST_CACHE_DIR + '-other')) {
        fs.rmSync(TEST_CACHE_DIR + '-other', { recursive: true, force: true });
      }
    });
  });

  describe('ensureReady', () => {
    it('syncs documentation when cache does not exist', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      await service.ensureReady();

      expect(fs.existsSync(path.join(TEST_CACHE_DIR, 'metadata.json'))).toBe(true);
      expect(fs.existsSync(path.join(TEST_CACHE_DIR, 'pages'))).toBe(true);
    });

    it('loads from cache when cache exists', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });

      // First call triggers sync
      await service.ensureReady();

      // Reset instance but keep cache
      DocsService.resetInstances();

      // Second instance should load from cache without syncing
      const service2 = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      await service2.ensureReady();

      // Should still work
      const results = service2.searchDocs('getting started');
      expect(results.length).toBeGreaterThan(0);
    });
  });

  describe('searchDocs', () => {
    it('throws error when not ready', () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      expect(() => service.searchDocs('test')).toThrow('DocsService not ready');
    });

    it('returns search results', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      await service.ensureReady();

      const results = service.searchDocs('schema diff');
      expect(results.length).toBeGreaterThan(0);
      expect(results[0]).toHaveProperty('path');
      expect(results[0]).toHaveProperty('title');
      expect(results[0]).toHaveProperty('url');
      expect(results[0]).toHaveProperty('score');
    });

    it('respects limit parameter', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      await service.ensureReady();

      const results = service.searchDocs('recce', 1);
      expect(results.length).toBeLessThanOrEqual(1);
    });
  });

  describe('getPage', () => {
    it('throws error when not ready', () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      expect(() => service.getPage('/getting-started')).toThrow('DocsService not ready');
    });

    it('returns page content for valid path', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      await service.ensureReady();

      const page = service.getPage('/getting-started');
      expect(page).not.toBeNull();
      expect(page?.title).toBe('Getting Started');
      expect(page?.content).toContain('Recce');
    });

    it('returns null for invalid path', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      await service.ensureReady();

      const page = service.getPage('/non-existent-page');
      expect(page).toBeNull();
    });
  });

  describe('listPages', () => {
    it('throws error when not ready', () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      expect(() => service.listPages()).toThrow('DocsService not ready');
    });

    it('returns all pages', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      await service.ensureReady();

      const pages = service.listPages();
      expect(pages.length).toBe(2);
      expect(pages[0]).toHaveProperty('path');
      expect(pages[0]).toHaveProperty('title');
      expect(pages[0]).toHaveProperty('url');
    });
  });

  describe('getStatus', () => {
    it('returns error status when cache not initialized', () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      const status = service.getStatus();

      expect(status.status).toBe('error');
      expect(status.totalPages).toBe(0);
    });

    it('returns up_to_date status after sync', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      await service.ensureReady();

      const status = service.getStatus();
      expect(status.status).toBe('up_to_date');
      expect(status.totalPages).toBe(2);
      expect(status.lastSync).toBeTruthy();
      expect(status.nextCheck).toBeTruthy();
    });
  });

  describe('sync', () => {
    it('syncs documentation', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      const status = await service.sync();

      expect(status.status).toBe('up_to_date');
      expect(status.totalPages).toBe(2);
    });

    it('force sync re-crawls even when cache is valid', async () => {
      const service = DocsService.getInstance({ cacheDir: TEST_CACHE_DIR });
      await service.sync();

      // Force sync should still work
      const status = await service.sync(true);
      expect(status.totalPages).toBe(2);
    });
  });
});
