<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import * as pdfjsLib from 'pdfjs-dist';

	export let url: string;
	export let mimeType: string | null = null;

	// Set worker source - served from static folder
	pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

	let container: HTMLDivElement;
	let canvas: HTMLCanvasElement;
	let loading = true;
	let error = false;
	let errorMessage = '';

	let pdfDoc: pdfjsLib.PDFDocumentProxy | null = null;
	let currentPage = 1;
	let totalPages = 0;
	let scale = 1;
	let rendering = false;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let currentRenderTask: any = null;

	const MIN_SCALE = 0.5;
	const MAX_SCALE = 3;
	const SCALE_STEP = 0.25;

	$: isImage = mimeType?.startsWith('image/') ?? false;
	$: viewUrl = url.includes('?') ? `${url}&download=false` : `${url}?download=false`;
	$: downloadUrl = url.includes('?') ? `${url}&download=true` : `${url}?download=true`;

	async function loadPdf() {
		if (isImage) {
			loading = false;
			return;
		}

		try {
			loading = true;
			error = false;

			const loadingTask = pdfjsLib.getDocument({
				url: viewUrl,
				withCredentials: true
			});

			pdfDoc = await loadingTask.promise;
			totalPages = pdfDoc.numPages;
			currentPage = 1;

			await renderPage();
			loading = false;
		} catch (err) {
			console.error('Failed to load PDF:', err);
			error = true;
			errorMessage = err instanceof Error ? err.message : 'Failed to load PDF';
			loading = false;
		}
	}

	async function renderPage() {
		if (!pdfDoc) return;

		// Wait for canvas to be available
		if (!canvas) {
			await new Promise((resolve) => setTimeout(resolve, 50));
			if (!canvas) return;
		}

		// Cancel any ongoing render
		if (currentRenderTask) {
			try {
				currentRenderTask.cancel();
			} catch {
				// Ignore cancel errors
			}
			currentRenderTask = null;
		}

		if (rendering) return;
		rendering = true;

		try {
			const page = await pdfDoc.getPage(currentPage);

			// Calculate scale to fit container width on mobile, or use fixed scale on desktop
			const containerWidth = container?.clientWidth || 800;
			const viewport = page.getViewport({ scale: 1 });
			const fitScale = (containerWidth - 32) / viewport.width; // 32px for padding
			const actualScale = scale * Math.min(fitScale, 1.5);

			const scaledViewport = page.getViewport({ scale: actualScale });

			// Set canvas dimensions
			const context = canvas.getContext('2d')!;
			canvas.height = scaledViewport.height;
			canvas.width = scaledViewport.width;

			// Render
			currentRenderTask = page.render({
				canvasContext: context,
				viewport: scaledViewport,
				canvas: canvas
			});
			await currentRenderTask.promise;
			currentRenderTask = null;
		} catch (err: unknown) {
			// Ignore cancellation errors
			if (err && typeof err === 'object' && 'name' in err && err.name === 'RenderingCancelledException') {
				return;
			}
			console.error('Failed to render page:', err);
		} finally {
			rendering = false;
		}
	}

	function prevPage() {
		if (currentPage > 1) {
			currentPage--;
			renderPage();
		}
	}

	function nextPage() {
		if (currentPage < totalPages) {
			currentPage++;
			renderPage();
		}
	}

	function zoomIn() {
		if (scale < MAX_SCALE) {
			scale = Math.min(scale + SCALE_STEP, MAX_SCALE);
			renderPage();
		}
	}

	function zoomOut() {
		if (scale > MIN_SCALE) {
			scale = Math.max(scale - SCALE_STEP, MIN_SCALE);
			renderPage();
		}
	}

	function resetZoom() {
		scale = 1;
		renderPage();
	}

	function openInNewTab() {
		window.open(viewUrl, '_blank');
	}

	function download() {
		window.location.href = downloadUrl;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
			prevPage();
		} else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
			nextPage();
		} else if (e.key === '+' || e.key === '=') {
			zoomIn();
		} else if (e.key === '-') {
			zoomOut();
		} else if (e.key === '0') {
			resetZoom();
		}
	}

	function handleImageLoad() {
		loading = false;
	}

	function handleImageError() {
		loading = false;
		error = true;
		errorMessage = 'Failed to load image';
	}

	// Touch swipe handling for mobile
	let touchStartX = 0;
	let touchStartY = 0;

	function handleTouchStart(e: TouchEvent) {
		touchStartX = e.touches[0].clientX;
		touchStartY = e.touches[0].clientY;
	}

	function handleTouchEnd(e: TouchEvent) {
		if (!e.changedTouches[0]) return;

		const touchEndX = e.changedTouches[0].clientX;
		const touchEndY = e.changedTouches[0].clientY;
		const deltaX = touchEndX - touchStartX;
		const deltaY = touchEndY - touchStartY;

		// Only trigger if horizontal swipe is dominant and significant
		if (Math.abs(deltaX) > 50 && Math.abs(deltaX) > Math.abs(deltaY) * 1.5) {
			if (deltaX > 0) {
				prevPage();
			} else {
				nextPage();
			}
		}
	}

	onMount(() => {
		loadPdf();
		window.addEventListener('keydown', handleKeydown);
	});

	onDestroy(() => {
		window.removeEventListener('keydown', handleKeydown);
		if (pdfDoc) {
			pdfDoc.destroy();
		}
	});

	// Re-render on container resize (debounced)
	let resizeObserver: ResizeObserver;
	let resizeTimeout: ReturnType<typeof setTimeout>;
	$: if (container && !isImage) {
		resizeObserver?.disconnect();
		resizeObserver = new ResizeObserver(() => {
			clearTimeout(resizeTimeout);
			resizeTimeout = setTimeout(() => {
				if (!rendering) renderPage();
			}, 150);
		});
		resizeObserver.observe(container);
	}
