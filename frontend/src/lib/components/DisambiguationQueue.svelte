<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getPendingDisambiguations,
		resolveDisambiguation,
		createCounterparty,
		createPerson,
		type DocumentDisambiguation,
		type DisambiguationCandidate
	} from '$lib/api';

	let items: DocumentDisambiguation[] = [];
	let loading = true;
	let error = '';
	let resolving: string | null = null;

	onMount(async () => {
		await loadItems();
	});

	async function loadItems() {
		loading = true;
		error = '';
		try {
			items = await getPendingDisambiguations();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load pending items';
		} finally {
			loading = false;
		}
	}

	async function handleResolve(
		item: DocumentDisambiguation,
		entityType: 'counterparty' | 'person',
		candidate: DisambiguationCandidate | null
	) {
		const key = `${item.document_id}-${entityType}`;
		resolving = key;
		error = '';

		try {
			if (candidate) {
				// Link to existing entity
				await resolveDisambiguation(item.document_id, entityType, candidate.entity_id, true);
			} else {
				// Create new entity
				const rawName =
					entityType === 'counterparty' ? item.counterparty_raw : item.affected_person_raw;

				if (rawName) {
					if (entityType === 'counterparty') {
						const newEntity = await createCounterparty({ canonical_name: rawName });
						await resolveDisambiguation(item.document_id, entityType, newEntity.id, false);
					} else {
						const newEntity = await createPerson({ canonical_name: rawName });
						await resolveDisambiguation(item.document_id, entityType, newEntity.id, false);
					}
				}
			}

			// Reload the list
			await loadItems();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to resolve disambiguation';
		} finally {
			resolving = null;
		}
	}

	function formatScore(score: number): string {
		return `${Math.round(score * 100)}%`;
	}
</script>

<div class="space-y-4">
	{#if loading}
		<div class="flex justify-center py-8">
			<div class="spinner"></div>
		</div>
	{:else if error}
		<div class="p-4 bg-red-50 text-red-700 rounded-lg">{error}</div>
	{:else if items.length === 0}
		<div class="text-center py-8 text-slate-500">No pending disambiguations</div>
	{:else}
		{#each items as item}
			<div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
				<!-- Header -->
				<div class="px-4 py-3 bg-slate-50 border-b border-slate-200">
					<a
						href="/documents/{item.document_id}"
						class="font-medium text-slate-900 hover:text-primary-600"
					>
						{item.title || item.filename}
					</a>
				</div>

				<div class="p-4 space-y-4">
					<!-- Counterparty disambiguation -->
					{#if item.counterparty_raw}
						<div class="space-y-2">
							<div class="text-sm font-medium text-slate-700">Counterparty</div>
							<div class="text-sm text-slate-600">
								Extracted: <span class="font-mono bg-slate-100 px-1 rounded"
									>{item.counterparty_raw}</span
								>
							</div>

							{#if item.counterparty_candidates.length > 0}
								<div class="space-y-1">
									{#each item.counterparty_candidates as candidate}
										<button
											on:click={() => handleResolve(item, 'counterparty', candidate)}
											disabled={resolving === `${item.document_id}-counterparty`}
											class="w-full flex items-center justify-between px-3 py-2 text-sm text-left border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50"
										>
											<div>
												<span class="font-medium">{candidate.entity_name}</span>
												{#if candidate.matched_alias}
													<span class="text-slate-500 ml-2"
														>(matched: {candidate.matched_alias})</span
													>
												{/if}
											</div>
											<span class="text-slate-400 text-xs">{formatScore(candidate.score)}</span>
										</button>
									{/each}
								</div>
							{/if}

							<button
								on:click={() => handleResolve(item, 'counterparty', null)}
								disabled={resolving === `${item.document_id}-counterparty`}
								class="w-full flex items-center gap-2 px-3 py-2 text-sm text-primary-600 border border-dashed border-primary-300 rounded-lg hover:bg-primary-50 disabled:opacity-50"
							>
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M12 4v16m8-8H4"
									/>
								</svg>
								Create new counterparty
							</button>
						</div>
					{/if}

					<!-- Person disambiguation -->
					{#if item.affected_person_raw}
						<div class="space-y-2">
							<div class="text-sm font-medium text-slate-700">Person</div>
							<div class="text-sm text-slate-600">
								Extracted: <span class="font-mono bg-slate-100 px-1 rounded"
									>{item.affected_person_raw}</span
								>
							</div>

							{#if item.person_candidates.length > 0}
								<div class="space-y-1">
									{#each item.person_candidates as candidate}
										<button
											on:click={() => handleResolve(item, 'person', candidate)}
											disabled={resolving === `${item.document_id}-person`}
											class="w-full flex items-center justify-between px-3 py-2 text-sm text-left border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50"
										>
											<div>
												<span class="font-medium">{candidate.entity_name}</span>
												{#if candidate.matched_alias}
													<span class="text-slate-500 ml-2"
														>(matched: {candidate.matched_alias})</span
													>
												{/if}
											</div>
											<span class="text-slate-400 text-xs">{formatScore(candidate.score)}</span>
										</button>
									{/each}
								</div>
							{/if}

							<button
								on:click={() => handleResolve(item, 'person', null)}
								disabled={resolving === `${item.document_id}-person`}
								class="w-full flex items-center gap-2 px-3 py-2 text-sm text-primary-600 border border-dashed border-primary-300 rounded-lg hover:bg-primary-50 disabled:opacity-50"
							>
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M12 4v16m8-8H4"
									/>
								</svg>
								Create new person
							</button>
						</div>
					{/if}
				</div>
			</div>
		{/each}
	{/if}
</div>
