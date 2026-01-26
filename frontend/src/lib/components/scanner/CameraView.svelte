<script lang="ts">
	import { onMount, onDestroy, createEventDispatcher } from 'svelte';
	import { browser } from '$app/environment';
	import {
		startCamera,
		switchCamera,
		stopAllTracks,
		captureImage,
		processImageFile,
		isCameraSupported,
		getVideoDevices,
		type CameraStream
	} from '$lib/services/camera';

	const dispatch = createEventDispatcher<{
		capture: Blob;
		error: string;
	}>();

	let videoElement: HTMLVideoElement;
	let fileInput: HTMLInputElement;
	let cameraStream: CameraStream | null = null;
	let hasMultipleCameras = false;
	let isCapturing = false;
	let permissionDenied = false;
	let cameraError: string | null = null;
	let useFallback = false;

	onMount(async () => {
		if (!browser) return;

		// Check if camera is supported
		if (!isCameraSupported()) {
			useFallback = true;
			return;
		}

		// Start camera first (to get permission)
		await initCamera();

		// Handle visibility changes
		document.addEventListener('visibilitychange', handleVisibilityChange);
	});

	onDestroy(() => {
		if (browser) {
			stopAllTracks(cameraStream?.stream ?? null);
			document.removeEventListener('visibilitychange', handleVisibilityChange);
		}
	});

	async function initCamera() {
		try {
			cameraError = null;
			permissionDenied = false;

			cameraStream = await startCamera('environment');

			if (videoElement && cameraStream) {
				videoElement.srcObject = cameraStream.stream;
			}

			// Re-check for multiple cameras after permission granted
			// (enumerateDevices often returns empty before permission)
			try {
				const devices = await getVideoDevices();
				hasMultipleCameras = devices.length > 1;
			} catch {
				// Ignore - will still work with single camera
			}
		} catch (error) {
			console.error('Camera init error:', error);

			if (error instanceof Error) {
				if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
					permissionDenied = true;
					cameraError = 'Camera access denied. Please allow camera access in your browser settings.';
				} else if (error.name === 'NotFoundError') {
					cameraError = 'No camera found on this device.';
					useFallback = true;
				} else {
					cameraError = error.message || 'Failed to access camera';
					useFallback = true;
				}
			}

			dispatch('error', cameraError || 'Camera error');
		}
	}

	// Track the last requested facing mode for restart after visibility change
	let lastRequestedFacingMode: 'user' | 'environment' = 'environment';

	async function handleVisibilityChange() {
		if (!browser) return;

		if (document.hidden) {
			// Fully stop camera when tab is hidden (iOS keeps LED on if only disabled)
			if (cameraStream) {
				lastRequestedFacingMode = cameraStream.requestedFacingMode;
				stopAllTracks(cameraStream.stream);
				cameraStream = null;
				if (videoElement) {
					videoElement.srcObject = null;
				}
			}
		} else {
			// Restart camera when tab is visible
			if (!cameraStream && !useFallback && !permissionDenied) {
				try {
					cameraStream = await startCamera(lastRequestedFacingMode);
					if (videoElement && cameraStream) {
						videoElement.srcObject = cameraStream.stream;
					}
					// Clear any previous error on successful restart
					cameraError = null;
				} catch (error) {
					console.error('Failed to restart camera:', error);
					// Show error UI so user can tap "Try Again"
					cameraError = 'Camera disconnected. Tap to reconnect.';
				}
			}
		}
	}

	async function handleCapture() {
		if (isCapturing || !videoElement) return;

		isCapturing = true;

		try {
			const blob = await captureImage(videoElement);
			dispatch('capture', blob);
		} catch (error) {
			console.error('Capture error:', error);
			dispatch('error', 'Failed to capture image');
		} finally {
			isCapturing = false;
		}
	}

	async function handleSwitchCamera() {
		if (!cameraStream) return;

		stopAllTracks(cameraStream.stream);

		try {
			cameraStream = await switchCamera(cameraStream.requestedFacingMode);

			if (videoElement && cameraStream) {
				videoElement.srcObject = cameraStream.stream;
			}
		} catch (error) {
			console.error('Switch camera error:', error);
			// Try to restore original camera
			await initCamera();
		}
	}

	async function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];

		if (!file) return;

		try {
			const blob = await processImageFile(file);
			dispatch('capture', blob);
		} catch (error) {
			console.error('File processing error:', error);
			dispatch('error', 'Failed to process image file');
		}

		// Reset input
		input.value = '';
	}

	function openFilePicker() {
		fileInput?.click();
	}

	export function stopCamera() {
		stopAllTracks(cameraStream?.stream ?? null);
		cameraStream = null;
	}
</script>

<div class="relative w-full h-full bg-black flex flex-col">
	{#if useFallback || permissionDenied}
		<!-- Fallback: File picker -->
		<div class="flex-1 flex flex-col items-center justify-center p-8 text-center">
			{#if permissionDenied}
				<svg class="w-16 h-16 text-red-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
					/>
				</svg>
				<p class="text-white text-lg mb-2">Camera Access Denied</p>
				<p class="text-gray-400 text-sm mb-6">
					Please allow camera access in your browser settings, or use the file picker below.
				</p>
			{:else}
				<svg class="w-16 h-16 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
					/>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
					/>
				</svg>
				<p class="text-white text-lg mb-2">Camera Not Available</p>
				<p class="text-gray-400 text-sm mb-6">Use the button below to select a photo from your device.</p>
			{/if}

			<button
				type="button"
				on:click={openFilePicker}
				class="px-6 py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors"
			>
				Choose Photo
			</button>
		</div>
	{:else if cameraError}
		<!-- Error state -->
		<div class="flex-1 flex flex-col items-center justify-center p-8 text-center">
			<svg class="w-16 h-16 text-yellow-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<p class="text-white text-lg mb-2">Camera Error</p>
			<p class="text-gray-400 text-sm mb-6">{cameraError}</p>
			<button
				type="button"
				on:click={initCamera}
				class="px-6 py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors"
			>
				Try Again
			</button>
		</div>
	{:else}
		<!-- Camera view -->
		<div class="flex-1 relative overflow-hidden">
			<video
				bind:this={videoElement}
				autoplay
				playsinline
				muted
				class="absolute inset-0 w-full h-full object-cover"
			/>

			<!-- Camera switch button -->
			{#if hasMultipleCameras}
				<button
					type="button"
					on:click={handleSwitchCamera}
					class="absolute top-4 right-4 p-3 bg-black/50 rounded-full text-white hover:bg-black/70 transition-colors"
					aria-label="Switch camera"
				>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
						/>
					</svg>
				</button>
			{/if}
		</div>

		<!-- Capture button -->
		<div class="flex justify-center items-center py-6 bg-black">
			<button
				type="button"
				on:click={handleCapture}
				disabled={isCapturing}
				class="w-16 h-16 rounded-full border-4 border-white bg-transparent hover:bg-white/20 transition-colors disabled:opacity-50 flex items-center justify-center"
				aria-label="Capture photo"
			>
				<span class="w-12 h-12 rounded-full bg-white" />
			</button>
		</div>
	{/if}

	<!-- Hidden file input for fallback -->
	<input
		bind:this={fileInput}
		type="file"
		accept="image/jpeg,image/png,image/heic,image/heif"
		capture="environment"
		class="hidden"
		on:change={handleFileSelect}
	/>
</div>
