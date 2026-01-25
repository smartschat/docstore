/**
 * Scanner store for document scanning state management
 */

import { writable, derived, get } from 'svelte/store';
import { revokeObjectURL, createObjectURL } from '$lib/services/camera';

// Maximum pages to prevent memory issues on mobile
export const MAX_PAGES = 20;

// Scanner states
export type ScannerState = 'idle' | 'camera' | 'preview' | 'review' | 'generating' | 'uploading';

// Page interface
export interface ScannedPage {
  id: string;
  blob: Blob;
  objectUrl: string;
}

// Scanner state stores
export const scannerState = writable<ScannerState>('idle');
export const pages = writable<ScannedPage[]>([]);
export const currentPreviewPage = writable<ScannedPage | null>(null);
export const generationProgress = writable<{ current: number; total: number }>({ current: 0, total: 0 });
export const scannerError = writable<string | null>(null);

// Derived stores
export const pageCount = derived(pages, ($pages) => $pages.length);
export const isAtPageLimit = derived(pages, ($pages) => $pages.length >= MAX_PAGES);
export const canAddMorePages = derived(pages, ($pages) => $pages.length < MAX_PAGES);

/**
 * Generate a unique ID for a page
 */
function generatePageId(): string {
  return `page-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Add a new page from a blob
 */
export function addPage(blob: Blob): ScannedPage | null {
  const currentPages = get(pages);

  if (currentPages.length >= MAX_PAGES) {
    scannerError.set(`Maximum of ${MAX_PAGES} pages reached`);
    return null;
  }

  const page: ScannedPage = {
    id: generatePageId(),
    blob,
    objectUrl: createObjectURL(blob),
  };

  pages.update((p) => [...p, page]);
  currentPreviewPage.set(page);

  return page;
}

/**
 * Remove a page by ID
 */
export function removePage(pageId: string): void {
  pages.update((currentPages) => {
    const pageToRemove = currentPages.find((p) => p.id === pageId);
    if (pageToRemove) {
      revokeObjectURL(pageToRemove.objectUrl);
    }
    return currentPages.filter((p) => p.id !== pageId);
  });
}

/**
 * Reorder pages - move page from one index to another
 */
export function reorderPages(fromIndex: number, toIndex: number): void {
  pages.update((currentPages) => {
    if (fromIndex < 0 || fromIndex >= currentPages.length) return currentPages;
    if (toIndex < 0 || toIndex >= currentPages.length) return currentPages;

    const newPages = [...currentPages];
    const [removed] = newPages.splice(fromIndex, 1);
    newPages.splice(toIndex, 0, removed);
    return newPages;
  });
}

/**
 * Move page up (decrease index)
 */
export function movePageUp(pageId: string): void {
  const currentPages = get(pages);
  const index = currentPages.findIndex((p) => p.id === pageId);
  if (index > 0) {
    reorderPages(index, index - 1);
  }
}

/**
 * Move page down (increase index)
 */
export function movePageDown(pageId: string): void {
  const currentPages = get(pages);
  const index = currentPages.findIndex((p) => p.id === pageId);
  if (index < currentPages.length - 1) {
    reorderPages(index, index + 1);
  }
}

/**
 * Remove the last page (for retake)
 */
export function removeLastPage(): void {
  pages.update((currentPages) => {
    if (currentPages.length === 0) return currentPages;

    const lastPage = currentPages[currentPages.length - 1];
    revokeObjectURL(lastPage.objectUrl);

    return currentPages.slice(0, -1);
  });
  currentPreviewPage.set(null);
}

/**
 * Clear all pages and revoke object URLs
 */
export function clearAllPages(): void {
  const currentPages = get(pages);
  currentPages.forEach((page) => {
    revokeObjectURL(page.objectUrl);
  });
  pages.set([]);
  currentPreviewPage.set(null);
}

/**
 * Get all page blobs in order
 */
export function getPageBlobs(): Blob[] {
  return get(pages).map((p) => p.blob);
}

/**
 * Reset scanner to initial state
 */
export function resetScanner(): void {
  clearAllPages();
  scannerState.set('idle');
  generationProgress.set({ current: 0, total: 0 });
  scannerError.set(null);
}

/**
 * Start scanner (open camera)
 */
export function openScanner(): void {
  scannerState.set('camera');
  scannerError.set(null);
}

/**
 * Go to preview state
 */
export function goToPreview(): void {
  scannerState.set('preview');
}

/**
 * Go to review state
 */
export function goToReview(): void {
  scannerState.set('review');
}

/**
 * Go back to camera from preview
 */
export function goToCamera(): void {
  scannerState.set('camera');
}

/**
 * Set generating state
 */
export function setGenerating(): void {
  scannerState.set('generating');
}

/**
 * Set uploading state
 */
export function setUploading(): void {
  scannerState.set('uploading');
}

/**
 * Update generation progress
 */
export function updateProgress(current: number, total: number): void {
  generationProgress.set({ current, total });
}

/**
 * Close scanner and cleanup
 */
export function closeScanner(): void {
  resetScanner();
}
