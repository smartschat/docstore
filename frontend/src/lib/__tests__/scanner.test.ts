import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';
import {
  scannerState,
  pages,
  currentPreviewPage,
  pageCount,
  isAtPageLimit,
  canAddMorePages,
  MAX_PAGES,
  addPage,
  removePage,
  reorderPages,
  movePageUp,
  movePageDown,
  removeLastPage,
  clearAllPages,
  getPageBlobs,
  resetScanner,
  openScanner,
  goToPreview,
  goToReview,
  goToCamera,
  setGenerating,
  setUploading,
  closeScanner
} from '$lib/stores/scanner';

// Mock URL.createObjectURL and URL.revokeObjectURL
const mockObjectUrls = new Map<string, Blob>();
let urlCounter = 0;

vi.stubGlobal('URL', {
  createObjectURL: (blob: Blob) => {
    const url = `blob:mock-${urlCounter++}`;
    mockObjectUrls.set(url, blob);
    return url;
  },
  revokeObjectURL: (url: string) => {
    mockObjectUrls.delete(url);
  }
});

// Helper to create mock blobs
function createMockBlob(content: string = 'test'): Blob {
  return new Blob([content], { type: 'image/jpeg' });
}

describe('Scanner Store', () => {
  beforeEach(() => {
    // Reset all stores before each test
    resetScanner();
    mockObjectUrls.clear();
    urlCounter = 0;
  });

  describe('State Transitions', () => {
    it('should start in idle state', () => {
      expect(get(scannerState)).toBe('idle');
    });

    it('should transition to camera state when opened', () => {
      openScanner();
      expect(get(scannerState)).toBe('camera');
    });

    it('should transition to preview state', () => {
      openScanner();
      goToPreview();
      expect(get(scannerState)).toBe('preview');
    });

    it('should transition to review state', () => {
      openScanner();
      goToReview();
      expect(get(scannerState)).toBe('review');
    });

    it('should transition back to camera from preview', () => {
      openScanner();
      goToPreview();
      goToCamera();
      expect(get(scannerState)).toBe('camera');
    });

    it('should transition to generating state', () => {
      setGenerating();
      expect(get(scannerState)).toBe('generating');
    });

    it('should transition to uploading state', () => {
      setUploading();
      expect(get(scannerState)).toBe('uploading');
    });

    it('should reset to idle when closed', () => {
      openScanner();
      goToPreview();
      closeScanner();
      expect(get(scannerState)).toBe('idle');
    });
  });

  describe('Page Operations', () => {
    it('should add a page', () => {
      const blob = createMockBlob();
      const page = addPage(blob);

      expect(page).not.toBeNull();
      expect(get(pages)).toHaveLength(1);
      expect(get(pageCount)).toBe(1);
    });

    it('should set current preview page when adding', () => {
      const blob = createMockBlob();
      const page = addPage(blob);

      expect(get(currentPreviewPage)).toBe(page);
    });

    it('should create object URL for page', () => {
      const blob = createMockBlob();
      const page = addPage(blob);

      expect(page?.objectUrl).toMatch(/^blob:mock-\d+$/);
    });

    it('should remove a page by ID', () => {
      const blob1 = createMockBlob('page1');
      const blob2 = createMockBlob('page2');
      const page1 = addPage(blob1);
      addPage(blob2);

      expect(get(pages)).toHaveLength(2);

      removePage(page1!.id);

      expect(get(pages)).toHaveLength(1);
      expect(get(pages)[0].blob).toBe(blob2);
    });

    it('should revoke object URL when removing page', () => {
      const blob = createMockBlob();
      const page = addPage(blob);
      const url = page!.objectUrl;

      expect(mockObjectUrls.has(url)).toBe(true);

      removePage(page!.id);

      expect(mockObjectUrls.has(url)).toBe(false);
    });

    it('should remove the last page', () => {
      addPage(createMockBlob('page1'));
      addPage(createMockBlob('page2'));
      addPage(createMockBlob('page3'));

      expect(get(pages)).toHaveLength(3);

      removeLastPage();

      expect(get(pages)).toHaveLength(2);
      expect(get(currentPreviewPage)).toBeNull();
    });

    it('should clear all pages', () => {
      addPage(createMockBlob('page1'));
      addPage(createMockBlob('page2'));
      addPage(createMockBlob('page3'));

      const urlCount = mockObjectUrls.size;
      expect(urlCount).toBe(3);

      clearAllPages();

      expect(get(pages)).toHaveLength(0);
      expect(mockObjectUrls.size).toBe(0);
    });

    it('should return page blobs in order', () => {
      const blob1 = createMockBlob('page1');
      const blob2 = createMockBlob('page2');
      const blob3 = createMockBlob('page3');

      addPage(blob1);
      addPage(blob2);
      addPage(blob3);

      const blobs = getPageBlobs();

      expect(blobs).toHaveLength(3);
      expect(blobs[0]).toBe(blob1);
      expect(blobs[1]).toBe(blob2);
      expect(blobs[2]).toBe(blob3);
    });
  });

  describe('Page Reordering', () => {
    it('should reorder pages', () => {
      const blob1 = createMockBlob('page1');
      const blob2 = createMockBlob('page2');
      const blob3 = createMockBlob('page3');

      addPage(blob1);
      addPage(blob2);
      addPage(blob3);

      reorderPages(0, 2);

      const blobs = getPageBlobs();
      expect(blobs[0]).toBe(blob2);
      expect(blobs[1]).toBe(blob3);
      expect(blobs[2]).toBe(blob1);
    });

    it('should move page up', () => {
      const blob1 = createMockBlob('page1');
      const blob2 = createMockBlob('page2');

      addPage(blob1);
      const page2 = addPage(blob2);

      movePageUp(page2!.id);

      const blobs = getPageBlobs();
      expect(blobs[0]).toBe(blob2);
      expect(blobs[1]).toBe(blob1);
    });

    it('should not move first page up', () => {
      const blob1 = createMockBlob('page1');
      const blob2 = createMockBlob('page2');

      const page1 = addPage(blob1);
      addPage(blob2);

      movePageUp(page1!.id);

      const blobs = getPageBlobs();
      expect(blobs[0]).toBe(blob1);
      expect(blobs[1]).toBe(blob2);
    });

    it('should move page down', () => {
      const blob1 = createMockBlob('page1');
      const blob2 = createMockBlob('page2');

      const page1 = addPage(blob1);
      addPage(blob2);

      movePageDown(page1!.id);

      const blobs = getPageBlobs();
      expect(blobs[0]).toBe(blob2);
      expect(blobs[1]).toBe(blob1);
    });

    it('should not move last page down', () => {
      const blob1 = createMockBlob('page1');
      const blob2 = createMockBlob('page2');

      addPage(blob1);
      const page2 = addPage(blob2);

      movePageDown(page2!.id);

      const blobs = getPageBlobs();
      expect(blobs[0]).toBe(blob1);
      expect(blobs[1]).toBe(blob2);
    });

    it('should handle invalid reorder indices', () => {
      addPage(createMockBlob('page1'));
      addPage(createMockBlob('page2'));

      const pagesBefore = get(pages).map(p => p.id);

      // Invalid from index
      reorderPages(-1, 1);
      expect(get(pages).map(p => p.id)).toEqual(pagesBefore);

      // Invalid to index
      reorderPages(0, 5);
      expect(get(pages).map(p => p.id)).toEqual(pagesBefore);
    });
  });

  describe('Page Limit', () => {
    it('should enforce maximum page limit', () => {
      for (let i = 0; i < MAX_PAGES; i++) {
        addPage(createMockBlob(`page${i}`));
      }

      expect(get(pages)).toHaveLength(MAX_PAGES);
      expect(get(isAtPageLimit)).toBe(true);
      expect(get(canAddMorePages)).toBe(false);

      // Try to add one more
      const result = addPage(createMockBlob('overflow'));
      expect(result).toBeNull();
      expect(get(pages)).toHaveLength(MAX_PAGES);
    });

    it('should allow adding after removing when at limit', () => {
      for (let i = 0; i < MAX_PAGES; i++) {
        addPage(createMockBlob(`page${i}`));
      }

      const firstPage = get(pages)[0];
      removePage(firstPage.id);

      expect(get(isAtPageLimit)).toBe(false);
      expect(get(canAddMorePages)).toBe(true);

      const result = addPage(createMockBlob('new page'));
      expect(result).not.toBeNull();
      expect(get(pages)).toHaveLength(MAX_PAGES);
    });
  });

  describe('Object URL Cleanup', () => {
    it('should clean up object URLs on page delete', () => {
      const blob = createMockBlob();
      const page = addPage(blob);
      const url = page!.objectUrl;

      expect(mockObjectUrls.has(url)).toBe(true);

      removePage(page!.id);

      expect(mockObjectUrls.has(url)).toBe(false);
    });

    it('should clean up all object URLs on reset', () => {
      addPage(createMockBlob('page1'));
      addPage(createMockBlob('page2'));
      addPage(createMockBlob('page3'));

      expect(mockObjectUrls.size).toBe(3);

      resetScanner();

      expect(mockObjectUrls.size).toBe(0);
    });

    it('should clean up object URLs on close', () => {
      openScanner();
      addPage(createMockBlob('page1'));
      addPage(createMockBlob('page2'));

      expect(mockObjectUrls.size).toBe(2);

      closeScanner();

      expect(mockObjectUrls.size).toBe(0);
    });
  });
});
