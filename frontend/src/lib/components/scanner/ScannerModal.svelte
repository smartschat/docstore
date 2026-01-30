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
		resetScanner,
		openScanner
	} from '$lib/stores/scanner';
	import { generatePdf, pdfBlobToFile } from '$lib/services/pdf-generator';

	export let open = false;

	const dispatch = createEventDispatcher<{
		close: void;
		upload: { file: File; onSuccess: () => void; onError: (error: string) => void };
	}>();

	let cameraView: CameraView;
	let modalElement: HTMLDivElement;
	let abortController: AbortController | null = null;

	// Handle keyboard events (escape and focus trap)
	function handleKeydown(event: KeyboardEvent) {
		if (!open) return;

		if (event.key === 'Escape') {
			handleClose();
		} else if (event.key === 'Tab') {
			handleFocusTrap(event);
		}
	}

	onMount(() => {
		if (browser) {
			document.addEventListener('keydown', handleKeydown);
		}
	});

	onDestroy(() => {
		if (browser) {
			abortController?.abort();
			document.removeEventListener('keydown', handleKeydown);
			resetScanner();
		}
	});

	// Initialize scanner when modal opens, cleanup when closed
	$: if (open) {
		abortController = null;
		openScanner();
	} else if (browser) {
		abortController?.abort();
		resetScanner();
	}

	// Focus modal when opened
	$: if (open && modalElement) {
		modalElement.focus();
	}

	// Focus trap - keep focus within modal
	function handleFocusTrap(event: KeyboardEvent) {
		if (event.key !== 'Tab' || !modalElement) return;

		// Query focusable elements and filter out disabled and hidden ones
		const allFocusable = modalElement.querySelectorAll<HTMLElement>(
			'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
		);
		const focusableElements = Array.from(allFocusable).filter((el) => {
			// Filter out disabled elements
			if (el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true') {
				return false;
			}
			// Filter out hidden elements (display:none, visibility:hidden, or zero size)
			if (el.offsetParent === null && el.offsetWidth === 0 && el.offsetHeight === 0) {
				return false;
			}
			return true;
		});

		if (focusableElements.length === 0) return;

		const firstElement = focusableElements[0];
		const lastElement = focusableElements[focusableElements.length - 1];
		const activeIndex = focusableElements.indexOf(document.activeElement as HTMLElement);

		// If active element is not in the list (e.g., on modal container), redirect
		if (activeIndex === -1) {
			event.preventDefault();
			if (event.shiftKey) {
				lastElement.focus();
			} else {
				firstElement.focus();
			}
			return;
		}

		if (event.shiftKey) {
			// Shift+Tab: if on first element, wrap to last
			if (activeIndex === 0) {
				event.preventDefault();
				lastElement.focus();
			}
		} else {
			// Tab: if on last element, wrap to first
			if (activeIndex === focusableElements.length - 1) {
				event.preventDefault();
				firstElement.focus();
			}
		}
	}

	function handleClose() {
		abortController?.abort();
		cameraView?.stopCamera();
		resetScanner();
		dispatch('close');
	}

	function handleCapture(event: CustomEvent<Blob>) {
		const blob = event.detail;
		const page = addPage(blob);
		// Only advance to preview if page was added (null means at limit)
		if (page) {
			// Clear any previous error on successful capture
			scannerError.set(null);
			goToPreview();
		}
	}

	function handleCameraError(event: CustomEvent<string>) {
		console.error('Camera error:', event.detail);
		// Show error to user (CameraView will show fallback file picker)
		scannerError.set(event.detail);
	}

	function handleCameraReady() {
		// Clear any camera error when camera successfully starts/restarts
		scannerError.set(null);
	}

	function handleRetake() {
		removeLastPage();
		// Clear any error when going back to retake
		scannerError.set(null);
		goToCamera();
	}

	function handleAddPage() {
		// Clear any error when going to add more pages
		scannerError.set(null);
		goToCamera();
	}

	function handleDone() {
		goToReview();
	}

	async function handleSave() {
		if ($pageCount === 0) return;

		scannerError.set(null);
		setGenerating();

		abortController = new AbortController();

		try {
			const blobs = getPageBlobs();
			const pdfBlob = await generatePdf(blobs, {
				onProgress: (current, total) => {
					generationProgress.set({ current, total });
				},
				signal: abortController.signal
			});

			const file = pdfBlobToFile(pdfBlob);

			// Dispatch upload event - parent will close modal immediately and handle upload via toast
			dispatch('upload', {
				file,
				onSuccess: () => {
					if (!open) return;
					clearAllPages();
					handleClose();
				},
				onError: (error: string) => {
					// Errors now handled via toast in parent
				}
			});
		} catch (error) {
			// Don't show error if aborted (user closed modal)
			if (error instanceof DOMException && error.name === 'AbortError') {
				return;
			}
			console.error('PDF generation error:', error);
			scannerError.set('Failed to generate PDF. Please try again.');
			goToReview();
		} finally {
			abortController = null;
		}
	}
</script>

{#if open}
	<!-- Backdrop -->
	<div class="fixed inset-0 z-[60] bg-black/80" aria-hidden="true" />

	<!-- Modal -->
	<div
		bind:this={modalElement}
		class="fixed inset-0 z-[60] flex items-center justify-center p-0 sm:p-4"
		role="dialog"
		aria-modal="true"
		aria-label="Document Scanner"
		tabindex="-1"
	>
		<div class="w-full h-full sm:max-w-2xl sm:max-h-[90vh] sm:h-[80vh] sm:rounded-xl bg-white overflow-hidden flex flex-col shadow-2xl">
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
			<div class="flex-1 overflow-hidden relative">
				{#if $scannerState === 'camera' || $scannerState === 'idle'}
					<CameraView
						bind:this={cameraView}
						on:capture={handleCapture}
						on:error={handleCameraError}
						on:ready={handleCameraReady}
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
