<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { Document } from '$lib/api';

	interface Message {
		role: 'user' | 'assistant';
		content: string;
		sources?: Document[];
	}

	export let messages: Message[] = [];
	export let loading = false;
	export let disabled = false;

	const dispatch = createEventDispatcher<{
		submit: string;
		clear: void;
	}>();

	let input = '';

	function handleSubmit() {
		if (!input.trim() || loading || disabled) return;
		dispatch('submit', input.trim());
		input = '';
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			handleSubmit();
		}
	}
</script>

<div class="flex flex-col h-full bg-white rounded-xl shadow-sm overflow-hidden">
	<!-- Messages -->
	<div class="flex-1 overflow-y-auto p-4 space-y-4">
		{#if messages.length === 0}
			<div class="text-center py-8 text-slate-400">
				<p>Ask a question about your documents</p>
			</div>
		{:else}
			{#each messages as message}
				<div class="flex gap-3 {message.role === 'user' ? 'justify-end' : ''}">
					{#if message.role === 'assistant'}
						<div class="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
							<svg class="w-4 h-4 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
							</svg>
						</div>
					{/if}

					<div class="max-w-[80%]">
						<div
							class="px-4 py-2 rounded-xl text-sm
								{message.role === 'user'
								? 'bg-primary-600 text-white'
								: 'bg-slate-100 text-slate-900'}"
						>
							<p class="whitespace-pre-wrap">{message.content}</p>
						</div>

						{#if message.sources && message.sources.length > 0}
							<div class="mt-2 text-xs text-slate-500">
								Sources: {message.sources.map(s => s.filename).join(', ')}
							</div>
						{/if}
					</div>

					{#if message.role === 'user'}
						<div class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
							<svg class="w-4 h-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
							</svg>
						</div>
					{/if}
				</div>
			{/each}

			{#if loading}
				<div class="flex gap-3">
					<div class="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
						<div class="spinner w-4 h-4"></div>
					</div>
					<div class="px-4 py-2 bg-slate-100 rounded-xl text-sm text-slate-500">
						Thinking...
					</div>
				</div>
			{/if}
		{/if}
	</div>

	<!-- Input -->
	<div class="border-t border-slate-200 p-3">
		<form on:submit|preventDefault={handleSubmit} class="flex gap-2">
			<input
				type="text"
				bind:value={input}
				on:keydown={handleKeydown}
				placeholder="Ask a question..."
				class="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
				disabled={loading || disabled}
			/>
			<button
				type="submit"
				disabled={!input.trim() || loading || disabled}
				class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
			>
				Send
			</button>
		</form>
	</div>
</div>
