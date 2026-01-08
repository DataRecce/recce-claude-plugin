// src/cache/__tests__/cache.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { Cache } from '../index.js';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TEST_CACHE_DIR = path.join(__dirname, '.test-cache');

describe('Cache', () => {
  let cache: Cache;

  beforeEach(() => {
    cache = new Cache(TEST_CACHE_DIR);
  });

  afterEach(() => {
    fs.rmSync(TEST_CACHE_DIR, { recursive: true, force: true });
  });

  it('should report not exists when cache directory is empty', () => {
    expect(cache.exists()).toBe(false);
  });

  it('should save and load metadata', () => {
    const metadata = {
      lastCrawl: '2026-01-09T10:00:00Z',
      ttlDays: 7,
      pages: {}
    };
    cache.saveMetadata(metadata);
    expect(cache.exists()).toBe(true);
    expect(cache.loadMetadata()).toEqual(metadata);
  });

  it('should save and load page', () => {
    const page = {
      path: '/getting-started',
      url: 'https://docs.reccehq.com/getting-started/',
      title: 'Getting Started',
      content: '# Getting Started\n\nWelcome to Recce.',
      snippet: 'Welcome to Recce.'
    };
    cache.savePage(page);
    expect(cache.loadPage('/getting-started')).toEqual(page);
  });

  it('should check if cache is expired', () => {
    const oldDate = new Date();
    oldDate.setDate(oldDate.getDate() - 10);

    cache.saveMetadata({
      lastCrawl: oldDate.toISOString(),
      ttlDays: 7,
      pages: {}
    });

    expect(cache.isExpired()).toBe(true);
  });
});
