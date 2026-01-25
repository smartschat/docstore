<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import PageThumbnail from './PageThumbnail.svelte';
	import {
		pages,
		pageCount,
		isAtPageLimit,
		canAddMorePages,
		MAX_PAGES,
		removePage,
		movePageUp,
		movePageDown,
		reorderPages
	} from '$lib/stores/scanner';

	const dispatch = createEventDispatcher<{
		addPage: void;
		save: void;
	}>();

	let draggedIndex: number | null = null;

	function handleDelete(pageId: string) {
		removePage(pageId);
	}

	function handleMoveUp(pageId: string) {
		movePageUp(pageId);
	}

	function handleMoveDown(pageId: string) {
		movePageDown(pageId);
	}

	function handleDragStart(index: number) {
		draggedIndex = index;
	}

	function handleDragOver(event: DragEvent, targetIndex: number) {
		event.preventDefault();
		if (draggedIndex !== null && draggedIndex !== targetIndex) {
			reorderPages(draggedIndex, targetIndex);
			draggedIndex = targetIndex;
		}
	}

	function handleDragEnd() {
		draggedIndex = null;
	}
</script>

<div class="flex flex-col h-full bg-slate-100">
	<!-- Header -->
	<div class="flex items-center justify-between p-4 bg-white border-b border-slate-200">
		<div>
			<h2 class="text-lg font-semibold text-slate-900">Review Pages</h2>
			<p class="text-sm text-slate-500">
				{$pageCount} page{$pageCount !== 1 ? 's' : ''}
				{#if $isAtPageLimit}
					<span class="text-amber-600">(limit reached)</span>
				{/if}
			</p>
		</div>
	</div>

	<!-- Page grid -->
	<div class="flex-1 overflow-y-auto p-4">
		{#if $pageCount === 0}
			<div class="flex flex-col items-center justify-center h-full text-center">
				<svg class="w-16 h-16 text-slate-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
					/>
				</svg>
				<p class="text-slate-500">No pages scanned yet</p>
			</div>
		{:else}
			<div
				class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4"
				role="list"
				aria-label="Scanned pages"
			>
				{#each $pages as page, index (page.id)}
					<div
						role="listitem"
						draggable="true"
						on:dragstart={() => handleDragStart(index)}
						on:dragover={(e) => handleDragOver(e, index)}
						on:dragend={handleDragEnd}
					>
						<PageThumbnail
							imageUrl={page.objectUrl}
							pageNumber={index + 1}
							isFirst={index === 0}
							isLast={index === $pages.length - 1}
							on:delete={() => handleDelete(page.id)}
							on:moveUp={() => handleMoveUp(page.id)}
							on:moveDown={() => handleMoveDown(page.id)}
						/>
					</div>
				{/each}
			</div>
		{/if}

		{#if $isAtPageLimit}
			<div class="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
				<p class="text-sm text-amber-800">
					<strong>Page limit reached.</strong> Maximum of {MAX_PAGES} pages per scan. Delete pages to add more.
				</p>
			</div>
		{/if}
	</div>

	<!-- Actions -->
	<div class="flex gap-3 p-4 bg-white border-t border-slate-200">
		{#if $canAddMorePages}
			<button
				type="button"
				on:click={() => dispatch('addPage')}
				class="flex-1 py-3 px-4 bg-slate-100 text-slate-700 rounded-lg font-medium hover:bg-slate-200 transition-colors flex items-center justify-center gap-2"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
				</svg>
				Add Page
			</button>
		{/if}

		<button
			type="button"
			on:click={() => dispatch('save')}
			disabled={$pageCount === 0}
			class="flex-1 py-3 px-4 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
		>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			Save as PDF
		</button>
	</div>
</div>
