<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import {
		getDocument,
		deleteDocument,
		updateDocument,
		addTags,
		removeTag,
		reprocessDocument,
		getDocumentFileUrl,
		getDocumentPersons,
		addDocumentPerson,
		removeDocumentPerson,
		getCounterparty,
		createCounterparty,
		createPerson,
		type Document,
		type DocumentPerson,
		type Counterparty
	} from '$lib/api';
	import PdfViewer from '$components/PdfViewer.svelte';
	import TagEditor from '$components/TagEditor.svelte';
	import EntityPicker from '$components/EntityPicker.svelte';

	let document: Document | null = null;
	let documentPersons: DocumentPerson[] = [];
	let counterpartyEntity: Counterparty | null = null;
	let loading = true;
	let deleting = false;
	let reprocessing = false;
	let saving = false;
	let error = '';

	let showDeleteConfirm = false;
	let showRawText = false;
	let editMode = false;
	let showAddPerson = false;

	const CATEGORIES = [
		'utilities',
		'insurance',
		'tax',
		'medical',
		'banking',
		'salary',
		'contract',
		'legal',
		'correspondence',
		'receipt',
		'invoice',
		'other'
	];

	let editData = {
		title: '',
		summary: '',
		counterparty: '',
		affected_person: '',
		reference: '',
		category: '',
		document_date: ''
	};

	$: docId = $page.params.id as string;

	onMount(async () => {
		await loadDocument();
	});

	async function loadDocument() {
		loading = true;
		try {
			document = await getDocument(docId);

			// Load linked persons
			documentPersons = await getDocumentPersons(docId);

			// Load counterparty entity if linked
			if (document.counterparty_id) {
				try {
					counterpartyEntity = await getCounterparty(document.counterparty_id);
				} catch {
					counterpartyEntity = null;
				}
			} else {
				counterpartyEntity = null;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load document';
		} finally {
			loading = false;
		}
	}

	async function handleDelete() {
		deleting = true;
		try {
			await deleteDocument(docId);
			goto('/documents');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete document';
		} finally {
			deleting = false;
			showDeleteConfirm = false;
		}
	}

	async function handleReprocess() {
		reprocessing = true;
		try {
			await reprocessDocument(docId);
			await loadDocument();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to reprocess document';
		} finally {
			reprocessing = false;
		}
	}

	async function handleAddTag(event: CustomEvent<string>) {
		const tagName = event.detail;
		try {
			await addTags(docId, [tagName]);
			await loadDocument();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to add tag';
		}
	}

	async function handleRemoveTag(event: CustomEvent<string>) {
		const tagName = event.detail;
		try {
			await removeTag(docId, tagName);
			await loadDocument();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to remove tag';
		}
	}

	function startEdit() {
		if (!document) return;
		editData = {
			title: document.title || '',
			summary: document.summary || '',
			counterparty: document.counterparty || '',
			affected_person: document.affected_person || '',
			reference: document.reference || '',
			category: document.category || '',
			document_date: document.document_date || ''
		};
		editMode = true;
	}

	function cancelEdit() {
		editMode = false;
		error = '';
	}

	async function handleSave() {
		saving = true;
		error = '';
		try {
			const updateData: Record<string, unknown> = {};

			if (editData.title !== (document?.title || '')) updateData.title = editData.title || null;
			if (editData.summary !== (document?.summary || ''))
				updateData.summary = editData.summary || null;
			if (editData.counterparty !== (document?.counterparty || ''))
				updateData.counterparty = editData.counterparty || null;
			if (editData.affected_person !== (document?.affected_person || ''))
				updateData.affected_person = editData.affected_person || null;
			if (editData.reference !== (document?.reference || ''))
				updateData.reference = editData.reference || null;
			if (editData.category !== (document?.category || ''))
				updateData.category = editData.category || null;
			if (editData.document_date !== (document?.document_date || ''))
				updateData.document_date = editData.document_date || null;

			if (Object.keys(updateData).length > 0) {
				await updateDocument(docId, updateData);
				await loadDocument();
			}
			editMode = false;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save changes';
		} finally {
			saving = false;
		}
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '-';
		return new Date(dateStr).toLocaleDateString('de-DE', {
			year: 'numeric',
			month: 'long',
			day: 'numeric'
		});
	}

	function formatFileSize(bytes: number | null): string {
		if (!bytes) return '-';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function getStatusClass(status: string): string {
		return `status-${status}`;
	}

	function getCategoryClass(category: string | null): string {
		return category ? `badge-${category}` : 'badge-other';
	}

	async function handleCounterpartySelect(
		event: CustomEvent<{ id: string; name: string } | null>
	) {
		const selection = event.detail;
		try {
			if (selection) {
				await updateDocument(docId, { counterparty_id: selection.id });
			} else {
				await updateDocument(docId, { counterparty_id: null });
			}
			await loadDocument();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to update counterparty';
		}
	}

	async function handleCreateCounterparty(event: CustomEvent<string>) {
		const name = event.detail;
		try {
			const newEntity = await createCounterparty({ canonical_name: name });
			await updateDocument(docId, { counterparty_id: newEntity.id });
			await loadDocument();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create counterparty';
		}
	}

	async function handlePersonSelect(event: CustomEvent<{ id: string; name: string } | null>) {
		const selection = event.detail;
		if (selection) {
			try {
				await addDocumentPerson(docId, selection.id, 'affected');
				await loadDocument();
				showAddPerson = false;
			} catch (e) {
				error = e instanceof Error ? e.message : 'Failed to add person';
			}
		}
	}

	async function handleCreatePerson(event: CustomEvent<string>) {
		const name = event.detail;
		try {
			const newEntity = await createPerson({ canonical_name: name });
			await addDocumentPerson(docId, newEntity.id, 'affected');
			await loadDocument();
			showAddPerson = false;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create person';
		}
	}

	async function handleRemovePerson(personId: string) {
		try {
			await removeDocumentPerson(docId, personId);
			await loadDocument();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to remove person';
		}
	}
</script>

<svelte:head>
	<title>{document?.title || document?.filename || 'Document'} - DocStore</title>
</svelte:head>

{#if loading}
	<div class="flex justify-center py-12">
		<div class="spinner"></div>
	</div>
{:else if error && !document}
	<div class="text-center py-12">
		<p class="text-red-600">{error}</p>
		<a href="/documents" class="mt-4 inline-block text-primary-600 hover:text-primary-700">
			Back to documents
		</a>
	</div>
{:else if document}
	<div class="space-y-6">
		<!-- Header -->
		<div class="flex items-start justify-between">
			<div>
				<a href="/documents" class="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
					</svg>
					Back to documents
				</a>
				<h1 class="mt-2 text-2xl font-bold text-slate-900">{document.title || document.filename}</h1>
				{#if document.title}
					<p class="text-sm text-slate-500">{document.filename}</p>
				{/if}
				<div class="mt-2 flex items-center gap-2">
					{#if document.category}
						<span class="badge {getCategoryClass(document.category)}">
							{document.category}
						</span>
					{/if}
					<span class="badge {getStatusClass(document.status)}">
						{document.status}
					</span>
				</div>
			</div>

			<div class="flex items-center gap-2">
				<a
					href={getDocumentFileUrl(docId)}
					download={document.filename}
					class="px-3 py-2 text-sm border border-slate-300 rounded-lg hover:bg-slate-50"
				>
					Download
				</a>
				<button
					on:click={handleReprocess}
					disabled={reprocessing}
					class="px-3 py-2 text-sm border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50"
				>
					{reprocessing ? 'Reprocessing...' : 'Reprocess'}
				</button>
				<button
					on:click={() => (showDeleteConfirm = true)}
					class="px-3 py-2 text-sm text-red-600 border border-red-300 rounded-lg hover:bg-red-50"
				>
					Delete
				</button>
			</div>
		</div>

		{#if error}
			<div class="p-4 bg-red-50 text-red-700 rounded-lg">{error}</div>
		{/if}

		<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
			<!-- PDF Viewer -->
			<div class="lg:col-span-2">
				<div class="bg-white rounded-xl shadow-sm overflow-hidden h-[calc(100vh-12rem)]">
					<PdfViewer url={getDocumentFileUrl(docId)} mimeType={document.mime_type} />
				</div>
			</div>

			<!-- Sidebar -->
			<div class="space-y-6">
				<!-- Document Info -->
				<div class="bg-white rounded-xl shadow-sm p-6">
					<div class="flex items-center justify-between mb-4">
						<h2 class="text-lg font-semibold text-slate-900">Details</h2>
						{#if editMode}
							<div class="flex gap-2">
								<button
									on:click={cancelEdit}
									disabled={saving}
									class="px-3 py-1 text-sm text-slate-600 hover:text-slate-800"
								>
									Cancel
								</button>
								<button
									on:click={handleSave}
									disabled={saving}
									class="px-3 py-1 text-sm text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
								>
									{saving ? 'Saving...' : 'Save'}
								</button>
							</div>
						{:else}
							<button
								on:click={startEdit}
								class="px-3 py-1 text-sm text-primary-600 hover:text-primary-700"
							>
								Edit
							</button>
						{/if}
					</div>

					{#if editMode}
						<!-- Edit Mode -->
						<div class="space-y-4">
							<div>
								<label for="edit-title" class="block text-sm font-medium text-slate-500">Title</label>
								<input
									id="edit-title"
									type="text"
									bind:value={editData.title}
									class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
								/>
							</div>

							<div>
								<label for="edit-summary" class="block text-sm font-medium text-slate-500">Summary</label>
								<textarea
									id="edit-summary"
									bind:value={editData.summary}
									rows="3"
									class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
								></textarea>
							</div>

							<div>
								<label class="block text-sm font-medium text-slate-500 mb-1">Counterparty</label>
								<EntityPicker
									entityType="counterparty"
									value={document?.counterparty_id || null}
									selectedName={counterpartyEntity?.canonical_name || null}
									placeholder="Search counterparties..."
									on:select={handleCounterpartySelect}
									on:create={handleCreateCounterparty}
								/>
								{#if document?.counterparty && !document?.counterparty_id}
									<p class="mt-1 text-xs text-slate-400">
										Extracted: {document.counterparty}
									</p>
								{/if}
							</div>

							<div>
								<label class="block text-sm font-medium text-slate-500 mb-1">Persons</label>
								{#if documentPersons.length > 0}
									<div class="space-y-1 mb-2">
										{#each documentPersons as dp}
											<div class="flex items-center justify-between px-2 py-1 bg-slate-50 rounded">
												<span class="text-sm">{dp.person.canonical_name}</span>
												<button
													type="button"
													on:click={() => handleRemovePerson(dp.person.id)}
													class="p-1 text-slate-400 hover:text-red-600"
												>
													<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
													</svg>
												</button>
											</div>
										{/each}
									</div>
								{/if}
								{#if showAddPerson}
									<EntityPicker
										entityType="person"
										placeholder="Search persons..."
										on:select={handlePersonSelect}
										on:create={handleCreatePerson}
									/>
									<button
										type="button"
										on:click={() => (showAddPerson = false)}
										class="mt-1 text-xs text-slate-500 hover:text-slate-700"
									>
										Cancel
									</button>
								{:else}
									<button
										type="button"
										on:click={() => (showAddPerson = true)}
										class="flex items-center gap-1 text-sm text-primary-600 hover:text-primary-700"
									>
										<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
										</svg>
										Add person
									</button>
								{/if}
								{#if document?.affected_person && documentPersons.length === 0}
									<p class="mt-1 text-xs text-slate-400">
										Extracted: {document.affected_person}
									</p>
								{/if}
							</div>

							<div>
								<label for="edit-reference" class="block text-sm font-medium text-slate-500">Reference</label>
								<input
									id="edit-reference"
									type="text"
									bind:value={editData.reference}
									class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono focus:border-primary-500 focus:ring-primary-500"
								/>
							</div>

							<div>
								<label for="edit-category" class="block text-sm font-medium text-slate-500">Category</label>
								<select
									id="edit-category"
									bind:value={editData.category}
									class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
								>
									<option value="">None</option>
									{#each CATEGORIES as cat}
										<option value={cat}>{cat}</option>
									{/each}
								</select>
							</div>

							<div>
								<label for="edit-document-date" class="block text-sm font-medium text-slate-500">Document Date</label>
								<input
									id="edit-document-date"
									type="date"
									bind:value={editData.document_date}
									class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
								/>
							</div>
						</div>
					{:else}
						<!-- View Mode -->
						<dl class="space-y-3">
							{#if document.summary}
								<div>
									<dt class="text-sm font-medium text-slate-500">Summary</dt>
									<dd class="mt-1 text-sm text-slate-900">{document.summary}</dd>
								</div>
							{/if}

							<div>
								<dt class="text-sm font-medium text-slate-500">Counterparty</dt>
								<dd class="mt-1 text-sm text-slate-900">
									{#if counterpartyEntity}
										<span class="inline-flex items-center gap-1 px-2 py-1 bg-primary-50 text-primary-700 rounded text-sm">
											{counterpartyEntity.canonical_name}
										</span>
									{:else if document.counterparty}
										<span class="text-slate-500">{document.counterparty}</span>
										{#if document.counterparty_disambiguation === 'pending'}
											<span class="ml-1 text-xs text-amber-600">(needs review)</span>
										{/if}
									{:else}
										<span class="text-slate-400">-</span>
									{/if}
								</dd>
							</div>

							<div>
								<dt class="text-sm font-medium text-slate-500">Persons</dt>
								<dd class="mt-1">
									{#if documentPersons.length > 0}
										<div class="flex flex-wrap gap-1">
											{#each documentPersons as dp}
												<span class="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 text-slate-700 rounded text-sm">
													{dp.person.canonical_name}
													<span class="text-xs text-slate-400">({dp.role})</span>
												</span>
											{/each}
										</div>
									{:else if document.affected_person}
										<span class="text-slate-500">{document.affected_person}</span>
										{#if document.persons_disambiguation === 'pending'}
											<span class="ml-1 text-xs text-amber-600">(needs review)</span>
										{/if}
									{:else}
										<span class="text-slate-400">-</span>
									{/if}
								</dd>
							</div>

							{#if document.reference}
								<div>
									<dt class="text-sm font-medium text-slate-500">Reference</dt>
									<dd class="mt-1 text-sm text-slate-900 font-mono">{document.reference}</dd>
								</div>
							{/if}

							<div>
								<dt class="text-sm font-medium text-slate-500">Document Date</dt>
								<dd class="mt-1 text-sm text-slate-900">{formatDate(document.document_date)}</dd>
							</div>

							<div>
								<dt class="text-sm font-medium text-slate-500">Pages</dt>
								<dd class="mt-1 text-sm text-slate-900">{document.page_count || '-'}</dd>
							</div>

							<div>
								<dt class="text-sm font-medium text-slate-500">File Size</dt>
								<dd class="mt-1 text-sm text-slate-900">{formatFileSize(document.file_size)}</dd>
							</div>

							<div>
								<dt class="text-sm font-medium text-slate-500">Added</dt>
								<dd class="mt-1 text-sm text-slate-900">{formatDate(document.created_at)}</dd>
							</div>

							{#if document.processed_at}
								<div>
									<dt class="text-sm font-medium text-slate-500">Processed</dt>
									<dd class="mt-1 text-sm text-slate-900">{formatDate(document.processed_at)}</dd>
								</div>
							{/if}
						</dl>
					{/if}
				</div>

				<!-- Tags -->
				<div class="bg-white rounded-xl shadow-sm p-6">
					<h2 class="text-lg font-semibold text-slate-900 mb-4">Tags</h2>
					<TagEditor
						tags={document.tags.map((t) => t.name)}
						on:add={handleAddTag}
						on:remove={handleRemoveTag}
					/>
				</div>

				<!-- Raw Text -->
				{#if document.raw_text}
					<div class="bg-white rounded-xl shadow-sm p-6">
						<button
							on:click={() => (showRawText = !showRawText)}
							class="flex items-center justify-between w-full text-left"
						>
							<h2 class="text-lg font-semibold text-slate-900">OCR Text</h2>
							<svg
								class="w-5 h-5 text-slate-400 transform transition-transform {showRawText ? 'rotate-180' : ''}"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
							</svg>
						</button>
						{#if showRawText}
							<pre class="mt-4 text-xs text-slate-600 whitespace-pre-wrap max-h-96 overflow-auto bg-slate-50 p-4 rounded-lg">{document.raw_text}</pre>
						{/if}
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm}
	<div class="fixed inset-0 z-50 overflow-y-auto">
		<div class="flex min-h-full items-center justify-center p-4">
			<div
				class="fixed inset-0 bg-slate-900/50"
				on:click={() => (showDeleteConfirm = false)}
				on:keydown={(e) => e.key === 'Escape' && (showDeleteConfirm = false)}
				role="button"
				tabindex="0"
			></div>

			<div class="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6">
				<h2 class="text-lg font-semibold text-slate-900">Delete Document</h2>
				<p class="mt-2 text-sm text-slate-500">
					Are you sure you want to delete this document? This action cannot be undone.
				</p>

				<div class="mt-6 flex justify-end gap-3">
					<button
						on:click={() => (showDeleteConfirm = false)}
						class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
					>
						Cancel
					</button>
					<button
						on:click={handleDelete}
						disabled={deleting}
						class="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
					>
						{deleting ? 'Deleting...' : 'Delete'}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
