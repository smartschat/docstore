/**
 * API client for DocStore backend.
 */

const API_BASE = '/api';

export interface Document {
	id: string;
	filename: string;
	file_path: string;
	file_hash: string;
	file_size: number | null;
	mime_type: string | null;
	raw_text: string | null;
	page_count: number | null;
	summary: string | null;
	document_date: string | null;
	created_at: string;
	processed_at: string | null;
	status: 'pending' | 'processing' | 'completed' | 'failed';
	extraction_status: 'pending' | 'completed' | null;
	// Extracted fields
	title: string | null;
	counterparty: string | null;
	affected_person: string | null;
	category: string | null;
	reference: string | null;
	tags: Tag[];
}

export interface Tag {
	id: number;
	name: string;
}

export interface DocumentList {
	items: Document[];
	total: number;
	page: number;
	page_size: number;
}

export interface SearchResult {
	document: Document;
	score: number;
	snippet: string | null;
}

export interface SearchResponse {
	results: SearchResult[];
	total: number;
	query: string;
}

export interface QuestionResponse {
	answer: string;
	sources: Document[];
}

export interface DashboardStats {
	total_documents: number;
	documents_by_category: Record<string, number>;
	documents_by_status: Record<string, number>;
	recent_documents: Document[];
}


class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

async function request<T>(
	endpoint: string,
	options: RequestInit = {}
): Promise<T> {
	const response = await fetch(`${API_BASE}${endpoint}`, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...options.headers
		},
		credentials: 'include'
	});

	if (!response.ok) {
		if (response.status === 401) {
			// Redirect to login
			window.location.href = '/login';
			throw new ApiError(401, 'Unauthorized');
		}
		const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
		throw new ApiError(response.status, error.detail || 'Request failed');
	}

	// Handle empty responses
	const text = await response.text();
	if (!text) {
		return {} as T;
	}

	return JSON.parse(text);
}

// Auth
export async function login(password: string): Promise<{ success: boolean; message: string }> {
	return request('/auth/login', {
		method: 'POST',
		body: JSON.stringify({ password })
	});
}

export async function logout(): Promise<void> {
	await request('/auth/logout', { method: 'POST' });
}

export async function checkAuth(): Promise<{ authenticated: boolean }> {
	try {
		return await request('/auth/check');
	} catch {
		return { authenticated: false };
	}
}

// Documents
export async function listDocuments(params: {
	page?: number;
	page_size?: number;
	category?: string;
	affected_person?: string;
	status?: string;
	tag?: string;
} = {}): Promise<DocumentList> {
	const searchParams = new URLSearchParams();
	if (params.page) searchParams.set('page', params.page.toString());
	if (params.page_size) searchParams.set('page_size', params.page_size.toString());
	if (params.category) searchParams.set('category', params.category);
	if (params.affected_person) searchParams.set('affected_person', params.affected_person);
	if (params.status) searchParams.set('status', params.status);
	if (params.tag) searchParams.set('tag', params.tag);

	const query = searchParams.toString();
	return request(`/documents${query ? `?${query}` : ''}`);
}

export async function getDocument(id: string): Promise<Document> {
	return request(`/documents/${id}`);
}

export async function uploadDocument(file: File): Promise<Document> {
	const formData = new FormData();
	formData.append('file', file);

	const response = await fetch(`${API_BASE}/documents/upload`, {
		method: 'POST',
		body: formData,
		credentials: 'include'
	});

	if (!response.ok) {
		if (response.status === 401) {
			window.location.href = '/login';
			throw new ApiError(401, 'Unauthorized');
		}
		const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
		throw new ApiError(response.status, error.detail || 'Upload failed');
	}

	return response.json();
}

export async function updateDocument(
	id: string,
	data: {
		title?: string;
		counterparty?: string;
		affected_person?: string;
		category?: string;
		reference?: string;
		document_date?: string;
		summary?: string;
	}
): Promise<Document> {
	return request(`/documents/${id}`, {
		method: 'PATCH',
		body: JSON.stringify(data)
	});
}

export async function deleteDocument(id: string): Promise<void> {
	await request(`/documents/${id}`, { method: 'DELETE' });
}

export function getDocumentFileUrl(id: string): string {
	return `${API_BASE}/documents/${id}/file`;
}

export function getDocumentThumbnailUrl(id: string): string {
	return `${API_BASE}/documents/${id}/thumbnail`;
}

export async function addTags(docId: string, tags: string[]): Promise<void> {
	await request(`/documents/${docId}/tags`, {
		method: 'POST',
		body: JSON.stringify(tags)
	});
}

export async function removeTag(docId: string, tagName: string): Promise<void> {
	await request(`/documents/${docId}/tags/${encodeURIComponent(tagName)}`, {
		method: 'DELETE'
	});
}

// Search
export async function search(params: {
	query: string;
	search_type?: 'keyword' | 'semantic' | 'hybrid';
	category?: string;
	affected_person?: string;
	tags?: string[];
	date_from?: string;
	date_to?: string;
	page?: number;
	page_size?: number;
}): Promise<SearchResponse> {
	return request('/search', {
		method: 'POST',
		body: JSON.stringify({
			query: params.query,
			search_type: params.search_type || 'hybrid',
			category: params.category,
			affected_person: params.affected_person,
			tags: params.tags,
			date_from: params.date_from,
			date_to: params.date_to,
			page: params.page || 1,
			page_size: params.page_size || 20
		})
	});
}

export async function getSearchSuggestions(query: string): Promise<{
	filenames: string[];
	tags: string[];
	counterparties: string[];
}> {
	return request(`/search/suggest?q=${encodeURIComponent(query)}`);
}

// Q&A
export async function askQuestion(
	question: string,
	docIds?: string[]
): Promise<QuestionResponse> {
	return request('/ask', {
		method: 'POST',
		body: JSON.stringify({
			question,
			doc_ids: docIds
		})
	});
}

// Tags
export async function listTags(): Promise<Tag[]> {
	return request('/tags');
}

// Stats
export async function getStats(): Promise<DashboardStats> {
	return request('/stats');
}

export interface QueueStats {
	pending: number;
	completed: number;
	no_status: number;
	ollama_available: boolean;
	queue_running: boolean;
}

export async function getQueueStats(): Promise<QueueStats> {
	return request('/queue/stats');
}

// System
export async function healthCheck(): Promise<{ status: string; version: string }> {
	return request('/health');
}

export async function reprocessDocument(docId: string): Promise<{ message: string }> {
	return request(`/reprocess/${docId}`, { method: 'POST' });
}
