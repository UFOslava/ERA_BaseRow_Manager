import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock the API calls made when main.js is loaded/run
vi.mock('../src/api.js', () => {
  return {
    fetchBomTree: vi.fn(),
    fetchItem: vi.fn(),
    updateItem: vi.fn(),
    fetchScanStatus: vi.fn(),
    getHealth: vi.fn(),
    fetchRules: vi.fn(),
    fetchFlatItems: vi.fn().mockResolvedValue([]),
    fetchManufacturers: vi.fn().mockResolvedValue([]),
    fetchStates: vi.fn().mockResolvedValue({}),
    checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: {} })
  };
});

import { sortTreeNodesRecursively, filterNode, disabledCategories, disabledStates, allItems, applyStructuralFilter, renderDrawerStructural, getFilterHasParents, setFilterHasParents, getFilterHasChildren, setFilterHasChildren } from '../src/main.js';

describe('BOM Sorting & Filtering Logic', () => {
  beforeEach(() => {
    disabledCategories.clear();
    disabledStates.clear();
    setFilterHasParents(null);
    setFilterHasChildren(null);
  });

  describe('sortTreeNodesRecursively', () => {
    it('sorts active first, disabled second, and then alphanumerically by part number', () => {
      const mockTree = [
        {
          id: 1,
          part_number: '10-00002',
          pn_tag: { name: 'Raw Material' },
          isDisabledCategory: true,
          children: []
        },
        {
          id: 2,
          part_number: '20-00001',
          pn_tag: { name: 'Mechanical COTS' },
          isDisabledCategory: false,
          children: []
        },
        {
          id: 3,
          part_number: '10-00001',
          pn_tag: { name: 'Raw Material' },
          isDisabledCategory: false,
          children: []
        },
        {
          id: 4,
          part_number: '99-99999',
          pn_tag: null,
          isDisabledCategory: true,
          children: []
        }
      ];

      const sorted = sortTreeNodesRecursively(mockTree);
      
      // Expected Order:
      // Active group (sorted by PN):
      // 1. Raw Material (10-00001) - id 3
      // 2. Mechanical COTS (20-00001) - id 2
      // Disabled group (sorted by PN):
      // 3. Raw Material (10-00002) - id 1
      // 4. Unknown (99-99999) - id 4
      
      expect(sorted[0].id).toBe(3);
      expect(sorted[1].id).toBe(2);
      expect(sorted[2].id).toBe(1);
      expect(sorted[3].id).toBe(4);
    });

    it('recursively sorts children', () => {
      const mockTree = [
        {
          id: 1,
          part_number: '10-00001',
          pn_tag: { name: 'Raw Material' },
          children: [
            {
              id: 12,
              part_number: '30-00002',
              pn_tag: { name: 'Mechanical Custom' }
            },
            {
              id: 11,
              part_number: '30-00001',
              pn_tag: { name: 'Mechanical Custom' }
            }
          ]
        }
      ];

      const sorted = sortTreeNodesRecursively(mockTree);
      expect(sorted[0].children[0].id).toBe(11);
      expect(sorted[0].children[1].id).toBe(12);
    });
  });

  describe('filterNode category and search filtering', () => {
    it('sets isDisabledCategory on nodes of disabled categories but does not hide them', () => {
      const node = {
        id: 1,
        part_number: '30-00001',
        pn_tag: { name: 'Mechanical Custom' },
        children: []
      };

      // Initially enabled
      let result = filterNode(node, '', '1', []);
      expect(result).not.toBeNull();
      expect(result.isDisabledCategory).toBe(false);

      // Disable category
      disabledCategories.add('Mechanical Custom');
      result = filterNode(node, '', '1', []);
      expect(result).not.toBeNull();
      expect(result.isDisabledCategory).toBe(true);
    });

    it('retains child nodes of disabled categories with their respective status', () => {
      const node = {
        id: 1,
        part_number: '10-00001',
        pn_tag: { name: 'Raw Material' },
        children: [
          {
            id: 2,
            part_number: '30-00001',
            pn_tag: { name: 'Mechanical Custom' },
            children: []
          }
        ]
      };

      disabledCategories.add('Mechanical Custom');
      const filtered = filterNode(node, '', '1', []);
      expect(filtered).not.toBeNull();
      expect(filtered.isDisabledCategory).toBe(false);
      expect(filtered.children.length).toBe(1);
      expect(filtered.children[0].isDisabledCategory).toBe(true);
    });

    it('still hides nodes if they do not match search query', () => {
      const node = {
        id: 1,
        part_number: '10-00001',
        pn_tag: { name: 'Raw Material' },
        children: []
      };

      const result = filterNode(node, 'nonexistent-query', '1', []);
      expect(result).toBeNull();
    });

    it('matches nodes by external_pn and notes search properties', () => {
      const node = {
        id: 1,
        part_number: '10-00001',
        pn_tag: { name: 'Raw Material' },
        external_pn: 'EXT-PN-VAL',
        notes: 'Spec note content',
        children: []
      };

      const matchExt = filterNode(node, 'ext-pn', '1', []);
      expect(matchExt).not.toBeNull();

      const matchNotes = filterNode(node, 'spec note', '1', []);
      expect(matchNotes).not.toBeNull();
    });

    it('does not hide or gray out nested items that do not match the search if their ancestor matches', () => {
      const node = {
        id: 1,
        part_number: '10-00001',
        description: 'Matching Parent Assembly',
        pn_tag: { name: 'Raw Material' },
        children: [
          {
            id: 2,
            part_number: '20-00002',
            description: 'Non-matching Child Component',
            pn_tag: { name: 'Raw Material' },
            children: []
          }
        ]
      };

      const result = filterNode(node, 'parent assembly', '1', []);
      
      expect(result).not.toBeNull();
      expect(result.children.length).toBe(1);
      
      const childResult = result.children[0];
      expect(childResult.id).toBe(2);
      expect(childResult.isDisabledCategory).toBe(false);
      expect(childResult.isMatch).toBe(true);
    });

    it('grays out nodes if their state is in disabledStates', () => {
      const node = {
        id: 1,
        part_number: '10-00001',
        description: 'Component',
        state: 'EOL',
        pn_tag: { name: 'Raw Material' },
        children: []
      };

      let result = filterNode(node, '', '1', []);
      expect(result).not.toBeNull();
      expect(result.isDisabledCategory).toBe(false);

      disabledStates.add('EOL');
      result = filterNode(node, '', '1', []);
      expect(result).not.toBeNull();
      expect(result.isDisabledCategory).toBe(true);
    });
  });

  describe('duplicate revision filtering among siblings', () => {
    beforeEach(() => {
      allItems.length = 0;
    });

    it('filters out duplicate PN nodes of older revisions, keeping only the latest revision among siblings', () => {
      allItems.push(
        { id: 1, 'Part Number': '40-00000', 'Revision': 'A' },
        { id: 2, 'Part Number': '40-00000', 'Revision': 'B' },
        { id: 3, 'Part Number': '40-00000', 'Revision': 'Z' },
        { id: 4, 'Part Number': '50-11111', 'Revision': 'A' }
      );

      const siblingNodes = [
        {
          id: 1,
          part_number: '40-00000',
          pn_tag: { name: 'Electrical COTS' },
          isDisabledCategory: false,
          children: []
        },
        {
          id: 2,
          part_number: '40-00000',
          pn_tag: { name: 'Electrical COTS' },
          isDisabledCategory: false,
          children: []
        },
        {
          id: 3,
          part_number: '40-00000',
          pn_tag: { name: 'Electrical COTS' },
          isDisabledCategory: false,
          children: []
        },
        {
          id: 4,
          part_number: '50-11111',
          pn_tag: { name: 'Electrical Custom' },
          isDisabledCategory: false,
          children: []
        }
      ];

      const sortedAndFiltered = sortTreeNodesRecursively(siblingNodes);
      
      expect(sortedAndFiltered.length).toBe(2);
      expect(sortedAndFiltered.map(n => n.id)).toContain(3);
      expect(sortedAndFiltered.map(n => n.id)).toContain(4);
      expect(sortedAndFiltered.map(n => n.id)).not.toContain(1);
      expect(sortedAndFiltered.map(n => n.id)).not.toContain(2);
    });
  });

  describe('renderDrawerStates UI rendering', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <div id="states-filter-list"></div>
        <span id="filter-badge"></span>
        <button id="btn-filter"></button>
      `;
    });

    it('renders the checklist of states with correct colors', async () => {
      const { renderDrawerStates, STATE_COLORS } = await import('../src/main.js');
      renderDrawerStates();

      const container = document.getElementById('states-filter-list');
      const items = container.querySelectorAll('.category-filter-item');
      expect(items.length).toBe(Object.keys(STATE_COLORS).length + 1); // 6 states + 1 select-all item

      const firstStateItem = items[1]; // Index 0 is Select All item, index 1 is first state
      const colorDot = firstStateItem.querySelector('.category-color-dot');
      expect(colorDot.style.backgroundColor).toBe('rgb(0, 255, 0)'); // Production Use color in rgb
    });
  });

  describe('renderDrawerCategories UI rendering', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <div id="categories-filter-list"></div>
        <span id="filter-badge"></span>
        <button id="btn-filter"></button>
      `;
    });

    it('renders the checklist of categories with prefix sorted numerically', async () => {
      const { renderDrawerCategories, categoryRules } = await import('../src/main.js');
      
      // Seed rules
      for (const k of Object.keys(categoryRules)) {
        delete categoryRules[k];
      }
      categoryRules['40'] = { name: 'Electrical COTS', color: 'cyan' };
      categoryRules['10'] = { name: 'Raw Material', color: 'red' };
      categoryRules['55'] = { name: 'Assemblies & Kits', color: 'orange' };

      renderDrawerCategories();

      const container = document.getElementById('categories-filter-list');
      const items = container.querySelectorAll('.category-filter-item');
      
      expect(items.length).toBe(5);

      expect(items[1].textContent).toContain('10 - Raw Material');
      expect(items[2].textContent).toContain('40 - Electrical COTS');
      expect(items[3].textContent).toContain('55 - Assemblies & Kits');
      expect(items[4].textContent).toContain('Unknown');
    });
  });

  describe('refreshData retry button and countdown', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <div id="tree-container"></div>
        <div id="toast-container" class="toast-container"></div>
      `;
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('renders a retry button with a 10s countdown on fetch failure', async () => {
      const api = await import('../src/api.js');
      api.fetchBomTree.mockRejectedValueOnce(new Error('Network Error'));
      api.fetchScanStatus.mockResolvedValue({ status: 'completed' });
      
      const { refreshData, disabledCategories } = await import('../src/main.js');
      disabledCategories.add('Some Category');
      await refreshData();

      const treeContainer = document.getElementById('tree-container');
      expect(treeContainer.innerHTML).toContain('Error: failed to fetch BOM tree');
      
      const retryBtn = document.getElementById('btn-retry-refresh');
      expect(retryBtn).toBeTruthy();
      expect(retryBtn.querySelector('span').textContent).toBe('Refresh (10s)');

      // Advance timers by 1 second
      vi.advanceTimersByTime(1000);
      expect(retryBtn.querySelector('span').textContent).toBe('Refresh (9s)');

      // Mock success for the auto-triggered refresh after 10s
      api.fetchBomTree.mockResolvedValueOnce([]);
      api.fetchRules.mockResolvedValueOnce({});
      api.fetchFlatItems.mockResolvedValueOnce([]);

      // Advance remaining 11 seconds to trigger auto-refresh
      await vi.advanceTimersByTimeAsync(11000);
      
      expect(treeContainer.querySelector('#btn-retry-refresh')).toBeNull();
    });
  });

  describe('Conditional fetching based on search/filter', () => {
    let api;
    beforeEach(async () => {
      api = await import('../src/api.js');
      api.fetchBomTree.mockReset();
      api.fetchFlatItems.mockReset();
      api.fetchRules.mockReset();
      api.fetchStates.mockReset();
      
      api.fetchBomTree.mockResolvedValue([]);
      api.fetchFlatItems.mockResolvedValue([]);
      api.fetchRules.mockResolvedValue({});
      api.fetchStates.mockResolvedValue({});

      const { disabledCategories, disabledStates, resetSearchState } = await import('../src/main.js');
      disabledCategories.clear();
      disabledStates.clear();
      resetSearchState();

      document.body.innerHTML = `
        <div id="tree-container"></div>
        <div id="toast-container" class="toast-container"></div>
        <input type="text" id="search-input" />
        <div id="filter-drawer" class="drawer">
          <div class="drawer-overlay" id="drawer-overlay"></div>
          <button id="btn-close-drawer" class="btn-close"></button>
        </div>
      `;
    });

    it('does not fetch tree/flat data on initial load if no search or filter is active but fetches rules/states', async () => {
      const { refreshData } = await import('../src/main.js');
      await refreshData();
      expect(api.fetchBomTree).not.toHaveBeenCalled();
      expect(api.fetchFlatItems).not.toHaveBeenCalled();
      expect(api.fetchRules).toHaveBeenCalled();
      expect(api.fetchStates).toHaveBeenCalled();
    });

    it('fetches BOM when filter is active', async () => {
      const { refreshData, disabledCategories } = await import('../src/main.js');
      disabledCategories.add('Raw Material');
      await refreshData();
      expect(api.fetchBomTree).toHaveBeenCalled();
      expect(api.fetchFlatItems).toHaveBeenCalled();
    });

    it('does not fetch BOM when typing (only Enter triggers search)', async () => {
      const { init } = await import('../src/main.js');
      await init();
      const input = document.getElementById('search-input');
      input.value = 'part';
      input.dispatchEvent(new Event('input'));
      expect(api.fetchBomTree).not.toHaveBeenCalled();
      expect(api.fetchFlatItems).not.toHaveBeenCalled();
    });

    it('does not fetch BOM when query is short and only typing (no Enter)', async () => {
      const { init } = await import('../src/main.js');
      await init();
      const input = document.getElementById('search-input');
      input.value = 'fan';
      input.dispatchEvent(new Event('input'));
      expect(api.fetchBomTree).not.toHaveBeenCalled();
      expect(api.fetchFlatItems).not.toHaveBeenCalled();
    });

    it('fetches BOM when Enter is pressed on search input', async () => {
      const { init } = await import('../src/main.js');
      await init();
      const input = document.getElementById('search-input');
      input.value = 'fan';
      const event = new KeyboardEvent('keydown', { key: 'Enter' });
      input.dispatchEvent(event);
      expect(api.fetchBomTree).toHaveBeenCalled();
      expect(api.fetchFlatItems).toHaveBeenCalled();
    });
  });
});

describe('Multi-token search: nodeMatchesQuery', () => {
  let nodeMatchesQuery;
  let setSearchMode;
  let mainModule;

  beforeEach(async () => {
    vi.resetModules();
    mainModule = await import('../src/main.js');
    nodeMatchesQuery = mainModule.nodeMatchesQuery;
    setSearchMode = mainModule.setSearchMode;
    // Reset to default ALL mode
    setSearchMode('all');
  });

  const makeNode = (part_number, description, search_helper = '', external_pn = '', notes = '') =>
    ({ part_number, description, search_helper, external_pn, notes });

  it('matches "30 59" against part_number "30-00059" via search_helper or combined string', () => {
    const node = makeNode('30-00059', 'Some Part', '30 59');
    expect(nodeMatchesQuery(node, '30 59')).toBe(true);
  });

  it('matches "30 59" against part_number "30-00059" even without search_helper (both tokens appear in combined)', () => {
    const node = makeNode('30-00059', 'description without tokens', '');
    // '30' and '59' both appear in '30-00059' inside the combined string
    expect(nodeMatchesQuery(node, '30 59')).toBe(true);
  });

  it('matches "m3 8" against a description containing "M3" and "8" (case-insensitive)', () => {
    const node = makeNode('20-00001', 'M3 x 8 Flat Head Phillips Screw, SS', '');
    expect(nodeMatchesQuery(node, 'm3 8')).toBe(true);
  });

  it('does NOT match "m3 8" against a node that only has M3 but not 8', () => {
    const node = makeNode('20-00001', 'M3 Pan Head Screw', '');
    // No "8" anywhere in combined string
    expect(nodeMatchesQuery(node, 'm3 8')).toBe(false);
  });

  it('matches an empty query (no search)', () => {
    const node = makeNode('10-00001', 'Some part');
    expect(nodeMatchesQuery(node, '')).toBe(true);
  });

  it('in ANY mode, matches if at least one token hits', () => {
    setSearchMode('any');
    const node = makeNode('30-00059', 'No eighty here', '');
    // '30' matches, '99' does not — should still match in ANY mode
    expect(nodeMatchesQuery(node, '30 99')).toBe(true);
  });

  it('in ALL mode, does NOT match if one token is missing', () => {
    setSearchMode('all');
    const node = makeNode('30-00059', 'No eighty here', '');
    // '99' is not in combined string
    expect(nodeMatchesQuery(node, '30 99')).toBe(false);
  });

  it('searches across all fields — token in notes still matches', () => {
    const node = makeNode('10-00001', 'Plain Part', '', '', 'contains bolt M5');
    expect(nodeMatchesQuery(node, 'm5')).toBe(true);
  });

  describe('applyStructuralFilter', () => {
    beforeEach(() => {
      setFilterHasParents(null);
      setFilterHasChildren(null);
    });

    const mockNodes = [
      { id: 1, part_number: '10-00000', has_parents: false, has_children: true },
      { id: 2, part_number: '20-00000', has_parents: true, has_children: false },
      { id: 3, part_number: '30-00000', has_parents: true, has_children: true },
      { id: 4, part_number: '40-00000', has_parents: false, has_children: false }
    ];

    it('returns all nodes when filters are null', () => {
      expect(applyStructuralFilter(mockNodes)).toEqual(mockNodes);
    });

    it('filters by has_parents when filterHasParents is set', () => {
      setFilterHasParents(true);
      const res = applyStructuralFilter(mockNodes);
      expect(res.map(n => n.id)).toEqual([2, 3]);

      setFilterHasParents(false);
      const res2 = applyStructuralFilter(mockNodes);
      expect(res2.map(n => n.id)).toEqual([1, 4]);
    });

    it('filters by has_children when filterHasChildren is set', () => {
      setFilterHasChildren(true);
      const res = applyStructuralFilter(mockNodes);
      expect(res.map(n => n.id)).toEqual([1, 3]);

      setFilterHasChildren(false);
      const res2 = applyStructuralFilter(mockNodes);
      expect(res2.map(n => n.id)).toEqual([2, 4]);
    });

    it('combines both filters correctly', () => {
      setFilterHasParents(true);
      setFilterHasChildren(true);
      const res = applyStructuralFilter(mockNodes);
      expect(res.map(n => n.id)).toEqual([3]);
    });
  });
});
