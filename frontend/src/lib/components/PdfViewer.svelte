<script lang="ts">
	import { onMount } from 'svelte';

	export let url: string;
	export let mimeType: string | null = null;

	let iframe: HTMLIFrameElement;
	let loading = true;
	let error = false;

	$: isImage = mimeType?.startsWith('image/') ?? false;

	// Ensure URL doesn't have download=true for viewing
	// #navpanes=0 hides the page thumbnails sidebar
	$: viewUrl = isImage
		? (url.includes('?') ? `${url}&download=false` : `${url}?download=false`)
		: (url.includes('?') ? `${url}&download=false` : `${url}?download=false`) + '#navpanes=0';
	$: downloadUrl = url.includes('?') ? `${url}&download=true` : `${url}?download=true`;

	function handleLoad() {
		loading = false;
	}

	function handleError() {
		loading = false;
		error = true;
	}

	function openInNewTab() {
		window.open(viewUrl, '_blank');
	}

	function download() {
		window.location.href = downloadUrl;
	}

	onMount(() => {
		// Fallback timeout for loading state
		const timeout = setTimeout(() => {
			loading = false;
		}, 5000);
		return () => clearTimeout(timeout);
	});
</script>

<div class="flex flex-col h-full">
	<!-- Toolbar -->
	<div class="flex items-center justify-between p-3 border-b border-slate-200 bg-slate-50">
		<span class="text-sm text-slate-600">{isImage ? 'Image Viewer' : 'PDF Viewer'}</span>

		<div class="flex items-center gap-2">
			<button
				on:click={openInNewTab}
				class="p-2 rounded hover:bg-slate-200"
				title="Open in new tab"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
				</svg>
			</button>

			<button
				on:click={download}
				class="p-2 rounded hover:bg-slate-200"
				title="Download"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
				</svg>
			</button>
		</div>
	</div>

	<!-- PDF Container -->
	<div class="flex-1 relative bg-slate-100">
		{#if loading}
			<div class="absolute inset-0 flex items-center justify-center bg-slate-100 z-10">
				<div class="spinner"></div>
			</div>
		{/if}

		{#if error}
			<div class="flex items-center justify-center h-full">
				<div class="text-center">
					<svg class="mx-auto h-12 w-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
					</svg>
					<p class="mt-2 text-sm text-slate-500">Failed to load {isImage ? 'image' : 'PDF'}</p>
					<button
						on:click={openInNewTab}
						class="mt-4 text-sm text-blue-600 hover:text-blue-800"
					>
						Try opening in new tab
					</button>
				</div>
			</div>
		{:else if isImage}
			<img
				src={viewUrl}
				alt="Document"
				class="w-full h-full object-contain"
				on:load={handleLoad}
				on:error={handleError}
			/>
		{:else}
			<iframe
				bind:this={iframe}
				src={viewUrl}
				class="w-full h-full border-0"
				title="PDF document"
				on:load={handleLoad}
				on:error={handleError}
			></iframe>
		{/if}
	</div>
</div>
