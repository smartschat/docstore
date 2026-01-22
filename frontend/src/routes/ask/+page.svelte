<script lang="ts">
	import { askQuestion, type QuestionResponse, type Document } from '$lib/api';
	import DocumentCard from '$components/DocumentCard.svelte';

	interface Message {
		role: 'user' | 'assistant';
		content: string;
		sources?: Document[];
	}

	let messages: Message[] = [];
	let question = '';
	let loading = false;
	let error = '';

	async function handleSubmit() {
		if (!question.trim() || loading) return;

		const userQuestion = question.trim();
		question = '';
		error = '';

		messages = [...messages, { role: 'user', content: userQuestion }];
		loading = true;

		try {
			const response = await askQuestion(userQuestion);

			messages = [
				...messages,
				{
					role: 'assistant',
					content: response.answer,
					sources: response.sources
				}
			];
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to get answer';
			messages = [
				...messages,
				{
					role: 'assistant',
					content: 'Sorry, I encountered an error while processing your question. Please try again.'
				}
			];
		} finally {
			loading = false;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			handleSubmit();
		}
	}

	function clearChat() {
		messages = [];
		error = '';
	}
</script>

<svelte:head>
	<title>Ask Questions - DocStore</title>
</svelte:head>

<div class="max-w-4xl mx-auto">
	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold text-slate-900">Ask Questions</h1>
			<p class="mt-1 text-sm text-slate-500">
				Ask questions about your documents using AI
			</p>
		</div>

		{#if messages.length > 0}
			<button
				on:click={clearChat}
				class="text-sm text-slate-500 hover:text-slate-700"
			>
				Clear chat
			</button>
		{/if}
	</div>

	<!-- Chat Container -->
	<div class="bg-white rounded-xl shadow-sm overflow-hidden">
		<!-- Messages -->
		<div class="h-[500px] overflow-y-auto p-6 space-y-6">
			{#if messages.length === 0}
				<div class="text-center py-12">
					<svg
						class="mx-auto h-12 w-12 text-slate-300"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
						/>
					</svg>
					<p class="mt-4 text-slate-500">Ask a question about your documents</p>
					<div class="mt-4 space-y-2 text-sm text-slate-400">
						<p>Try asking:</p>
						<ul class="space-y-1">
							<li>"What invoices do I have from last month?"</li>
							<li>"How much did I spend on groceries?"</li>
							<li>"What is the total amount on my electricity bill?"</li>
						</ul>
					</div>
				</div>
			{:else}
				{#each messages as message}
					<div class="flex gap-4 {message.role === 'user' ? 'justify-end' : ''}">
						{#if message.role === 'assistant'}
							<div class="flex-shrink-0 w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
								<svg class="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
								</svg>
							</div>
						{/if}

						<div class="flex-1 max-w-2xl {message.role === 'user' ? 'text-right' : ''}">
							<div
								class="inline-block px-4 py-3 rounded-xl text-sm
									{message.role === 'user'
									? 'bg-primary-600 text-white'
									: 'bg-slate-100 text-slate-900'}"
							>
								<p class="whitespace-pre-wrap">{message.content}</p>
							</div>

							{#if message.sources && message.sources.length > 0}
								<div class="mt-4 space-y-2">
									<p class="text-xs text-slate-500 font-medium">Sources:</p>
									{#each message.sources as source}
										<DocumentCard document={source} compact={true} />
									{/each}
								</div>
							{/if}
						</div>

						{#if message.role === 'user'}
							<div class="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center">
								<svg class="w-5 h-5 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
								</svg>
							</div>
						{/if}
					</div>
				{/each}

				{#if loading}
					<div class="flex gap-4">
						<div class="flex-shrink-0 w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
							<div class="spinner w-4 h-4"></div>
						</div>
						<div class="flex-1">
							<div class="inline-block px-4 py-3 bg-slate-100 rounded-xl text-sm text-slate-500">
								Thinking...
							</div>
						</div>
					</div>
				{/if}
			{/if}
		</div>

		<!-- Input -->
		<div class="border-t border-slate-200 p-4">
			{#if error}
				<div class="mb-3 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
					{error}
				</div>
			{/if}

			<form on:submit|preventDefault={handleSubmit} class="flex gap-3">
				<textarea
					bind:value={question}
					on:keydown={handleKeydown}
					placeholder="Ask a question about your documents..."
					rows="1"
					class="flex-1 px-4 py-3 border border-slate-300 rounded-xl resize-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
					disabled={loading}
				></textarea>

				<button
					type="submit"
					disabled={!question.trim() || loading}
					class="px-6 py-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
				>
					{#if loading}
						<div class="spinner w-5 h-5"></div>
					{:else}
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
						</svg>
					{/if}
				</button>
			</form>
		</div>
	</div>
</div>
