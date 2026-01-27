<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import {
		listCounterparties,
		listPersons,
		createCounterparty,
		createPerson,
		updateCounterparty,
		updatePerson,
		deleteCounterparty,
		deletePerson,
		addCounterpartyAlias,
		addPersonAlias,
		removeCounterpartyAlias,
		removePersonAlias,
		mergeCounterparties,
		mergePersons,
		getStats,
		type Counterparty,
		type Person
	} from '$lib/api';
	import DisambiguationQueue from '$components/DisambiguationQueue.svelte';

	type Tab = 'counterparties' | 'persons' | 'pending';

	let activeTab: Tab = 'counterparties';

	// Check URL param for initial tab
	$: {
		const tabParam = $page.url.searchParams.get('tab');
		if (tabParam === 'pending' || tabParam === 'counterparties' || tabParam === 'persons') {
			activeTab = tabParam;
		}
	}
	let counterparties: Counterparty[] = [];
	let persons: Person[] = [];
	let pendingCount = 0;
	let loading = true;
	let error = '';
	let search = '';

	// Modal state
	let showCreateModal = false;
	let showEditModal = false;
	let showMergeModal = false;
	let showDeleteConfirm = false;

	let editingEntity: Counterparty | Person | null = null;
	let mergeTarget: Counterparty | Person | null = null;
	let deleteTarget: { type: 'counterparty' | 'person'; entity: Counterparty | Person } | null =
		null;

	// Form data
	let formData = {
		canonical_name: '',
		short_name: '',
		first_name: '',
		last_name: '',
		notes: '',
		newAlias: ''
	};

	onMount(async () => {
		await loadData();
	});

	async function loadData() {
		loading = true;
		error = '';
		try {
			const [cpResponse, pResponse, stats] = await Promise.all([
				listCounterparties(search || undefined),
				listPersons(search || undefined),
				getStats()
			]);
			counterparties = cpResponse.items;
			persons = pResponse.items;
			pendingCount = stats.pending_reviews;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load data';
		} finally {
			loading = false;
		}
	}

	function handleSearch() {
		loadData();
	}

	function openCreateModal() {
		formData = {
			canonical_name: '',
			short_name: '',
			first_name: '',
			last_name: '',
			notes: '',
			newAlias: ''
		};
		showCreateModal = true;
	}

	function openEditModal(entity: Counterparty | Person) {
		editingEntity = entity;
		const isPerson = 'first_name' in entity;
		formData = {
			canonical_name: entity.canonical_name,
			short_name: !isPerson ? (entity as Counterparty).short_name || '' : '',
			first_name: isPerson ? (entity as Person).first_name || '' : '',
			last_name: isPerson ? (entity as Person).last_name || '' : '',
			notes: entity.notes || '',
			newAlias: ''
		};
		showEditModal = true;
	}

	function openMergeModal(entity: Counterparty | Person) {
		mergeTarget = entity;
		showMergeModal = true;
	}

	function openDeleteConfirm(type: 'counterparty' | 'person', entity: Counterparty | Person) {
		deleteTarget = { type, entity };
		showDeleteConfirm = true;
	}

	async function handleCreate() {
		error = '';
		try {
			if (activeTab === 'counterparties') {
				await createCounterparty({
					canonical_name: formData.canonical_name,
					short_name: formData.short_name || undefined,
					notes: formData.notes || undefined
				});
			} else {
				await createPerson({
					canonical_name: formData.canonical_name,
					first_name: formData.first_name || undefined,
					last_name: formData.last_name || undefined,
					notes: formData.notes || undefined
				});
			}
			showCreateModal = false;
			await loadData();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create';
		}
	}

	async function handleUpdate() {
		if (!editingEntity) return;
		error = '';
		try {
			const isPerson = 'first_name' in editingEntity;
			if (isPerson) {
				await updatePerson(editingEntity.id, {
					canonical_name: formData.canonical_name,
					first_name: formData.first_name || undefined,
					last_name: formData.last_name || undefined,
					notes: formData.notes || undefined
				});
			} else {
				await updateCounterparty(editingEntity.id, {
					canonical_name: formData.canonical_name,
					short_name: formData.short_name || undefined,
					notes: formData.notes || undefined
				});
			}
			showEditModal = false;
			editingEntity = null;
			await loadData();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to update';
		}
	}

	async function handleAddAlias() {
		if (!editingEntity || !formData.newAlias.trim()) return;
		error = '';
		try {
			const isPerson = 'first_name' in editingEntity;
			if (isPerson) {
				await addPersonAlias(editingEntity.id, formData.newAlias.trim());
			} else {
				await addCounterpartyAlias(editingEntity.id, formData.newAlias.trim());
			}
			formData.newAlias = '';
			// Reload the entity
			await loadData();
			const reloaded = isPerson
				? persons.find((p) => p.id === editingEntity?.id)
				: counterparties.find((c) => c.id === editingEntity?.id);
			if (reloaded) {
				editingEntity = reloaded;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to add alias';
		}
	}

	async function handleRemoveAlias(aliasId: number) {
		if (!editingEntity) return;
		error = '';
		try {
			const isPerson = 'first_name' in editingEntity;
			if (isPerson) {
				await removePersonAlias(editingEntity.id, aliasId);
			} else {
				await removeCounterpartyAlias(editingEntity.id, aliasId);
			}
			// Reload
			await loadData();
			const reloaded = isPerson
				? persons.find((p) => p.id === editingEntity?.id)
				: counterparties.find((c) => c.id === editingEntity?.id);
			if (reloaded) {
				editingEntity = reloaded;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to remove alias';
		}
	}

	async function handleMerge(keepId: string) {
		if (!mergeTarget) return;
		error = '';
		try {
			const isPerson = 'first_name' in mergeTarget;
			if (isPerson) {
				await mergePersons(keepId, mergeTarget.id);
			} else {
				await mergeCounterparties(keepId, mergeTarget.id);
			}
			showMergeModal = false;
			mergeTarget = null;
			await loadData();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to merge';
		}
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		error = '';
		try {
			if (deleteTarget.type === 'counterparty') {
				await deleteCounterparty(deleteTarget.entity.id);
			} else {
				await deletePerson(deleteTarget.entity.id);
			}
			showDeleteConfirm = false;
			deleteTarget = null;
			await loadData();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete';
		}
	}

	$: currentList = activeTab === 'counterparties' ? counterparties : persons;
</script>

<svelte:head>
	<title>Entities - DocStore</title>
</svelte:head>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold text-slate-900">Entity Management</h1>

		{#if activeTab !== 'pending'}
			<button
				on:click={openCreateModal}
				class="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
			>
				Add {activeTab === 'counterparties' ? 'Counterparty' : 'Person'}
			</button>
		{/if}
	</div>

	{#if error}
		<div class="p-4 bg-red-50 text-red-700 rounded-lg">{error}</div>
	{/if}

	<!-- Tabs -->
	<div class="border-b border-slate-200">
		<nav class="flex gap-4">
			<button
				on:click={() => (activeTab = 'counterparties')}
				class="px-1 py-3 text-sm font-medium border-b-2 transition-colors {activeTab ===
				'counterparties'
					? 'border-primary-600 text-primary-600'
					: 'border-transparent text-slate-500 hover:text-slate-700'}"
			>
				Counterparties ({counterparties.length})
			</button>
			<button
				on:click={() => (activeTab = 'persons')}
				class="px-1 py-3 text-sm font-medium border-b-2 transition-colors {activeTab === 'persons'
					? 'border-primary-600 text-primary-600'
					: 'border-transparent text-slate-500 hover:text-slate-700'}"
			>
				Persons ({persons.length})
			</button>
			<button
				on:click={() => (activeTab = 'pending')}
				class="px-1 py-3 text-sm font-medium border-b-2 transition-colors {activeTab === 'pending'
					? 'border-primary-600 text-primary-600'
					: 'border-transparent text-slate-500 hover:text-slate-700'}"
			>
				Pending Review ({pendingCount})
			</button>
		</nav>
	</div>

	{#if activeTab === 'pending'}
		<DisambiguationQueue />
	{:else}
		<!-- Search -->
		<div class="flex gap-2">
			<input
				type="text"
				bind:value={search}
				on:keydown={(e) => e.key === 'Enter' && handleSearch()}
				placeholder="Search..."
				class="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
			/>
			<button
				on:click={handleSearch}
				class="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200"
			>
				Search
			</button>
		</div>

		<!-- List -->
		{#if loading}
			<div class="flex justify-center py-8">
				<div class="spinner"></div>
			</div>
		{:else if currentList.length === 0}
			<div class="text-center py-8 text-slate-500">
				No {activeTab === 'counterparties' ? 'counterparties' : 'persons'} found
			</div>
		{:else}
			<div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
				<table class="w-full">
					<thead class="bg-slate-50 border-b border-slate-200">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Name</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase"
								>Aliases</th
							>
							<th class="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase"
								>Actions</th
							>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-200">
						{#each currentList as entity}
							<tr class="hover:bg-slate-50">
								<td class="px-4 py-3">
									<div class="font-medium text-slate-900">{entity.canonical_name}</div>
									{#if 'short_name' in entity && entity.short_name}
										<div class="text-sm text-slate-500">{entity.short_name}</div>
									{/if}
									{#if 'first_name' in entity && (entity.first_name || entity.last_name)}
										<div class="text-sm text-slate-500">
											{entity.first_name || ''} {entity.last_name || ''}
										</div>
									{/if}
								</td>
								<td class="px-4 py-3">
									<div class="flex flex-wrap gap-1">
										{#each entity.aliases.slice(0, 5) as alias}
											<span class="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded">
												{alias.alias}
											</span>
										{/each}
										{#if entity.aliases.length > 5}
											<span class="px-2 py-0.5 text-xs text-slate-400">
												+{entity.aliases.length - 5} more
											</span>
										{/if}
									</div>
								</td>
								<td class="px-4 py-3 text-right">
									<div class="flex justify-end gap-2">
										<button
											on:click={() => openEditModal(entity)}
											class="text-sm text-primary-600 hover:text-primary-700"
										>
											Edit
										</button>
										<button
											on:click={() => openMergeModal(entity)}
											class="text-sm text-slate-500 hover:text-slate-700"
										>
											Merge
										</button>
										<button
											on:click={() =>
												openDeleteConfirm(
													activeTab === 'counterparties' ? 'counterparty' : 'person',
													entity
												)}
											class="text-sm text-red-600 hover:text-red-700"
										>
											Delete
										</button>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>

<!-- Create Modal -->
{#if showCreateModal}
	<div class="fixed inset-0 z-50 overflow-y-auto">
		<div class="flex min-h-full items-center justify-center p-4">
			<div
				class="fixed inset-0 bg-slate-900/50"
				on:click={() => (showCreateModal = false)}
				on:keydown={(e) => e.key === 'Escape' && (showCreateModal = false)}
				role="button"
				tabindex="0"
			></div>

			<div class="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6">
				<h2 class="text-lg font-semibold text-slate-900">
					Add {activeTab === 'counterparties' ? 'Counterparty' : 'Person'}
				</h2>

				<form on:submit|preventDefault={handleCreate} class="mt-4 space-y-4">
					<div>
						<label for="canonical_name" class="block text-sm font-medium text-slate-700"
							>Canonical Name</label
						>
						<input
							id="canonical_name"
							type="text"
							bind:value={formData.canonical_name}
							required
							class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
						/>
					</div>

					{#if activeTab === 'counterparties'}
						<div>
							<label for="short_name" class="block text-sm font-medium text-slate-700"
								>Short Name</label
							>
							<input
								id="short_name"
								type="text"
								bind:value={formData.short_name}
								class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
							/>
						</div>
					{:else}
						<div class="grid grid-cols-2 gap-4">
							<div>
								<label for="first_name" class="block text-sm font-medium text-slate-700"
									>First Name</label
								>
								<input
									id="first_name"
									type="text"
									bind:value={formData.first_name}
									class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
								/>
							</div>
							<div>
								<label for="last_name" class="block text-sm font-medium text-slate-700"
									>Last Name</label
								>
								<input
									id="last_name"
									type="text"
									bind:value={formData.last_name}
									class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
								/>
							</div>
						</div>
					{/if}

					<div>
						<label for="notes" class="block text-sm font-medium text-slate-700">Notes</label>
						<textarea
							id="notes"
							bind:value={formData.notes}
							rows="2"
							class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
						></textarea>
					</div>

					<div class="flex justify-end gap-3 pt-4">
						<button
							type="button"
							on:click={() => (showCreateModal = false)}
							class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
						>
							Cancel
						</button>
						<button
							type="submit"
							class="px-4 py-2 text-sm text-white bg-primary-600 rounded-lg hover:bg-primary-700"
						>
							Create
						</button>
					</div>
				</form>
			</div>
		</div>
	</div>
{/if}

<!-- Edit Modal -->
{#if showEditModal && editingEntity}
	<div class="fixed inset-0 z-50 overflow-y-auto">
		<div class="flex min-h-full items-center justify-center p-4">
			<div
				class="fixed inset-0 bg-slate-900/50"
				on:click={() => (showEditModal = false)}
				on:keydown={(e) => e.key === 'Escape' && (showEditModal = false)}
				role="button"
				tabindex="0"
			></div>

			<div class="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
				<h2 class="text-lg font-semibold text-slate-900">Edit Entity</h2>

				<form on:submit|preventDefault={handleUpdate} class="mt-4 space-y-4">
					<div>
						<label for="edit_canonical_name" class="block text-sm font-medium text-slate-700"
							>Canonical Name</label
						>
						<input
							id="edit_canonical_name"
							type="text"
							bind:value={formData.canonical_name}
							required
							class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
						/>
					</div>

					{#if !('first_name' in editingEntity)}
						<div>
							<label for="edit_short_name" class="block text-sm font-medium text-slate-700"
								>Short Name</label
							>
							<input
								id="edit_short_name"
								type="text"
								bind:value={formData.short_name}
								class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
							/>
						</div>
					{:else}
						<div class="grid grid-cols-2 gap-4">
							<div>
								<label for="edit_first_name" class="block text-sm font-medium text-slate-700"
									>First Name</label
								>
								<input
									id="edit_first_name"
									type="text"
									bind:value={formData.first_name}
									class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
								/>
							</div>
							<div>
								<label for="edit_last_name" class="block text-sm font-medium text-slate-700"
									>Last Name</label
								>
								<input
									id="edit_last_name"
									type="text"
									bind:value={formData.last_name}
									class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
								/>
							</div>
						</div>
					{/if}

					<div>
						<label for="edit_notes" class="block text-sm font-medium text-slate-700">Notes</label>
						<textarea
							id="edit_notes"
							bind:value={formData.notes}
							rows="2"
							class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
						></textarea>
					</div>

					<!-- Aliases -->
					<div>
						<label class="block text-sm font-medium text-slate-700 mb-2">Aliases</label>
						<div class="flex flex-wrap gap-2 mb-2">
							{#each editingEntity.aliases as alias}
								<span
									class="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 text-slate-700 rounded text-sm"
								>
									{alias.alias}
									{#if alias.alias !== editingEntity.canonical_name}
										<button
											type="button"
											on:click={() => handleRemoveAlias(alias.id)}
											class="p-0.5 text-slate-400 hover:text-slate-600"
										>
											<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M6 18L18 6M6 6l12 12"
												/>
											</svg>
										</button>
									{/if}
								</span>
							{/each}
						</div>
						<div class="flex gap-2">
							<input
								type="text"
								bind:value={formData.newAlias}
								placeholder="Add alias..."
								class="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500"
							/>
							<button
								type="button"
								on:click={handleAddAlias}
								class="px-3 py-2 text-sm text-primary-600 border border-primary-300 rounded-lg hover:bg-primary-50"
							>
								Add
							</button>
						</div>
					</div>

					<div class="flex justify-end gap-3 pt-4">
						<button
							type="button"
							on:click={() => (showEditModal = false)}
							class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
						>
							Cancel
						</button>
						<button
							type="submit"
							class="px-4 py-2 text-sm text-white bg-primary-600 rounded-lg hover:bg-primary-700"
						>
							Save
						</button>
					</div>
				</form>
			</div>
		</div>
	</div>
{/if}

<!-- Merge Modal -->
{#if showMergeModal && mergeTarget}
	{@const isPerson = 'first_name' in mergeTarget}
	{@const mergeOptions = isPerson
		? persons.filter((p) => p.id !== mergeTarget?.id)
		: counterparties.filter((c) => c.id !== mergeTarget?.id)}

	<div class="fixed inset-0 z-50 overflow-y-auto">
		<div class="flex min-h-full items-center justify-center p-4">
			<div
				class="fixed inset-0 bg-slate-900/50"
				on:click={() => (showMergeModal = false)}
				on:keydown={(e) => e.key === 'Escape' && (showMergeModal = false)}
				role="button"
				tabindex="0"
			></div>

			<div class="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6">
				<h2 class="text-lg font-semibold text-slate-900">Merge Entity</h2>
				<p class="mt-2 text-sm text-slate-500">
					Merge "{mergeTarget.canonical_name}" into another entity. All documents and aliases will
					be transferred.
				</p>

				<div class="mt-4 space-y-2 max-h-64 overflow-auto">
					{#each mergeOptions as option}
						<button
							on:click={() => handleMerge(option.id)}
							class="w-full px-3 py-2 text-left text-sm border border-slate-200 rounded-lg hover:bg-slate-50"
						>
							<div class="font-medium">{option.canonical_name}</div>
							<div class="text-xs text-slate-500">
								{option.aliases.length} aliases
							</div>
						</button>
					{/each}
				</div>

				<div class="flex justify-end pt-4">
					<button
						on:click={() => (showMergeModal = false)}
						class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
					>
						Cancel
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- Delete Confirmation -->
{#if showDeleteConfirm && deleteTarget}
	<div class="fixed inset-0 z-50 overflow-y-auto">
		<div class="flex min-h-full items-center justify-center p-4">
			<div
				class="fixed inset-0 bg-slate-900/50"
				on:click={() => (showDeleteConfirm = false)}
				on:keydown={(e) => e.key === 'Escape' && (showDeleteConfirm = false)}
				role="button"
				tabindex="0"
			></div>

			<div class="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6">
				<h2 class="text-lg font-semibold text-slate-900">Delete Entity</h2>
				<p class="mt-2 text-sm text-slate-500">
					Are you sure you want to delete "{deleteTarget.entity.canonical_name}"? This will unlink
					all associated documents.
				</p>

				<div class="mt-6 flex justify-end gap-3">
					<button
						on:click={() => (showDeleteConfirm = false)}
						class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
					>
						Cancel
					</button>
					<button
						on:click={handleDelete}
						class="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700"
					>
						Delete
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
