<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { listDocuments, uploadDocument, listTags, type Document, type Tag } from '$lib/api';
	import DocumentCard from '$components/DocumentCard.svelte';
	import ScannerModal from '$lib/components/scanner/ScannerModal.svelte';

	let documents: Document[] = [];
	let tags: Tag[] = [];
	let total = 0;
	let currentPage = 1;
	let pageSize = 20;
	let loading = true;
	let uploading = false;
	let uploadError = '';

	let filterCategory = '';
	let filterStatus = '';
	let filterTag = '';

	let showUploadModal = false;
	let showScanner = false;
	let dragOver = false;

	const categories = [
		{ value: '', label: 'All Categories' },
		{ value: 'utilities', label: 'Utilities' },
		{ value: 'insurance', label: 'Insurance' },
		{ value: 'tax', label: 'Tax' },
		{ value: 'medical', label: 'Medical' },
		{ value: 'banking', label: 'Banking' },
		{ value: 'salary', label: 'Salary' },
		{ value: 'contract', label: 'Contract' },
		{ value: 'legal', label: 'Legal' },
		{ value: 'correspondence', label: 'Correspondence' },
		{ value: 'receipt', label: 'Receipt' },
		{ value: 'invoice', label: 'Invoice' },
		{ value: 'other', label: 'Other' }
	];

	const statuses = [
		{ value: '', label: 'All Status' },
		{ value: 'pending', label: 'Pending' },
		{ value: 'processing', label: 'Processing' },
		{ value: 'completed', label: 'Completed' },
		{ value: 'failed', label: 'Failed' }
	];

	onMount(async () => {
		// Check URL params for filters
		const urlParams = $page.url.searchParams;
		filterCategory = urlParams.get('category') || '';
		filterStatus = urlParams.get('status') || '';
		filterTag = urlParams.get('tag') || '';

		if (urlParams.get('upload') === 'true') {
			showUploadModal = true;
		}

		await loadData();
	});

	async function loadData() {
		loading = true;
		try {
			const [docsResponse, tagsResponse] = await Promise.all([
				listDocuments({
					page: currentPage,
					page_size: pageSize,
					category: filterCategory || undefined,
					status: filterStatus || undefined,
					tag: filterTag || undefined
				}),
				listTags()
			]);

			documents = docsResponse.items;
			total = docsResponse.total;
			tags = tagsResponse;
		} catch (error) {
			console.error('Failed to load documents:', error);
		} finally {
			loading = false;
		}
	}

	function handleFilterChange() {
		currentPage = 1;
		updateUrl();
		loadData();
	}

	function updateUrl() {
		const params = new URLSearchParams();
		if (filterCategory) params.set('category', filterCategory);
		if (filterStatus) params.set('status', filterStatus);
		if (filterTag) params.set('tag', filterTag);
		goto(`/documents${params.toString() ? '?' + params.toString() : ''}`, {
			replaceState: true,
			keepFocus: true
		});
	}

	async function handleFileUpload(files: FileList | null) {
		if (!files || files.length === 0) return;

		uploading = true;
		uploadError = '';

		try {
			for (const file of files) {
				await uploadDocument(file);
			}
			showUploadModal = false;
			await loadData();
		} catch (error) {
			uploadError = error instanceof Error ? error.message : 'Upload failed';
		} finally {
			uploading = false;
		}
	}

	function handleDrop(event: DragEvent) {
		event.preventDefault();
		dragOver = false;
		handleFileUpload(event.dataTransfer?.files || null);
	}

	function handleDragOver(event: DragEvent) {
		event.preventDefault();
		dragOver = true;
	}

	function handleDragLeave() {
		dragOver = false;
	}

	async function handleScanUpload(event: CustomEvent<{ file: File; onSuccess: () => void; onError: (error: string) => void }>) {
		const { file, onSuccess, onError } = event.detail;
		uploading = true;
		uploadError = '';

		try {
			await uploadDocument(file);
			await loadData();
			onSuccess();
		} catch (error) {
			const errorMessage = error instanceof Error ? error.message : 'Upload failed';
			uploadError = errorMessage;
			onError(errorMessage);
		} finally {
			uploading = false;
		}
	}

	$: totalPages = Math.ceil(total / pageSize);
	$: hasNextPage = currentPage < totalPages;
	$: hasPrevPage = currentPage > 1;
</script>

<svelte:head>
	<title>Documents - DocStore</title>
</svelte:head>

