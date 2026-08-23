import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  fetchBomTree, fetchItem, updateItem, fetchScanStatus, fetchRules, saveRules,
  fetchProblemDefinitions, saveProblemDefinitions, fetchProblemDefinitionCount,
  triggerRescan, fetchManufacturers, fetchManufacturer, createManufacturer, updateManufacturer, deleteManufacturer,
  fetchSuppliers, fetchSupplier, createSupplier, updateSupplier, deleteSupplier,
  fetchContacts, fetchContact, createContact, updateContact, deleteContact,
  uploadLogo, uploadDatasheet, fetchFlatItems, createAssembly, updateAssembly, deleteAssembly,
  createItem, fetchLogsConfig, saveLogsConfig, fetchActiveLog,
  fetchAuthStatus, fetchAuthConfig, testAuthConfig, saveAuthConfig, checkGlobalAuthStatus
} from '../src/api';

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

  it('createAssembly makes POST request', async () => {
    const mockRes = { id: 10 };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes
    });

    const result = await createAssembly(1, 2, 3, 150, "C1");
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/assembly', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parent_id: 1, child_id: 2, quantity: 3, length: 150, pcb_symbol: "C1" })
    });
  });

  it('updateAssembly makes PATCH request', async () => {
    const mockRes = { id: 10 };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes
    });

    const result = await updateAssembly(10, 5, 200, "C2", 1, 2);
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/assembly/10', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quantity: 5, length: 200, pcb_symbol: "C2", parent_id: 1, child_id: 2 })
    });
  });

  it('deleteAssembly makes DELETE request', async () => {
    const mockRes = { status: 'success' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes
    });

    const result = await deleteAssembly(10);
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/assembly/10', {
      method: 'DELETE'
    });
  });

  it('createItem makes POST request', async () => {
    const mockRes = { id: 99, "Part Number": "10-00005" };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes
    });

    const result = await createItem("10", "New item desc");
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prefix: "10", description: "New item desc" })
    });
  });

  it('fetchLogsConfig returns config details', async () => {
    const mockConfig = { level: 'INFO' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfig
    });

    const result = await fetchLogsConfig();
    expect(result).toEqual(mockConfig);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/logs/config');
  });

  it('saveLogsConfig makes POST request to save config', async () => {
    const mockRes = { status: 'success', level: 'DEBUG' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes
    });

    const result = await saveLogsConfig('DEBUG');
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/logs/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: 'DEBUG' })
    });
  });

  it('fetchActiveLog returns active log filename and content', async () => {
    const mockRes = { filename: 'log_20260719_120000.log', content: 'test logs content' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockRes
    });

    const result = await fetchActiveLog();
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/logs/active');
  });

  it('fetchManufacturers with detailed=true calls correct URL', async () => {
    const mockM = [{ id: 1, Name: 'Nostrali', Notes: 'Notes' }];
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockM });
    const result = await fetchManufacturers(true);
    expect(result).toEqual(mockM);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/manufacturers?detailed=true');
  });

  it('fetchManufacturer by id calls correct endpoint', async () => {
    const mockM = { id: 1, Name: 'Nostrali' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockM });
    const result = await fetchManufacturer(1);
    expect(result).toEqual(mockM);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/manufacturers/1');
  });

  it('createManufacturer posts data', async () => {
    const mockRes = { id: 2, Name: 'Schurter' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockRes });
    const result = await createManufacturer({ Name: 'Schurter' });
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/manufacturers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ Name: 'Schurter' })
    });
  });

  it('updateManufacturer patches data', async () => {
    const mockRes = { id: 2, Name: 'Schurter AG' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockRes });
    const result = await updateManufacturer(2, { Name: 'Schurter AG' });
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/manufacturers/2', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ Name: 'Schurter AG' })
    });
  });

  it('deleteManufacturer deletes row', async () => {
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'deleted' }) });
    const result = await deleteManufacturer(2);
    expect(result).toEqual({ status: 'deleted' });
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/manufacturers/2', { method: 'DELETE' });
  });

  it('fetchSuppliers calls correct URL', async () => {
    const mockS = [{ id: 1, 'Company Name': 'Mouser' }];
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockS });
    const result = await fetchSuppliers();
    expect(result).toEqual(mockS);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/suppliers');
  });

  it('fetchSupplier by id calls correct endpoint', async () => {
    const mockS = { id: 1, 'Company Name': 'Mouser' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockS });
    const result = await fetchSupplier(1);
    expect(result).toEqual(mockS);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/suppliers/1');
  });

  it('createSupplier posts data', async () => {
    const mockRes = { id: 2, 'Company Name': 'DigiKey' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockRes });
    const result = await createSupplier({ 'Company Name': 'DigiKey' });
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/suppliers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 'Company Name': 'DigiKey' })
    });
  });

  it('updateSupplier patches data', async () => {
    const mockRes = { id: 2, 'Company Name': 'DigiKey Inc' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockRes });
    const result = await updateSupplier(2, { 'Company Name': 'DigiKey Inc' });
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/suppliers/2', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 'Company Name': 'DigiKey Inc' })
    });
  });

  it('deleteSupplier deletes row', async () => {
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'deleted' }) });
    const result = await deleteSupplier(2);
    expect(result).toEqual({ status: 'deleted' });
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/suppliers/2', { method: 'DELETE' });
  });

  it('fetchContacts with or without supplierId calls correct URL', async () => {
    const mockC = [{ id: 1, Name: 'Alice' }];
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockC });
    const result1 = await fetchContacts();
    expect(result1).toEqual(mockC);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/contacts');

    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockC });
    const result2 = await fetchContacts(5);
    expect(result2).toEqual(mockC);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/contacts?supplier_id=5');
  });

  it('fetchContact by id calls correct endpoint', async () => {
    const mockC = { id: 1, Name: 'Alice' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockC });
    const result = await fetchContact(1);
    expect(result).toEqual(mockC);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/contacts/1');
  });

  it('createContact posts data', async () => {
    const mockRes = { id: 3, Name: 'Bob' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockRes });
    const result = await createContact({ Name: 'Bob', Email: 'bob@test.com' });
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/contacts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ Name: 'Bob', Email: 'bob@test.com' })
    });
  });

  it('updateContact patches data', async () => {
    const mockRes = { id: 3, Name: 'Bob Updated' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockRes });
    const result = await updateContact(3, { Name: 'Bob Updated' });
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/contacts/3', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ Name: 'Bob Updated' })
    });
  });

  it('deleteContact deletes row', async () => {
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'deleted' }) });
    const result = await deleteContact(3);
    expect(result).toEqual({ status: 'deleted' });
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/contacts/3', { method: 'DELETE' });
  });

  it('uploadLogo uploads image file', async () => {
    const mockRes = { name: 'logo.png', url: 'http://url/logo.png' };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockRes });
    const mockFile = new File(['logo-content'], 'logo.png', { type: 'image/png' });
    const result = await uploadLogo(mockFile);
    expect(result).toEqual(mockRes);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/bom/upload-file', {
      method: 'POST',
      body: expect.any(FormData)
    });
  });

  it('fetchAuthStatus calls GET /api/auth/status', async () => {
    const mockStatus = { is_complete: true, token_valid: true };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockStatus });
    const result = await fetchAuthStatus();
    expect(result).toEqual(mockStatus);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/auth/status');
  });

  it('fetchAuthConfig calls GET /api/auth/config', async () => {
    const mockConfig = { is_complete: true, tables: {} };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockConfig });
    const result = await fetchAuthConfig();
    expect(result).toEqual(mockConfig);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/auth/config');
  });

  it('testAuthConfig calls POST /api/auth/test', async () => {
    const mockResult = { is_connected: true };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockResult });
    const payload = { host: 'http://localhost', port: '7070', token: 'tok' };
    const result = await testAuthConfig(payload);
    expect(result).toEqual(mockResult);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/auth/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  });

  it('saveAuthConfig calls POST /api/auth/save', async () => {
    const mockResult = { success: true };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockResult });
    const payload = { host: 'http://localhost', port: '7070', token: 'tok' };
    const result = await saveAuthConfig(payload);
    expect(result).toEqual(mockResult);
    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/auth/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  });

  it('checkGlobalAuthStatus updates header warning and indicators', async () => {
    document.body.innerHTML = `
      <div class="api-status">
        <span id="status-indicator"></span>
        <span id="status-text"></span>
      </div>
    `;
    const mockIncomplete = { is_complete: false, missing: ['Token'] };
    fetch.mockResolvedValueOnce({ ok: true, json: async () => mockIncomplete });
    const res = await checkGlobalAuthStatus();
    expect(res.isComplete).toBe(false);
    const warning = document.getElementById('header-auth-warning');
    expect(warning).not.toBeNull();
    expect(warning.style.display).not.toBe('none');
  });
});
