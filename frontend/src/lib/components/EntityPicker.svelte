<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import {
		listCounterparties,
		listPersons,
		type Counterparty,
		type Person
	} from '$lib/api';

	export let entityType: 'counterparty' | 'person' = 'counterparty';
	export let value: string | null = null; // Entity ID
	export let selectedName: string | null = null; // Display name
	export let placeholder = 'Search...';

	const dispatch = createEventDispatcher<{
		select: { id: string; name: string } | null;
		create: string;
	}>();

	let searchQuery = '';
	let results: (Counterparty | Person)[] = [];
	let showDropdown = false;
	let loading = false;
	let searchTimeout: ReturnType<typeof setTimeout>;

	$: displayValue = selectedName || '';

	async function handleSearch() {
		if (!searchQuery.trim()) {
			results = [];
			return;
		}

		loading = true;
		try {
			if (entityType === 'counterparty') {
				const response = await listCounterparties(searchQuery);
				results = response.items;
			} else {
				const response = await listPersons(searchQuery);
				results = response.items;
			}
		} catch (e) {
			console.error('Search failed:', e);
			results = [];
		} finally {
			loading = false;
		}
	}

	function handleInput() {
		clearTimeout(searchTimeout);
		searchTimeout = setTimeout(handleSearch, 300);
	}

	function handleFocus() {
		showDropdown = true;
		if (searchQuery.trim()) {
			handleSearch();
		}
	}

	function handleBlur() {
		// Delay to allow click on dropdown item
		setTimeout(() => {
			showDropdown = false;
		}, 200);
	}

	function selectEntity(entity: Counterparty | Person) {
		value = entity.id;
		selectedName = entity.canonical_name;
		searchQuery = '';
		results = [];
		showDropdown = false;
		dispatch('select', { id: entity.id, name: entity.canonical_name });
	}

	function clearSelection() {
		value = null;
		selectedName = null;
		searchQuery = '';
		dispatch('select', null);
	}

	function handleCreateNew() {
		if (searchQuery.trim()) {
			dispatch('create', searchQuery.trim());
			searchQuery = '';
			showDropdown = false;
		}
	}

	function getMatchedAlias(entity: Counterparty | Person): string | null {
		if (!searchQuery) return null;
		const query = searchQuery.toLowerCase();
		const alias = entity.aliases.find(
			(a) => a.alias.toLowerCase().includes(query) && a.alias !== entity.canonical_name
		);
		return alias?.alias || null;
	}
</script>

<div class="relative">
	{#if value && selectedName}
		<!-- Selected entity display -->
		<div
			class="flex items-center justify-between px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg"
		>
			<span class="text-sm text-slate-900">{selectedName}</span>
			<button
				type="button"
				on:click={clearSelection}
				class="p-1 text-slate-400 hover:text-slate-600"
				aria-label="Clear selection"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
			</button>
		</div>
	{:else}
		<!-- Search input -->
		<input
			type="text"
			bind:value={searchQuery}
			on:input={handleInput}
			on:focus={handleFocus}
			on:blur={handleBlur}
			{placeholder}
			class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
		/>

		<!-- Loading indicator -->
		{#if loading}
			<div class="absolute right-3 top-1/2 -translate-y-1/2">
				<div class="w-4 h-4 border-2 border-slate-300 border-t-primary-600 rounded-full animate-spin"></div>
			</div>
		{/if}

		<!-- Dropdown -->
		{#if showDropdown && (results.length > 0 || searchQuery.trim())}
			<div
				class="absolute z-20 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-auto"
			>
				{#each results as entity}
					{@const matchedAlias = getMatchedAlias(entity)}
					<button
						type="button"
						on:click={() => selectEntity(entity)}
						class="w-full px-3 py-2 text-left hover:bg-slate-50 border-b border-slate-100 last:border-b-0"
					>
						<div class="text-sm font-medium text-slate-900">{entity.canonical_name}</div>
						{#if matchedAlias}
							<div class="text-xs text-slate-500">
								matched: "{matchedAlias}"
							</div>
						{/if}
						{#if entity.aliases.length > 1}
							<div class="text-xs text-slate-400 truncate">
								{entity.aliases
									.filter((a) => a.alias !== entity.canonical_name)
									.map((a) => a.alias)
									.slice(0, 3)
									.join(', ')}
								{#if entity.aliases.length > 4}
									...
								{/if}
							</div>
						{/if}
					</button>
				{/each}

				{#if searchQuery.trim()}
					<button
						type="button"
						on:click={handleCreateNew}
						class="w-full px-3 py-2 text-left hover:bg-primary-50 text-primary-600 border-t border-slate-200"
					>
						<div class="flex items-center gap-2 text-sm">
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M12 4v16m8-8H4"
								/>
							</svg>
							Create "{searchQuery.trim()}"
						</div>
					</button>
				{/if}
			</div>
		{/if}
	{/if}
</div>
