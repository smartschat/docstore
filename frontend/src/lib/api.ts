/**
 * API client for DocStore backend.
 */

const API_BASE = '/api';

export interface LinkedPerson {
	id: string;
	canonical_name: string;
	role: string;
}

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
	// Entity disambiguation
	counterparty_id: string | null;
	counterparty_disambiguation: 'pending' | 'auto_matched' | 'confirmed' | 'unmatched' | null;
	persons_disambiguation: 'pending' | 'auto_matched' | 'confirmed' | 'unmatched' | null;
	// Resolved entity names
	counterparty_name: string | null;
	linked_persons: LinkedPerson[];
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

export interface EntityCount {
	id: string;
	name: string;
	count: number;
}

export interface DashboardStats {
	total_documents: number;
	documents_by_category: Record<string, number>;
	documents_by_status: Record<string, number>;
	recent_documents: Document[];
	top_counterparties: EntityCount[];
	top_persons: EntityCount[];
	pending_reviews: number;
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
	counterparty_id?: string;
	person_id?: string;
} = {}): Promise<DocumentList> {
	const searchParams = new URLSearchParams();
	if (params.page) searchParams.set('page', params.page.toString());
	if (params.page_size) searchParams.set('page_size', params.page_size.toString());
	if (params.category) searchParams.set('category', params.category);
	if (params.affected_person) searchParams.set('affected_person', params.affected_person);
	if (params.status) searchParams.set('status', params.status);
	if (params.tag) searchParams.set('tag', params.tag);
	if (params.counterparty_id) searchParams.set('counterparty_id', params.counterparty_id);
	if (params.person_id) searchParams.set('person_id', params.person_id);

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
		counterparty_id?: string | null;
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

// ============== Entity Types ==============

export interface Alias {
	id: number;
	alias: string;
	source: 'manual' | 'llm_extracted' | 'merged';
	created_at: string;
}

export interface Counterparty {
	id: string;
	canonical_name: string;
	short_name: string | null;
	notes: string | null;
	aliases: Alias[];
	created_at: string;
	updated_at: string;
}

export interface CounterpartyList {
	items: Counterparty[];
	total: number;
}

export interface Person {
	id: string;
	canonical_name: string;
	first_name: string | null;
	last_name: string | null;
	notes: string | null;
	aliases: Alias[];
	created_at: string;
	updated_at: string;
}

export interface PersonList {
	items: Person[];
	total: number;
}

export interface DocumentPerson {
	person: Person;
	role: string;
}

export interface DisambiguationCandidate {
	entity_id: string;
	entity_name: string;
	score: number;
	matched_alias: string | null;
}

export interface DocumentDisambiguation {
	document_id: string;
	filename: string;
	title: string | null;
	counterparty_raw: string | null;
	counterparty_candidates: DisambiguationCandidate[];
	affected_person_raw: string | null;
	person_candidates: DisambiguationCandidate[];
}

// ============== Counterparty API ==============

export async function listCounterparties(search?: string): Promise<CounterpartyList> {
	const params = search ? `?search=${encodeURIComponent(search)}` : '';
	return request(`/entities/counterparties${params}`);
}

export async function getCounterparty(id: string): Promise<Counterparty> {
	return request(`/entities/counterparties/${id}`);
}

export async function createCounterparty(data: {
	canonical_name: string;
	short_name?: string;
	notes?: string;
	aliases?: string[];
}): Promise<Counterparty> {
	return request('/entities/counterparties', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function updateCounterparty(
	id: string,
	data: {
		canonical_name?: string;
		short_name?: string;
		notes?: string;
	}
): Promise<Counterparty> {
	return request(`/entities/counterparties/${id}`, {
		method: 'PATCH',
		body: JSON.stringify(data)
	});
}

export async function deleteCounterparty(id: string): Promise<void> {
	await request(`/entities/counterparties/${id}`, { method: 'DELETE' });
}

export async function addCounterpartyAlias(
	entityId: string,
	alias: string
): Promise<void> {
	await request(`/entities/counterparties/${entityId}/aliases?alias=${encodeURIComponent(alias)}`, {
		method: 'POST'
	});
}

export async function removeCounterpartyAlias(
	entityId: string,
	aliasId: number
): Promise<void> {
	await request(`/entities/counterparties/${entityId}/aliases/${aliasId}`, {
		method: 'DELETE'
	});
}

export async function mergeCounterparties(keepId: string, mergeId: string): Promise<Counterparty> {
	return request('/entities/counterparties/merge', {
		method: 'POST',
		body: JSON.stringify({ keep_id: keepId, merge_id: mergeId })
	});
}

// ============== Person API ==============

export async function listPersons(search?: string): Promise<PersonList> {
	const params = search ? `?search=${encodeURIComponent(search)}` : '';
	return request(`/entities/persons${params}`);
}

export async function getPerson(id: string): Promise<Person> {
	return request(`/entities/persons/${id}`);
}

export async function createPerson(data: {
	canonical_name: string;
	first_name?: string;
	last_name?: string;
	notes?: string;
	aliases?: string[];
}): Promise<Person> {
	return request('/entities/persons', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function updatePerson(
	id: string,
	data: {
		canonical_name?: string;
		first_name?: string;
		last_name?: string;
		notes?: string;
	}
): Promise<Person> {
	return request(`/entities/persons/${id}`, {
		method: 'PATCH',
		body: JSON.stringify(data)
	});
}

export async function deletePerson(id: string): Promise<void> {
	await request(`/entities/persons/${id}`, { method: 'DELETE' });
}

export async function addPersonAlias(entityId: string, alias: string): Promise<void> {
	await request(`/entities/persons/${entityId}/aliases?alias=${encodeURIComponent(alias)}`, {
		method: 'POST'
	});
}

export async function removePersonAlias(entityId: string, aliasId: number): Promise<void> {
	await request(`/entities/persons/${entityId}/aliases/${aliasId}`, {
		method: 'DELETE'
	});
}

export async function mergePersons(keepId: string, mergeId: string): Promise<Person> {
	return request('/entities/persons/merge', {
		method: 'POST',
		body: JSON.stringify({ keep_id: keepId, merge_id: mergeId })
	});
}

// ============== Document Persons API ==============

export async function getDocumentPersons(docId: string): Promise<DocumentPerson[]> {
	return request(`/documents/${docId}/persons`);
}

export async function addDocumentPerson(
	docId: string,
	personId: string,
	role: string = 'affected'
): Promise<void> {
	await request(`/documents/${docId}/persons`, {
		method: 'POST',
		body: JSON.stringify({ person_id: personId, role })
	});
}

export async function removeDocumentPerson(docId: string, personId: string): Promise<void> {
	await request(`/documents/${docId}/persons/${personId}`, { method: 'DELETE' });
}

// ============== Disambiguation API ==============

export async function getPendingDisambiguations(): Promise<DocumentDisambiguation[]> {
	return request('/entities/disambiguation/pending');
}

export async function resolveDisambiguation(
	docId: string,
	entityType: 'counterparty' | 'person',
	entityId: string | null,
	addAlias: boolean = true
): Promise<void> {
	await request(`/entities/disambiguation/${docId}/resolve`, {
		method: 'POST',
		body: JSON.stringify({
			entity_type: entityType,
			entity_id: entityId,
			add_alias: addAlias
		})
	});
}
