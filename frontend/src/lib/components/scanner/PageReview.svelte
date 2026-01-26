<script lang="ts">
	import { createEventDispatcher, onMount, onDestroy } from 'svelte';
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
	let dragOverIndex: number | null = null;
	let gridElement: HTMLElement;

	// Touch drag state
	let isTouchDragging = false;
	let touchDragElement: HTMLElement | null = null;
	let touchStartY = 0;
	let touchStartX = 0;

	function handleDelete(pageId: string) {
		removePage(pageId);
	}

	function handleMoveUp(pageId: string) {
		movePageUp(pageId);
	}

	function handleMoveDown(pageId: string) {
		movePageDown(pageId);
	}

	// HTML5 Drag and Drop (desktop)
	function handleDragStart(event: DragEvent, index: number) {
		// Required for Firefox - must set data
		event.dataTransfer?.setData('text/plain', String(index));
		event.dataTransfer!.effectAllowed = 'move';
		draggedIndex = index;
	}

	function handleDragOver(event: DragEvent, targetIndex: number) {
		event.preventDefault();
		event.dataTransfer!.dropEffect = 'move';
		dragOverIndex = targetIndex;
	}

	function handleDrop(event: DragEvent, targetIndex: number) {
		event.preventDefault();
		if (draggedIndex !== null && draggedIndex !== targetIndex) {
			reorderPages(draggedIndex, targetIndex);
		}
		draggedIndex = null;
		dragOverIndex = null;
	}

	function handleDragEnd() {
		draggedIndex = null;
		dragOverIndex = null;
	}

	// Touch/Pointer-based drag (mobile)
	function handlePointerDown(event: PointerEvent, index: number) {
		const target = event.target as HTMLElement;
		// Only start drag from drag handle
		if (!target.closest('[data-drag-handle]')) return;

		event.preventDefault();
		isTouchDragging = true;
		draggedIndex = index;
		touchStartX = event.clientX;
		touchStartY = event.clientY;

		// Capture pointer for tracking outside element
		(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
	}

	function handlePointerMove(event: PointerEvent) {
		if (!isTouchDragging || draggedIndex === null) return;

		event.preventDefault();

		// Find element under touch point
		const elementsAtPoint = document.elementsFromPoint(event.clientX, event.clientY);
		const targetItem = elementsAtPoint.find((el) => el.hasAttribute('data-page-index'));

		if (targetItem) {
			const targetIndex = parseInt(targetItem.getAttribute('data-page-index')!, 10);
			if (targetIndex !== draggedIndex) {
				reorderPages(draggedIndex, targetIndex);
				draggedIndex = targetIndex;
			}
		}
	}

	function handlePointerUp() {
		if (!isTouchDragging) return;

		isTouchDragging = false;
		draggedIndex = null;
		dragOverIndex = null;
		// Pointer capture is released automatically on pointerup
	}

	function handlePointerCancel() {
		handlePointerUp();
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
				bind:this={gridElement}
				class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4"
				role="list"
				aria-label="Scanned pages"
				on:pointermove={handlePointerMove}
				on:pointerup={handlePointerUp}
				on:pointercancel={handlePointerCancel}
			>
				{#each $pages as page, index (page.id)}
					<div
						role="listitem"
						data-page-index={index}
						draggable="true"
						on:dragstart={(e) => handleDragStart(e, index)}
						on:dragover={(e) => handleDragOver(e, index)}
						on:drop={(e) => handleDrop(e, index)}
						on:dragend={handleDragEnd}
						on:pointerdown={(e) => handlePointerDown(e, index)}
						class={dragOverIndex === index && draggedIndex !== index ? 'ring-2 ring-primary-400 ring-offset-2 rounded-lg' : ''}
					>
						<PageThumbnail
							imageUrl={page.objectUrl}
							pageNumber={index + 1}
							isFirst={index === 0}
							isLast={index === $pages.length - 1}
							isDragging={draggedIndex === index}
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
