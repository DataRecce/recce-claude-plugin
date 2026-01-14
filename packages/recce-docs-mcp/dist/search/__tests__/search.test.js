// src/search/__tests__/search.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { SearchIndex } from '../index.js';
describe('SearchIndex', () => {
    let searchIndex;
    const testPages = [
        {
            path: '/getting-started',
            url: 'https://docs.reccehq.com/getting-started/',
            title: 'Getting Started',
            content: 'Welcome to Recce. Learn how to validate your dbt models.',
            snippet: 'Welcome to Recce.'
        },
        {
            path: '/ci-cd/github-actions',
            url: 'https://docs.reccehq.com/ci-cd/github-actions/',
            title: 'GitHub Actions Integration',
            content: 'Set up CI/CD with GitHub Actions for automated data validation.',
            snippet: 'Set up CI/CD with GitHub Actions.'
        },
        {
            path: '/features/row-count-diff',
            url: 'https://docs.reccehq.com/features/row-count-diff/',
            title: 'Row Count Diff',
            content: 'Compare row counts between base and current environments.',
            snippet: 'Compare row counts.'
        }
    ];
    beforeEach(() => {
        searchIndex = new SearchIndex();
        searchIndex.buildIndex(testPages);
    });
    it('should find pages by keyword', () => {
        const results = searchIndex.search('GitHub Actions');
        expect(results.length).toBeGreaterThan(0);
        expect(results[0].path).toBe('/ci-cd/github-actions');
    });
    it('should find pages by fuzzy match', () => {
        const results = searchIndex.search('gihub'); // typo
        expect(results.length).toBeGreaterThan(0);
    });
    it('should boost title matches', () => {
        const results = searchIndex.search('Row Count');
        expect(results[0].title).toBe('Row Count Diff');
    });
    it('should return limited results', () => {
        const results = searchIndex.search('Recce', 1);
        expect(results.length).toBe(1);
    });
    it('should serialize and restore index', () => {
        const serialized = searchIndex.serialize();
        const newIndex = new SearchIndex();
        newIndex.restore(serialized, testPages);
        const results = newIndex.search('GitHub');
        expect(results.length).toBeGreaterThan(0);
    });
});
