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

import { sortTreeNodesRecursively, filterNode, disabledCategories, disabledStates, allItems, applyStructuralFilter, renderDrawerStructural, getFilterHasParents, setFilterHasParents, getFilterHasChildren, setFilterHasChildren, getViewMode, setViewMode, renderFlatBomTable, renderFlatBomRow, getParentAssemblyCount, updateParentCounts, resetSearchState } from '../src/main.js';

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
  let itemMatchesQuery;
  let setSearchMode;
  let mainModule;

  beforeEach(async () => {
    mainModule = await import('../src/main.js');
    nodeMatchesQuery = mainModule.nodeMatchesQuery;
    itemMatchesQuery = mainModule.itemMatchesQuery;
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

  describe('itemMatchesQuery on flat BOM items and aliases', () => {
    it('matches flat BOM items using Part Number and Search helper', () => {
      const flatItem = {
        id: 10,
        "Part Number": "30-00059",
        "Item description": "Handle Shell Upper",
        "Search helper": "30 59",
        "External PN": "EXT-3059",
        "Notes": "M3 threaded inserts"
      };

      expect(itemMatchesQuery(flatItem, '30 59')).toBe(true);
      expect(itemMatchesQuery(flatItem, 'handle upper')).toBe(true);
      expect(itemMatchesQuery(flatItem, 'ext 3059')).toBe(true);
      expect(itemMatchesQuery(flatItem, 'm3 inserts')).toBe(true);
      expect(itemMatchesQuery(flatItem, 'nonexistent')).toBe(false);
    });

    it('matches flat BOM items with capital Search Helper and Description aliases', () => {
      const flatItem = {
        id: 20,
        "Part Number": "40-00049",
        "Description": "100pF 50V Ceramic Capacitor",
        "Search Helper": "40 49",
        "External Part Number": "GRM188R71H104KA93D"
      };

      expect(itemMatchesQuery(flatItem, '40 49')).toBe(true);
      expect(itemMatchesQuery(flatItem, '100pf 50v')).toBe(true);
      expect(itemMatchesQuery(flatItem, 'grm188')).toBe(true);
    });

    it('matches Molex PNs ignoring dividers (hyphens, dots, slashes)', () => {
      const molexItem1 = {
        id: 30,
        "Part Number": "40-00050",
        "Item description": "Molex Mini-Fit Female Crimp Terminal",
        "External PN": "39-00-00-39"
      };

      const molexItem2 = {
        id: 31,
        "Part Number": "40-00051",
        "Item description": "Molex Mini-Fit Jr Receptacle Housing 2 Pos",
        "External PN": "39-01-2020"
      };

      const molexItem3 = {
        id: 32,
        "Part Number": "40-00052",
        "Item description": "Molex Connector",
        "External PN": "39012020"
      };

      // Search without dividers against item with dividers
      expect(itemMatchesQuery(molexItem1, '39000039')).toBe(true);
      expect(itemMatchesQuery(molexItem1, '39-00-00-39')).toBe(true);
      expect(itemMatchesQuery(molexItem1, '39-00-0039')).toBe(true);
      expect(itemMatchesQuery(molexItem1, 'crimp 39000039')).toBe(true);

      expect(itemMatchesQuery(molexItem2, '39012020')).toBe(true);
      expect(itemMatchesQuery(molexItem2, '39-01-2020')).toBe(true);
      expect(itemMatchesQuery(molexItem2, 'molex 39012020')).toBe(true);

      // Search with dividers against item stored without dividers
      expect(itemMatchesQuery(molexItem3, '39-01-2020')).toBe(true);
      expect(itemMatchesQuery(molexItem3, '39-01-20-20')).toBe(true);
    });

    it('handles empty query and invalid items safely', () => {
      expect(itemMatchesQuery({ id: 1 }, '')).toBe(true);
      expect(itemMatchesQuery({ id: 1 }, '   ')).toBe(true);
      expect(itemMatchesQuery(null, 'query')).toBe(false);
      expect(itemMatchesQuery(undefined, 'query')).toBe(false);
    });
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

describe('Flat BOM View & View Switching Logic', () => {
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

    document.body.innerHTML = `
      <h1 class="page-title" id="page-title">Nested BOM</h1>
      <button id="btn-view-nested" class="btn btn-secondary btn-view active">Nested</button>
      <button id="btn-view-flat" class="btn btn-secondary btn-view">Flat</button>
      <a href="#" id="menu-item-nested" class="menu-item active">Nested BOM View</a>
      <a href="#" id="menu-item-flat" class="menu-item">Flat BOM View</a>
      <div id="tree-container"></div>
      <div class="col-desc" id="header-col-desc">Part Description (Hierarchy)</div>
      <div class="col-qty" id="header-col-qty">Quantity</div>
      <input type="text" id="search-input" />
      <button id="btn-search-mode">ALL</button>
      <div id="hamburger-menu" class="hamburger-menu-dropdown"></div>
    `;
    disabledCategories.clear();
    disabledStates.clear();
    setFilterHasParents(null);
    setFilterHasChildren(null);
    resetSearchState();
    allItems.length = 0;
  });

  it('toggles view mode between nested and flat and updates UI labels and classes', () => {
    setViewMode('flat', false);
    expect(getViewMode()).toBe('flat');
    expect(document.getElementById('page-title').textContent).toBe('Flat BOM');
    expect(document.getElementById('btn-view-flat').classList.contains('active')).toBe(true);
    expect(document.getElementById('btn-view-nested').classList.contains('active')).toBe(false);
    expect(document.getElementById('menu-item-flat').classList.contains('active')).toBe(true);
    expect(document.getElementById('menu-item-nested').classList.contains('active')).toBe(false);
    expect(document.getElementById('header-col-desc').textContent).toBe('Part Description');
    expect(document.getElementById('header-col-qty').textContent).toBe('Assemblies');

    setViewMode('nested', false);
    expect(getViewMode()).toBe('nested');
    expect(document.getElementById('page-title').textContent).toBe('Nested BOM');
    expect(document.getElementById('btn-view-nested').classList.contains('active')).toBe(true);
    expect(document.getElementById('btn-view-flat').classList.contains('active')).toBe(false);
    expect(document.getElementById('header-col-desc').textContent).toBe('Part Description (Hierarchy)');
    expect(document.getElementById('header-col-qty').textContent).toBe('Quantity');
  });

  it('renders flat BOM table sorted by PN and groups revisions under latest revision item', () => {
    setViewMode('flat', false);
    allItems.push(
      { id: 1, "Part Number": "20-00001", "Revision": "A", "Item description": "M3 Nut", State: "Production Use" },
      { id: 2, "Part Number": "20-00001", "Revision": "B", "Item description": "M3 Nut Rev B", State: "Production Use" },
      { id: 3, "Part Number": "10-00005", "Revision": "A", "Item description": "Aluminum Sheet", State: "Production Use" },
      { id: 4, "Part Number": "30-00002", "Revision": "A", "Item description": "Enclosure Box", State: "Production Use" }
    );

    renderFlatBomTable();

    const container = document.getElementById('tree-container');
    const rows = container.querySelectorAll('.tree-row');
    expect(rows.length).toBe(3); // 10-00005, 20-00001 (rev B), 30-00002

    // First row: 10-00005
    const firstPn = rows[0].querySelector('.pn-number').textContent;
    expect(firstPn).toBe('10-00005');

    // Second row: 20-00001
    const secondPn = rows[1].querySelector('.pn-number').textContent;
    expect(secondPn).toBe('20-00001');
    const secondDesc = rows[1].querySelector('.node-text').textContent;
    expect(secondDesc).toBe('M3 Nut Rev B'); // Latest revision description

    // Revisions pill tags rendered for 20-00001
    const revTags = rows[1].querySelectorAll('.revision-tag');
    expect(revTags.length).toBe(2);
    expect(revTags[0].textContent).toBe('A');
    expect(revTags[1].textContent).toBe('B');
    expect(revTags[1].classList.contains('active')).toBe(true);

    // Third row: 30-00002
    const thirdPn = rows[2].querySelector('.pn-number').textContent;
    expect(thirdPn).toBe('30-00002');
  });

  it('displays the integer count of containing assemblies in Quantity column', () => {
    setViewMode('flat', false);
    const mockTree = [
      {
        id: 100,
        part_number: '55-00001',
        children: [
          { id: 1, part_number: '20-00001', children: [] },
          { id: 2, part_number: '10-00005', children: [] }
        ]
      },
      {
        id: 200,
        part_number: '55-00002',
        children: [
          { id: 1, part_number: '20-00001', children: [] }
        ]
      }
    ];

    updateParentCounts(mockTree);
    expect(getParentAssemblyCount(1)).toBe(2); // Part of assembly 100 and 200
    expect(getParentAssemblyCount(2)).toBe(1); // Part of assembly 100
    expect(getParentAssemblyCount(100)).toBe(0); // Top-level assembly

    allItems.push(
      { id: 1, "Part Number": "20-00001", "Revision": "A", "Item description": "Screw", State: "Production Use" },
      { id: 2, "Part Number": "10-00005", "Revision": "A", "Item description": "Sheet", State: "Production Use" },
      { id: 100, "Part Number": "55-00001", "Revision": "A", "Item description": "Top Assembly", State: "Production Use" }
    );

    renderFlatBomTable();

    const container = document.getElementById('tree-container');
    const rows = container.querySelectorAll('.tree-row');

    // Row 1 (10-00005) -> qty should be 1
    expect(rows[0].querySelector('.col-qty').textContent).toBe('1');
    // Row 2 (20-00001) -> qty should be 2
    expect(rows[1].querySelector('.col-qty').textContent).toBe('2');
    // Row 3 (55-00001) -> qty should be 0
    expect(rows[2].querySelector('.col-qty').textContent).toBe('0');
  });

  it('filters out non-matching categories and states completely (no grayed out rows in Flat BOM)', () => {
    setViewMode('flat', false);
    allItems.push(
      { id: 1, "Part Number": "10-00001", "Revision": "A", "Item description": "Raw Alu", State: "Production Use", pn_tag: { name: "Raw Material" } },
      { id: 2, "Part Number": "20-00001", "Revision": "A", "Item description": "Screw", State: "Production Use", pn_tag: { name: "Mechanical COTS" } },
      { id: 3, "Part Number": "30-00001", "Revision": "A", "Item description": "Bracket", State: "EOL", pn_tag: { name: "Mechanical Custom" } }
    );

    // Disable "Mechanical COTS"
    disabledCategories.add('Mechanical COTS');
    renderFlatBomTable();

    let container = document.getElementById('tree-container');
    let rows = container.querySelectorAll('.tree-row');
    expect(rows.length).toBe(2);
    expect(rows[0].querySelector('.pn-number').textContent).toBe('10-00001');
    expect(rows[1].querySelector('.pn-number').textContent).toBe('30-00001');
    // No rows should have .disabled-row class
    rows.forEach(r => expect(r.classList.contains('disabled-row')).toBe(false));

    // Disable EOL state
    disabledStates.add('EOL');
    renderFlatBomTable();

    rows = container.querySelectorAll('.tree-row');
    expect(rows.length).toBe(1);
    expect(rows[0].querySelector('.pn-number').textContent).toBe('10-00001');
  });

  it('search Enter switches to Flat BOM View and filters items without grayed out rows', async () => {
    const { init } = await import('../src/main.js');
    await init();

    setViewMode('nested', false);
    expect(getViewMode()).toBe('nested');

    const mockItems = [
      { id: 1, "Part Number": "10-00001", "Revision": "A", "Item description": "Power Cable", State: "Production Use" },
      { id: 2, "Part Number": "20-00002", "Revision": "A", "Item description": "Hex Nut M4", State: "Production Use" }
    ];
    api.fetchFlatItems.mockResolvedValue(mockItems);
    api.fetchBomTree.mockResolvedValue([]);

    const input = document.getElementById('search-input');
    input.value = 'hex nut';
    const event = new KeyboardEvent('keydown', { key: 'Enter' });
    input.dispatchEvent(event);

    // Search transitions view to Flat BOM
    expect(getViewMode()).toBe('flat');

    allItems.push(...mockItems);
    renderFlatBomTable();
    const container = document.getElementById('tree-container');
    const rows = container.querySelectorAll('.tree-row');
    expect(rows.length).toBe(1);
    expect(rows[0].querySelector('.pn-number').textContent).toBe('20-00002');
    expect(rows[0].classList.contains('disabled-row')).toBe(false);
  });

  it('clearing search query stays in Flat BOM View and displays all items', async () => {
    const { init } = await import('../src/main.js');
    await init();

    setViewMode('flat', false);

    allItems.push(
      { id: 1, "Part Number": "10-00001", "Revision": "A", "Item description": "Power Cable", State: "Production Use" },
      { id: 2, "Part Number": "20-00002", "Revision": "A", "Item description": "Hex Nut M4", State: "Production Use" }
    );

    // Enter empty query
    const input = document.getElementById('search-input');
    input.value = '';
    const event = new KeyboardEvent('keydown', { key: 'Enter' });
    input.dispatchEvent(event);

    // Stays in Flat BOM View
    expect(getViewMode()).toBe('flat');

    const container = document.getElementById('tree-container');
    const rows = container.querySelectorAll('.tree-row');
    expect(rows.length).toBe(2);
  });
});

