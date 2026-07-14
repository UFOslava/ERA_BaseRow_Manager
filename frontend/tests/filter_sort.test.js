import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the API calls made when main.js is loaded/run
vi.mock('../src/api.js', () => {
  return {
    fetchBomTree: vi.fn(),
    fetchItem: vi.fn(),
    updateItem: vi.fn(),
    fetchScanStatus: vi.fn(),
    getHealth: vi.fn(),
    fetchRules: vi.fn(),
  };
});

import { sortTreeNodesRecursively, filterNode, disabledCategories } from '../src/main.js';

describe('BOM Sorting & Filtering Logic', () => {
  beforeEach(() => {
    disabledCategories.clear();
  });

  describe('sortTreeNodesRecursively', () => {
    it('sorts nodes by category name first, and then by part number', () => {
      const mockTree = [
        {
          id: 1,
          part_number: '20-00002',
          pn_tag: { name: 'Mechanical COTS' },
          children: []
        },
        {
          id: 2,
          part_number: '10-00001',
          pn_tag: { name: 'Raw Material' },
          children: []
        },
        {
          id: 3,
          part_number: '20-00001',
          pn_tag: { name: 'Mechanical COTS' },
          children: []
        },
        {
          id: 4,
          part_number: '99-99999',
          pn_tag: null, // Should default to Unknown
          children: []
        }
      ];

      const sorted = sortTreeNodesRecursively(mockTree);
      
      // Expected Order:
      // 1. Mechanical COTS (20-00001) - id 3
      // 2. Mechanical COTS (20-00002) - id 1
      // 3. Raw Material (10-00001) - id 2
      // 4. Unknown (99-99999) - id 4
      
      expect(sorted[0].id).toBe(3);
      expect(sorted[1].id).toBe(1);
      expect(sorted[2].id).toBe(2);
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

  describe('filterNode category filtering', () => {
    it('filters out nodes of disabled categories', () => {
      const node = {
        id: 1,
        part_number: '30-00001',
        pn_tag: { name: 'Mechanical Custom' },
        children: []
      };

      // Initially enabled
      expect(filterNode(node, '', '1', [])).not.toBeNull();

      // Disable category
      disabledCategories.add('Mechanical Custom');
      expect(filterNode(node, '', '1', [])).toBeNull();
    });

    it('filters out child nodes of disabled categories', () => {
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
      expect(filtered.children.length).toBe(0);
    });
  });
});
