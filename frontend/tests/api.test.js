import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchParts, createPart, deletePart } from '../src/api';

global.fetch = vi.fn();

describe('API Service', () => {
  beforeEach(() => {
    fetch.mockClear();
  });

  it('fetchParts returns data', async () => {
    const mockParts = [{ id: 1, name: 'Root Part' }];
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockParts,
    });

    const result = await fetchParts();
    expect(result).toEqual(mockParts);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/parts');
  });

  it('createPart posts data and returns result', async () => {
    const mockNewPart = { name: 'New Part', parent_id: null };
    const mockResponse = { id: 2, ...mockNewPart };
    
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await createPart(mockNewPart);
    expect(result).toEqual(mockResponse);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/parts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(mockNewPart)
    });
  });

  it('throws error when request fails', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: 'Database issue' }),
    });

    await expect(deletePart(1)).rejects.toThrow('Database issue');
  });
});
