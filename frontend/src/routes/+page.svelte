<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getStats, search, type DashboardStats, type SearchResult } from '$lib/api';
	import SearchBar from '$components/SearchBar.svelte';
	import DocumentCard from '$components/DocumentCard.svelte';

	let stats: DashboardStats | null = null;
	let loading = true;
	let searchQuery = '';
	let searchResults: SearchResult[] = [];
	let isSearching = false;

	onMount(async () => {
		try {
			stats = await getStats();
		} catch (error) {
			console.error('Failed to load stats:', error);
		} finally {
			loading = false;
		}
	});

	async function handleSearch(event: CustomEvent<{ query: string; type: string }>) {
		const { query, type } = event.detail;
		if (!query.trim()) {
			searchResults = [];
			return;
		}

		isSearching = true;
		try {
			const response = await search({
				query,
				search_type: type as 'keyword' | 'semantic' | 'hybrid'
			});
			searchResults = response.results;
		} catch (error) {
			console.error('Search failed:', error);
		} finally {
			isSearching = false;
		}
	}

	function getCategoryColor(category: string): string {
		const colors: Record<string, string> = {
			utilities: 'bg-blue-500',
			insurance: 'bg-green-500',
			tax: 'bg-orange-500',
			medical: 'bg-red-500',
			banking: 'bg-purple-500',
			salary: 'bg-emerald-500',
			contract: 'bg-indigo-500',
			legal: 'bg-amber-500',
			correspondence: 'bg-slate-500',
			receipt: 'bg-cyan-500',
			invoice: 'bg-teal-500',
			other: 'bg-slate-400'
		};
		return colors[category] || colors.other;
	}
</script>

<svelte:head>
	<title>Dashboard - DocStore</title>
</svelte:head>

<div class="space-y-8">
	<!-- Search Section -->
	<div class="bg-white rounded-xl shadow-sm p-6">
		<h2 class="text-lg font-semibold text-slate-900 mb-4">Search Documents</h2>
		<SearchBar on:search={handleSearch} bind:query={searchQuery} />

		{#if isSearching}
			<div class="flex justify-center py-8">
				<div class="spinner"></div>
			</div>
		{:else if searchResults.length > 0}
			<div class="mt-6 grid gap-4">
				{#each searchResults as result}
					<DocumentCard document={result.document} snippet={result.snippet} />
				{/each}
			</div>
		{:else if searchQuery && !isSearching}
			<p class="text-center text-slate-500 py-8">No results found for "{searchQuery}"</p>
		{/if}
	</div>

	{#if loading}
		<div class="flex justify-center py-12">
			<div class="spinner"></div>
		</div>
	{:else if stats}
		<!-- Stats Overview -->
		<div class="grid grid-cols-1 md:grid-cols-4 gap-4">
			<div class="bg-white rounded-xl shadow-sm p-6">
				<p class="text-sm font-medium text-slate-500">Total Documents</p>
				<p class="mt-2 text-3xl font-bold text-slate-900">{stats.total_documents}</p>
			</div>

			<div class="bg-white rounded-xl shadow-sm p-6">
				<p class="text-sm font-medium text-slate-500">Pending</p>
				<p class="mt-2 text-3xl font-bold text-yellow-600">
					{stats.documents_by_status['pending'] || 0}
				</p>
			</div>

			<div class="bg-white rounded-xl shadow-sm p-6">
				<p class="text-sm font-medium text-slate-500">Completed</p>
				<p class="mt-2 text-3xl font-bold text-green-600">
					{stats.documents_by_status['completed'] || 0}
				</p>
			</div>

			<div class="bg-white rounded-xl shadow-sm p-6">
				<p class="text-sm font-medium text-slate-500">Categories</p>
				<p class="mt-2 text-3xl font-bold text-slate-900">
					{Object.keys(stats.documents_by_category).filter(c => c !== 'uncategorized').length}
				</p>
			</div>
		</div>

		<!-- Document Categories -->
		{#if Object.keys(stats.documents_by_category).length > 0}
			<div class="bg-white rounded-xl shadow-sm p-6">
				<h3 class="text-lg font-semibold text-slate-900 mb-4">By Category</h3>
				<div class="flex flex-wrap gap-2">
					{#each Object.entries(stats.documents_by_category) as [category, count]}
						{#if category && category !== 'null' && category !== 'uncategorized'}
							<button
								on:click={() => goto(`/documents?category=${category}`)}
								class="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
							>
								<span class="w-3 h-3 rounded-full {getCategoryColor(category)}"></span>
								<span class="text-sm font-medium text-slate-700 capitalize">
									{category}
								</span>
								<span class="text-sm text-slate-500">({count})</span>
							</button>
						{/if}
					{/each}
				</div>
			</div>
		{/if}

		<!-- Recent Documents -->
		{#if stats.recent_documents.length > 0}
			<div class="bg-white rounded-xl shadow-sm p-6">
				<div class="flex justify-between items-center mb-4">
					<h3 class="text-lg font-semibold text-slate-900">Recent Documents</h3>
					<a href="/documents" class="text-sm text-primary-600 hover:text-primary-700">
						View all
					</a>
				</div>
				<div class="grid gap-4">
					{#each stats.recent_documents as doc}
						<DocumentCard document={doc} />
					{/each}
				</div>
			</div>
		{/if}

	{/if}
</div>
