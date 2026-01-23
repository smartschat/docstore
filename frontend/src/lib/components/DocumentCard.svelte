<script lang="ts">
	import type { Document } from '$lib/api';
	import { getDocumentThumbnailUrl } from '$lib/api';

	export let document: Document;
	export let snippet: string | null = null;
	export let compact = false;

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '';
		return new Date(dateStr).toLocaleDateString('de-DE', {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
	}

	function formatFileSize(bytes: number | null): string {
		if (!bytes) return '';
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

	function formatCurrency(amount: number | null, currency: string = 'EUR'): string {
		if (amount === null) return '';
		return new Intl.NumberFormat('de-DE', {
			style: 'currency',
			currency
		}).format(amount);
	}

	let thumbnailError = false;

	function handleImageError(): void {
		thumbnailError = true;
	}
</script>

<a
	href="/documents/{document.id}"
	class="block bg-white border border-slate-200 rounded-lg hover:shadow-md transition-shadow overflow-hidden"
>
	<div class="flex">
		{#if !compact}
			<!-- Thumbnail -->
			<div class="flex-shrink-0 w-24 h-32 bg-slate-100 flex items-center justify-center">
				{#if thumbnailError}
					<svg class="w-8 h-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
					</svg>
				{:else}
					<img
						src={getDocumentThumbnailUrl(document.id)}
						alt=""
						class="w-full h-full object-cover"
						on:error={handleImageError}
					/>
				{/if}
			</div>
		{/if}

		<!-- Content -->
		<div class="flex-1 p-4 min-w-0">
			<div class="flex items-start justify-between gap-2">
				<div class="min-w-0">
					<h3 class="text-sm font-medium text-slate-900 truncate">{document.title || document.filename}</h3>
					{#if document.counterparty}
						<p class="text-xs text-slate-500">{document.counterparty}</p>
					{/if}
					{#if document.summary}
						<p class="mt-1 text-sm text-slate-500 line-clamp-2">{document.summary}</p>
					{/if}
				</div>

				<div class="flex-shrink-0 flex flex-col items-end gap-1">
					<div class="flex items-center gap-2">
						{#if document.category}
							<span class="badge {getCategoryClass(document.category)}">
								{document.category}
							</span>
						{/if}
						<span class="badge {getStatusClass(document.status)}">
							{document.status}
						</span>
					</div>
					{#if document.amount !== null}
						<span class="text-sm font-semibold text-slate-900">
							{formatCurrency(document.amount, document.currency)}
						</span>
					{/if}
				</div>
			</div>

			{#if snippet}
				<p class="mt-2 text-sm text-slate-600">
					{@html snippet}
				</p>
			{/if}

			<div class="mt-3 flex items-center gap-4 text-xs text-slate-400">
				{#if document.document_date}
					<span>Date: {formatDate(document.document_date)}</span>
				{/if}
				{#if document.page_count}
					<span>{document.page_count} pages</span>
				{/if}
				{#if document.file_size}
					<span>{formatFileSize(document.file_size)}</span>
				{/if}
				<span>Added: {formatDate(document.created_at)}</span>
			</div>

			{#if document.tags.length > 0}
				<div class="mt-2 flex flex-wrap gap-1">
					{#each document.tags as tag}
						<span class="inline-flex items-center px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">
							{tag.name}
						</span>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</a>
