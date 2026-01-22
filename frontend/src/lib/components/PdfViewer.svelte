<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	export let url: string;

	let container: HTMLDivElement;
	let canvas: HTMLCanvasElement;
	let pdfDoc: any = null;
	let currentPage = 1;
	let totalPages = 0;
	let scale = 1.0;
	let loading = true;
	let error = '';

	onMount(async () => {
		try {
			// Dynamically import pdfjs
			const pdfjsLib = await import('pdfjs-dist');

			// Set worker source
			pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

			// Load the PDF
			const loadingTask = pdfjsLib.getDocument({
				url,
				withCredentials: true
			});

			pdfDoc = await loadingTask.promise;
			totalPages = pdfDoc.numPages;

			await renderPage(currentPage);
		} catch (e) {
			console.error('Failed to load PDF:', e);
			error = 'Failed to load PDF. The document may not be available.';
		} finally {
			loading = false;
		}
	});

	async function renderPage(pageNum: number) {
		if (!pdfDoc || !canvas) return;

		const page = await pdfDoc.getPage(pageNum);
		const viewport = page.getViewport({ scale });

		canvas.height = viewport.height;
		canvas.width = viewport.width;

		const context = canvas.getContext('2d');
		if (!context) return;

		await page.render({
			canvasContext: context,
			viewport
		}).promise;
	}

	function prevPage() {
		if (currentPage > 1) {
			currentPage--;
			renderPage(currentPage);
		}
	}

	function nextPage() {
		if (currentPage < totalPages) {
			currentPage++;
			renderPage(currentPage);
		}
	}

	function zoomIn() {
		scale = Math.min(scale + 0.25, 3.0);
		renderPage(currentPage);
	}

	function zoomOut() {
		scale = Math.max(scale - 0.25, 0.5);
		renderPage(currentPage);
	}

	function resetZoom() {
		scale = 1.0;
		renderPage(currentPage);
	}
</script>

<div bind:this={container} class="flex flex-col h-full">
	<!-- Toolbar -->
	<div class="flex items-center justify-between p-3 border-b border-slate-200 bg-slate-50">
		<div class="flex items-center gap-2">
			<button
				on:click={prevPage}
				disabled={currentPage <= 1}
				class="p-2 rounded hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
				title="Previous page"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
				</svg>
			</button>

			<span class="text-sm text-slate-600">
				{currentPage} / {totalPages || '?'}
			</span>

			<button
				on:click={nextPage}
				disabled={currentPage >= totalPages}
				class="p-2 rounded hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
				title="Next page"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
				</svg>
			</button>
		</div>

		<div class="flex items-center gap-2">
			<button
				on:click={zoomOut}
				disabled={scale <= 0.5}
				class="p-2 rounded hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
				title="Zoom out"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
				</svg>
			</button>

			<button on:click={resetZoom} class="text-sm text-slate-600 hover:text-slate-900" title="Reset zoom">
				{Math.round(scale * 100)}%
			</button>

			<button
				on:click={zoomIn}
				disabled={scale >= 3.0}
				class="p-2 rounded hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
				title="Zoom in"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
				</svg>
			</button>
		</div>
	</div>

	<!-- Canvas Container -->
	<div class="flex-1 overflow-auto bg-slate-100 p-4">
		{#if loading}
			<div class="flex items-center justify-center h-64">
				<div class="spinner"></div>
			</div>
		{:else if error}
			<div class="flex items-center justify-center h-64">
				<div class="text-center">
					<svg class="mx-auto h-12 w-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
					</svg>
					<p class="mt-2 text-sm text-slate-500">{error}</p>
				</div>
			</div>
		{:else}
			<div class="flex justify-center">
				<canvas bind:this={canvas} class="pdf-page bg-white"></canvas>
			</div>
		{/if}
	</div>
</div>
