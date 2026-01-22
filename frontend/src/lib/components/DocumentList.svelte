<script lang="ts">
	import type { Document } from '$lib/api';
	import DocumentCard from './DocumentCard.svelte';

	export let documents: Document[] = [];
	export let loading = false;
	export let emptyMessage = 'No documents found';
</script>

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
		<p class="mt-2 text-sm text-slate-500">{emptyMessage}</p>
	</div>
{:else}
	<div class="space-y-4">
		{#each documents as document (document.id)}
			<DocumentCard {document} />
		{/each}
	</div>
{/if}
