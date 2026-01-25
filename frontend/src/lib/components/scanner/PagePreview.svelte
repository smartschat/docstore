<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { pageCount, isAtPageLimit, MAX_PAGES } from '$lib/stores/scanner';

	export let imageUrl: string;

	const dispatch = createEventDispatcher<{
		retake: void;
		addPage: void;
		done: void;
	}>();
</script>

<div class="flex flex-col h-full bg-slate-900">
	<!-- Image preview -->
	<div class="flex-1 relative overflow-hidden">
		<img src={imageUrl} alt="Captured page" class="absolute inset-0 w-full h-full object-contain" />

		<!-- Page count badge -->
		<div class="absolute top-4 left-4 px-3 py-1.5 bg-black/70 rounded-full text-white text-sm font-medium">
			Page {$pageCount}
		</div>
	</div>

	<!-- Actions -->
	<div class="flex gap-3 p-4 bg-black">
		<button
			type="button"
			on:click={() => dispatch('retake')}
			class="flex-1 py-3 px-4 bg-slate-700 text-white rounded-lg font-medium hover:bg-slate-600 transition-colors"
		>
			Retake
		</button>

		{#if $isAtPageLimit}
			<button
				type="button"
				disabled
				class="flex-1 py-3 px-4 bg-slate-800 text-slate-500 rounded-lg font-medium cursor-not-allowed"
				title="Maximum {MAX_PAGES} pages reached"
			>
				Limit Reached
			</button>
		{:else}
			<button
				type="button"
				on:click={() => dispatch('addPage')}
				class="flex-1 py-3 px-4 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors"
			>
				Add Page
			</button>
		{/if}

		<button
			type="button"
			on:click={() => dispatch('done')}
			class="flex-1 py-3 px-4 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
		>
			Done
		</button>
	</div>
</div>
