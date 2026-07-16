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
    fetchFlatItems: vi.fn().mockResolvedValue([]),
  };
});

import { sortTreeNodesRecursively, filterNode, disabledCategories, allItems } from '../src/main.js';

describe('BOM Sorting & Filtering Logic', () => {
  beforeEach(() => {
    disabledCategories.clear();
  });

  describe('sortTreeNodesRecursively', () => {
    it('sorts active first, disabled second, and then by category and part number', () => {
      const mockTree = [
        {
          id: 1,
          part_number: '20-00002',
          pn_tag: { name: 'Mechanical COTS' },
          isDisabledCategory: true,
          children: []
        },
        {
          id: 2,
          part_number: '10-00001',
          pn_tag: { name: 'Raw Material' },
          isDisabledCategory: false,
          children: []
        },
        {
          id: 3,
          part_number: '20-00001',
          pn_tag: { name: 'Mechanical COTS' },
          isDisabledCategory: false,
          children: []
        },
        {
          id: 4,
          part_number: '99-99999',
          pn_tag: null, // Should default to Unknown
          isDisabledCategory: true,
          children: []
        }
      ];

      const sorted = sortTreeNodesRecursively(mockTree);
      
      // Expected Order:
      // Active Group (sorted by Category, then PN):
      // 1. Mechanical COTS (20-00001) - id 3
      // 2. Raw Material (10-00001) - id 2
      // Disabled Group (sorted by Category, then PN):
      // 3. Mechanical COTS (20-00002) - id 1
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
});
