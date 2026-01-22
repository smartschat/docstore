<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let query = '';
	export let searchType: 'keyword' | 'semantic' | 'hybrid' = 'hybrid';
	export let placeholder = 'Search documents...';

	const dispatch = createEventDispatcher<{
		search: { query: string; type: string };
	}>();

	let debounceTimer: ReturnType<typeof setTimeout>;

	function handleInput() {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			dispatch('search', { query, type: searchType });
		}, 300);
	}

	function handleSubmit() {
		clearTimeout(debounceTimer);
		dispatch('search', { query, type: searchType });
	}

	function handleTypeChange() {
		if (query.trim()) {
			dispatch('search', { query, type: searchType });
		}
	}
</script>

<form on:submit|preventDefault={handleSubmit} class="space-y-3">
	<div class="flex gap-2">
		<div class="relative flex-1">
			<div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
				<svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
					/>
				</svg>
			</div>
			<input
				type="text"
				bind:value={query}
				on:input={handleInput}
				{placeholder}
				class="block w-full pl-10 pr-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
			/>
		</div>

		<button
			type="submit"
			class="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
		>
			Search
		</button>
	</div>

	<div class="flex items-center gap-4">
		<span class="text-sm text-slate-500">Search type:</span>
		<div class="flex gap-2">
			{#each ['hybrid', 'semantic', 'keyword'] as type}
				<label
					class="inline-flex items-center px-3 py-1 rounded-full text-sm cursor-pointer transition-colors
						{searchType === type
						? 'bg-primary-100 text-primary-700'
						: 'bg-slate-100 text-slate-600 hover:bg-slate-200'}"
				>
					<input
						type="radio"
						name="searchType"
						value={type}
						bind:group={searchType}
						on:change={handleTypeChange}
						class="sr-only"
					/>
					<span class="capitalize">{type}</span>
				</label>
			{/each}
		</div>
	</div>
</form>
