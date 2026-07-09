import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchBomTree, getHealth } from '../src/api';

global.fetch = vi.fn();

describe('API Service', () => {
  beforeEach(() => {
    fetch.mockClear();
  });

  it('fetchBomTree returns data', async () => {
    const mockTree = [{ id: 1, part_number: '30-00000', children: [] }];
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockTree,
    });

    const result = await fetchBomTree();
    expect(result).toEqual(mockTree);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/tree');
  });

  it('throws error when request fails', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: 'Database issue' }),
    });

    await expect(fetchBomTree()).rejects.toThrow('Failed to fetch BOM tree');
  });
});
