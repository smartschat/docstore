<script lang="ts">
	import { createEventDispatcher, onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import CameraView from './CameraView.svelte';
	import PagePreview from './PagePreview.svelte';
	import PageReview from './PageReview.svelte';
	import {
		scannerState,
		pages,
		currentPreviewPage,
		generationProgress,
		scannerError,
		pageCount,
		addPage,
		removeLastPage,
		clearAllPages,
		getPageBlobs,
		goToPreview,
		goToReview,
		goToCamera,
		setGenerating,
		setUploading,
		resetScanner
	} from '$lib/stores/scanner';
	import { generatePdf, pdfBlobToFile } from '$lib/services/pdf-generator';

	export let open = false;

	const dispatch = createEventDispatcher<{
		close: void;
		upload: { file: File; onSuccess: () => void; onError: (error: string) => void };
	}>();

	let cameraView: CameraView;
	let modalElement: HTMLDivElement;

	// Handle escape key
	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' && open) {
			handleClose();
		}
	}

	onMount(() => {
		if (browser) {
			document.addEventListener('keydown', handleKeydown);
		}
	});

	onDestroy(() => {
		if (browser) {
			document.removeEventListener('keydown', handleKeydown);
			// Clean up scanner state and object URLs on component destroy
			resetScanner();
		}
	});

	// Also reset when modal is closed externally (open prop changes to false)
	$: if (!open && browser) {
		resetScanner();
	}

	// Focus trap
	$: if (open && modalElement) {
		modalElement.focus();
	}

	function handleClose() {
		// Stop camera
		cameraView?.stopCamera();
		// Clean up state
		resetScanner();
		dispatch('close');
	}

	function handleCapture(event: CustomEvent<Blob>) {
		const blob = event.detail;
		addPage(blob);
		goToPreview();
	}

	function handleCameraError(event: CustomEvent<string>) {
		console.error('Camera error:', event.detail);
		// Still allow using file picker fallback
	}

	function handleRetake() {
		removeLastPage();
		goToCamera();
	}

	function handleAddPage() {
		goToCamera();
	}

	function handleDone() {
		goToReview();
	}

	async function handleSave() {
		if ($pageCount === 0) return;

		setGenerating();

		try {
			const blobs = getPageBlobs();
			const pdfBlob = await generatePdf(blobs, {
				onProgress: (current, total) => {
					generationProgress.set({ current, total });
				}
			});

			setUploading();

			const file = pdfBlobToFile(pdfBlob);

			// Dispatch upload event and wait for result via callbacks
			dispatch('upload', {
				file,
				onSuccess: () => {
					// Clean up pages and close only on success
					clearAllPages();
					handleClose();
				},
				onError: (error: string) => {
					// Show error and allow retry
					scannerError.set(error || 'Upload failed. Please try again.');
					goToReview();
				}
			});
		} catch (error) {
			console.error('PDF generation error:', error);
			scannerError.set('Failed to generate PDF. Please try again.');
			goToReview();
		}
	}
</script>

{#if open}
	<!-- Backdrop -->
	<div class="fixed inset-0 z-50 bg-black/80" aria-hidden="true" />

	<!-- Modal -->
	<div
		bind:this={modalElement}
		class="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-4"
		role="dialog"
		aria-modal="true"
		aria-label="Document Scanner"
		tabindex="-1"
	>
		<div class="w-full h-full sm:max-w-2xl sm:max-h-[90vh] sm:h-auto sm:rounded-xl bg-white overflow-hidden flex flex-col shadow-2xl">
			<!-- Header -->
			<div class="flex items-center justify-between px-4 py-3 bg-slate-900 text-white">
				<h2 class="text-lg font-semibold">
					{#if $scannerState === 'camera'}
						Scan Document
					{:else if $scannerState === 'preview'}
						Preview
					{:else if $scannerState === 'review'}
						Review Pages
					{:else if $scannerState === 'generating'}
						Creating PDF...
					{:else if $scannerState === 'uploading'}
						Uploading...
					{:else}
						Scanner
					{/if}
				</h2>

				<button
					type="button"
					on:click={handleClose}
					class="p-2 -mr-2 text-white/80 hover:text-white transition-colors"
					aria-label="Close scanner"
				>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			<!-- Content -->
			<div class="flex-1 overflow-hidden">
				{#if $scannerState === 'camera' || $scannerState === 'idle'}
					<CameraView
						bind:this={cameraView}
						on:capture={handleCapture}
						on:error={handleCameraError}
					/>
				{:else if $scannerState === 'preview' && $currentPreviewPage}
					<PagePreview
						imageUrl={$currentPreviewPage.objectUrl}
						on:retake={handleRetake}
						on:addPage={handleAddPage}
						on:done={handleDone}
					/>
				{:else if $scannerState === 'review'}
					<PageReview on:addPage={handleAddPage} on:save={handleSave} />
				{:else if $scannerState === 'generating' || $scannerState === 'uploading'}
					<div class="flex flex-col items-center justify-center h-full p-8">
						<!-- Spinner -->
						<div class="w-16 h-16 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mb-6" />

						<p class="text-lg font-medium text-slate-900 mb-2">
							{#if $scannerState === 'generating'}
								Creating PDF...
							{:else}
								Uploading document...
							{/if}
						</p>

						{#if $scannerState === 'generating' && $generationProgress.total > 0}
							<p class="text-sm text-slate-500">
								Processing page {$generationProgress.current} of {$generationProgress.total}
							</p>

							<!-- Progress bar -->
							<div class="w-full max-w-xs mt-4 h-2 bg-slate-200 rounded-full overflow-hidden">
								<div
									class="h-full bg-primary-600 transition-all duration-300"
									style="width: {($generationProgress.current / $generationProgress.total) * 100}%"
								/>
							</div>
						{/if}
					</div>
				{/if}

				<!-- Error message -->
				{#if $scannerError}
					<div class="absolute bottom-4 left-4 right-4 p-3 bg-red-50 border border-red-200 rounded-lg">
						<p class="text-sm text-red-800">{$scannerError}</p>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
