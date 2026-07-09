import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchBomTree, fetchItem, updateItem, fetchScanStatus } from '../src/api';

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

  it('fetchItem returns item details', async () => {
    const mockItem = { id: 1, name: 'Item 1' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockItem,
    });

    const result = await fetchItem(1);
    expect(result).toEqual(mockItem);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/items/1');
  });

  it('updateItem updates item', async () => {
    const mockItem = { id: 1, name: 'Updated' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockItem,
    });

    const result = await updateItem(1, { name: 'Updated' });
    expect(result).toEqual(mockItem);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/items/1', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Updated' })
    });
  });

  it('fetchScanStatus returns scan status', async () => {
    const mockStatus = { status: 'completed' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockStatus,
    });

    const result = await fetchScanStatus();
    expect(result).toEqual(mockStatus);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/scan-status');
  });
});
