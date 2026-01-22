/**
 * Document store for state management.
 */

import { writable, derived } from 'svelte/store';
import type { Document, SearchResult, Tag, DashboardStats } from '$lib/api';

// Auth state
export const isAuthenticated = writable<boolean>(false);

// Documents state
export const documents = writable<Document[]>([]);
export const totalDocuments = writable<number>(0);
export const currentPage = writable<number>(1);
export const pageSize = writable<number>(20);

// Current document
export const currentDocument = writable<Document | null>(null);

// Search state
export const searchQuery = writable<string>('');
export const searchType = writable<'keyword' | 'semantic' | 'hybrid'>('hybrid');
export const searchResults = writable<SearchResult[]>([]);
export const isSearching = writable<boolean>(false);

// Filters
export const filterCategory = writable<string | null>(null);
export const filterStatus = writable<string | null>(null);
export const filterTag = writable<string | null>(null);
export const filterDateFrom = writable<string | null>(null);
export const filterDateTo = writable<string | null>(null);

// Tags
export const allTags = writable<Tag[]>([]);

// Stats
export const stats = writable<DashboardStats | null>(null);

// Loading states
export const isLoading = writable<boolean>(false);
export const isUploading = writable<boolean>(false);

// Error state
export const error = writable<string | null>(null);

// Derived stores
export const hasMorePages = derived(
	[totalDocuments, currentPage, pageSize],
	([$total, $page, $size]) => $total > $page * $size
);

export const documentCategories = derived(stats, ($stats) => {
	if (!$stats) return [];
	return Object.keys($stats.documents_by_category).filter((c) => c !== 'null' && c !== 'uncategorized');
});

// Helper to clear error after delay
export function clearErrorAfter(ms: number = 5000) {
	setTimeout(() => error.set(null), ms);
}

// Reset all filters
export function resetFilters() {
	filterCategory.set(null);
	filterStatus.set(null);
	filterTag.set(null);
	filterDateFrom.set(null);
	filterDateTo.set(null);
	searchQuery.set('');
	searchResults.set([]);
}
