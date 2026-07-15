import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchBomTree, fetchItem, updateItem, fetchScanStatus, fetchRules, saveRules, fetchProblemDefinitions, saveProblemDefinitions, fetchProblemDefinitionCount, triggerRescan, fetchManufacturers, uploadDatasheet, fetchFlatItems } from '../src/api';

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

  it('fetchRules returns rules config', async () => {
    const mockRules = { '10': { name: 'Raw Material', color: '#10b981' } };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRules
    });

    const result = await fetchRules();
    expect(result).toEqual(mockRules);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/rules');
  });

  it('saveRules updates rules config', async () => {
    const mockRules = { '10': { name: 'Raw Material', color: '#10b981' } };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'success' })
    });

    const result = await saveRules(mockRules);
    expect(result).toEqual({ status: 'success' });
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(mockRules)
    });
  });

  it('fetchProblemDefinitions returns definitions config', async () => {
    const mockDefs = [{ id: 'rule_1', name: 'Rule 1', rule: {} }];
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockDefs
    });

    const result = await fetchProblemDefinitions();
    expect(result).toEqual(mockDefs);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/problem-definitions');
  });

  it('saveProblemDefinitions updates definitions config', async () => {
    const mockDefs = [{ id: 'rule_1', name: 'Rule 1', rule: {} }];
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'success' })
    });

    const result = await saveProblemDefinitions(mockDefs);
    expect(result).toEqual({ status: 'success' });
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/problem-definitions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(mockDefs)
    });
  });

  it('fetchProblemDefinitionCount returns count details', async () => {
    const mockResponse = { id: 'rule_1', count: 5, status: 'completed' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await fetchProblemDefinitionCount('rule_1');
    expect(result).toEqual(mockResponse);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/problem-definitions/rule_1/count');
  });

  it('triggerRescan triggers rescan', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'running' })
    });

    const result = await triggerRescan();
    expect(result).toEqual({ status: 'running' });
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/scan/rescan', {
      method: 'POST'
    });
  });

  it('fetchManufacturers returns manufacturers', async () => {
    const mockM = [{ id: 1, name: 'Nostrali' }];
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockM
    });

    const result = await fetchManufacturers();
    expect(result).toEqual(mockM);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/manufacturers');
  });

  it('uploadDatasheet uploads file', async () => {
    const mockRes = { name: 'test.pdf', url: 'http://url' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes
    });

    const mockFile = new File(['abc'], 'test.pdf', { type: 'application/pdf' });
    const result = await uploadDatasheet(mockFile);
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/upload-file', {
      method: 'POST',
      body: expect.any(FormData)
    });
  });

  it('fetchFlatItems returns flat BOM items', async () => {
    const mockItems = [{ id: 1, 'Part Number': '10-00001' }];
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockItems
    });

    const result = await fetchFlatItems();
    expect(result).toEqual(mockItems);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/items');
  });
});
