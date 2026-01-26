<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let imageUrl: string;
	export let pageNumber: number;
	export let isFirst: boolean = false;
	export let isLast: boolean = false;

	const dispatch = createEventDispatcher<{
		delete: void;
		moveUp: void;
		moveDown: void;
	}>();

	export let isDragging = false;
</script>

<div
	class="relative group bg-white rounded-lg shadow-md overflow-hidden border-2 transition-colors
		{isDragging ? 'border-primary-500 opacity-50' : 'border-transparent hover:border-slate-300'}"
	role="listitem"
	aria-label="Page {pageNumber}"
>
	<!-- Thumbnail image -->
	<div class="aspect-[3/4] relative">
		<img src={imageUrl} alt="Page {pageNumber}" class="absolute inset-0 w-full h-full object-cover" />

		<!-- Page number badge -->
		<div
			class="absolute top-2 left-2 w-6 h-6 bg-primary-600 rounded-full flex items-center justify-center text-white text-xs font-bold"
		>
			{pageNumber}
		</div>

		<!-- Delete button (visible on hover for mouse, always visible on touch) -->
		<button
			type="button"
			on:click={() => dispatch('delete')}
			class="absolute top-2 right-2 w-6 h-6 bg-red-500 rounded-full flex items-center justify-center text-white touch-visible opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
			aria-label="Delete page {pageNumber}"
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>

		<!-- Drag handle (visible on hover for mouse, always visible on touch) -->
		<div
			data-drag-handle
			class="absolute bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 bg-black/60 rounded-full touch-visible opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing"
			style="touch-action: none;"
			role="button"
			tabindex="0"
			aria-label="Drag to reorder"
		>
			<svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
				<path d="M8 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0zm0 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0zm-2 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm8-14a2 2 0 1 1-4 0 2 2 0 0 1 4 0zm-2 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm2 4a2 2 0 1 1-4 0 2 2 0 0 1 4 0z" />
			</svg>
		</div>
	</div>

	<!-- Accessible move buttons -->
	<div class="flex border-t border-slate-200">
		<button
			type="button"
			on:click={() => dispatch('moveUp')}
			disabled={isFirst}
			class="flex-1 py-2 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
			aria-label="Move page up"
		>
			<svg class="w-4 h-4 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
			</svg>
		</button>
		<div class="w-px bg-slate-200" />
		<button
			type="button"
			on:click={() => dispatch('moveDown')}
			disabled={isLast}
			class="flex-1 py-2 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
			aria-label="Move page down"
		>
			<svg class="w-4 h-4 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
			</svg>
		</button>
	</div>
</div>

<style>
	/* Show controls by default on touch devices (no hover capability) */
	@media (hover: none) {
		:global(.touch-visible) {
			opacity: 0.9 !important;
		}
	}
</style>
