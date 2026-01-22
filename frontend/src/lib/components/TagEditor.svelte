<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let tags: string[] = [];
	export let suggestions: string[] = [];
	export let placeholder = 'Add a tag...';

	const dispatch = createEventDispatcher<{
		add: string;
		remove: string;
	}>();

	let newTag = '';
	let showSuggestions = false;

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && newTag.trim()) {
			event.preventDefault();
			addTag(newTag.trim());
		} else if (event.key === 'Escape') {
			showSuggestions = false;
		}
	}

	function addTag(tag: string) {
		if (tag && !tags.includes(tag)) {
			dispatch('add', tag);
			newTag = '';
		}
		showSuggestions = false;
	}

	function removeTag(tag: string) {
		dispatch('remove', tag);
	}

	$: filteredSuggestions = suggestions.filter(
		(s) => !tags.includes(s) && s.toLowerCase().includes(newTag.toLowerCase())
	);
</script>

<div class="space-y-2">
	<!-- Tags -->
	{#if tags.length > 0}
		<div class="flex flex-wrap gap-2">
			{#each tags as tag}
				<span class="inline-flex items-center gap-1 px-2 py-1 bg-primary-50 text-primary-700 rounded-full text-sm">
					{tag}
					<button
						on:click={() => removeTag(tag)}
						class="p-0.5 rounded-full hover:bg-primary-200"
						aria-label="Remove tag {tag}"
					>
						<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</span>
			{/each}
		</div>
	{/if}

	<!-- Input -->
	<div class="relative">
		<input
			type="text"
			bind:value={newTag}
			on:keydown={handleKeydown}
			on:focus={() => (showSuggestions = true)}
			on:blur={() => setTimeout(() => (showSuggestions = false), 200)}
			{placeholder}
			class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
		/>

		<!-- Suggestions dropdown -->
		{#if showSuggestions && filteredSuggestions.length > 0}
			<div class="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-auto">
				{#each filteredSuggestions as suggestion}
					<button
						on:click={() => addTag(suggestion)}
						class="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
					>
						{suggestion}
					</button>
				{/each}
			</div>
		{/if}
	</div>

	<p class="text-xs text-slate-400">Press Enter to add a tag</p>
</div>