</script>

<div class="flex flex-col h-full">
	<!-- Toolbar -->
	<div class="flex items-center justify-between p-2 border-b border-slate-200 bg-slate-50 gap-2 flex-wrap">
		<span class="text-sm text-slate-600 hidden sm:block">{isImage ? 'Image' : 'PDF'}</span>

		{#if !isImage && totalPages > 0}
			<!-- Page navigation -->
			<div class="flex items-center gap-1">
				<button
					on:click={prevPage}
					disabled={currentPage <= 1}
					class="p-1.5 rounded hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
					title="Previous page"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
					</svg>
				</button>

				<span class="text-sm text-slate-600 min-w-[4rem] text-center">
					{currentPage} / {totalPages}
				</span>

				<button
					on:click={nextPage}
					disabled={currentPage >= totalPages}
					class="p-1.5 rounded hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
					title="Next page"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
					</svg>
				</button>
			</div>

			<!-- Zoom controls -->
			<div class="flex items-center gap-1">
				<button
					on:click={zoomOut}
					disabled={scale <= MIN_SCALE}
					class="p-1.5 rounded hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
					title="Zoom out"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
					</svg>
				</button>

				<button
					on:click={resetZoom}
					class="text-sm text-slate-600 px-2 py-1 rounded hover:bg-slate-200 min-w-[3.5rem]"
					title="Reset zoom"
				>
					{Math.round(scale * 100)}%
				</button>

				<button
					on:click={zoomIn}
					disabled={scale >= MAX_SCALE}
					class="p-1.5 rounded hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
					title="Zoom in"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
					</svg>
				</button>
			</div>
		{/if}

		<!-- Actions -->
		<div class="flex items-center gap-1">
			<button
				on:click={openInNewTab}
				class="p-1.5 rounded hover:bg-slate-200"
				title="Open in new tab"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
				</svg>
			</button>

			<button
				on:click={download}
				class="p-1.5 rounded hover:bg-slate-200"
				title="Download"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
				</svg>
			</button>
		</div>
	</div>

	<!-- Content -->
	<div
		bind:this={container}
		class="flex-1 relative bg-slate-100 overflow-auto"
		on:touchstart={handleTouchStart}
		on:touchend={handleTouchEnd}
	>
		{#if loading}
			<div class="absolute inset-0 flex items-center justify-center bg-slate-100 z-10">
				<div class="spinner"></div>
			</div>
		{/if}

		{#if error}
			<div class="flex items-center justify-center h-full p-4">
				<div class="text-center">
					<svg class="mx-auto h-12 w-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
					</svg>
					<p class="mt-2 text-sm text-slate-500">Failed to load {isImage ? 'image' : 'PDF'}</p>
					<p class="mt-1 text-xs text-slate-400">{errorMessage}</p>
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
				class="max-w-full h-auto mx-auto"
				on:load={handleImageLoad}
				on:error={handleImageError}
			/>
		{:else}
			<div class="flex justify-center p-4">
				<canvas bind:this={canvas} class="shadow-lg"></canvas>
			</div>
		{/if}
	</div>
</div>