<div class="space-y-6">
	<!-- Header -->
	<div class="flex justify-between items-center">
		<h1 class="text-2xl font-bold text-slate-900">Documents</h1>
		<div class="flex gap-2">
			{#if browser}
				<button
					on:click={() => (showScanner = true)}
					class="inline-flex items-center px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
				>
					<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
						/>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
						/>
					</svg>
					Scan
				</button>
			{/if}
			<button
				on:click={() => (showUploadModal = true)}
				class="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
			>
				<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
				</svg>
				Upload
			</button>
		</div>
	</div>

	<!-- Filters -->
	<div class="bg-white rounded-lg shadow-sm p-4">
		<div class="flex flex-wrap gap-4">
			<select
				bind:value={filterCategory}
				on:change={handleFilterChange}
				class="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
			>
				{#each categories as cat}
					<option value={cat.value}>{cat.label}</option>
				{/each}
			</select>

			<select
				bind:value={filterStatus}
				on:change={handleFilterChange}
				class="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
			>
				{#each statuses as status}
					<option value={status.value}>{status.label}</option>
				{/each}
			</select>

			{#if tags.length > 0}
				<select
					bind:value={filterTag}
					on:change={handleFilterChange}
					class="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
				>
					<option value="">All Tags</option>
					{#each tags as tag}
						<option value={tag.name}>{tag.name}</option>
					{/each}
				</select>
			{/if}

			{#if filterCategory || filterStatus || filterTag}
				<button
					on:click={() => {
						filterCategory = '';
						filterStatus = '';
						filterTag = '';
						handleFilterChange();
					}}
					class="text-sm text-slate-500 hover:text-slate-700"
				>
					Clear filters
				</button>
			{/if}
		</div>
	</div>

	<!-- Document List -->
	{#if loading}
		<div class="flex justify-center py-12">
			<div class="spinner"></div>
		</div>
	{:else if documents.length === 0}
		<div class="text-center py-12">
			<svg
				class="mx-auto h-12 w-12 text-slate-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
				/>
			</svg>
			<h3 class="mt-2 text-sm font-medium text-slate-900">No documents</h3>
			<p class="mt-1 text-sm text-slate-500">Get started by uploading a document.</p>
			<button
				on:click={() => (showUploadModal = true)}
				class="mt-4 inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
			>
				Upload Document
			</button>
		</div>
	{:else}
		<div class="space-y-4">
			{#each documents as doc}
				<DocumentCard document={doc} />
			{/each}
		</div>

		<!-- Pagination -->
		{#if totalPages > 1}
			<div class="flex justify-between items-center bg-white rounded-lg shadow-sm p-4">
				<p class="text-sm text-slate-500">
					Showing {(currentPage - 1) * pageSize + 1} to {Math.min(currentPage * pageSize, total)} of {total} documents
				</p>
				<div class="flex gap-2">
					<button
						on:click={() => {
							currentPage--;
							loadData();
						}}
						disabled={!hasPrevPage}
						class="px-3 py-2 text-sm border border-slate-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50"
					>
						Previous
					</button>
					<button
						on:click={() => {
							currentPage++;
							loadData();
						}}
						disabled={!hasNextPage}
						class="px-3 py-2 text-sm border border-slate-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50"
					>
						Next
					</button>
				</div>
			</div>
		{/if}
	{/if}
</div>

<!-- Upload Modal -->
{#if showUploadModal}
	<div class="fixed inset-0 z-50 overflow-y-auto">
		<div class="flex min-h-full items-center justify-center p-4">
			<div
				class="fixed inset-0 bg-slate-900/50"
				on:click={() => (showUploadModal = false)}
				on:keydown={(e) => e.key === 'Escape' && (showUploadModal = false)}
				role="button"
				tabindex="0"
			></div>

			<div class="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
				<h2 class="text-lg font-semibold text-slate-900 mb-4">Upload Documents</h2>

				{#if uploadError}
					<div class="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
						{uploadError}
					</div>
				{/if}

				<div
					class="border-2 border-dashed rounded-lg p-8 text-center transition-colors
						{dragOver ? 'border-primary-500 bg-primary-50' : 'border-slate-300'}"
					on:drop={handleDrop}
					on:dragover={handleDragOver}
					on:dragleave={handleDragLeave}
					role="button"
					tabindex="0"
				>
					{#if uploading}
						<div class="spinner mx-auto"></div>
						<p class="mt-2 text-sm text-slate-500">Uploading...</p>
					{:else}
						<svg
							class="mx-auto h-12 w-12 text-slate-400"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
							/>
						</svg>
						<p class="mt-2 text-sm text-slate-500">
							Drag and drop files here, or
							<label class="text-primary-600 hover:text-primary-700 cursor-pointer">
								browse
								<input
									type="file"
									class="sr-only"
									accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif"
									multiple
									on:change={(e) => handleFileUpload(e.currentTarget.files)}
								/>
							</label>
						</p>
						<p class="mt-1 text-xs text-slate-400">PDF, JPG, PNG, TIFF up to 50MB</p>
					{/if}
				</div>

				<div class="mt-4 flex justify-end">
					<button
						on:click={() => (showUploadModal = false)}
						class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
					>
						Cancel
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- Scanner Modal -->
<ScannerModal
	bind:open={showScanner}
	on:close={() => (showScanner = false)}
	on:upload={handleScanUpload}
/>
