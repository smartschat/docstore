<script lang="ts">
	import { toasts, type Toast } from '$lib/stores/toast';
	import { fly } from 'svelte/transition';

	function getIcon(type: Toast['type']) {
		switch (type) {
			case 'success':
				return '✓';
			case 'error':
				return '✕';
			case 'info':
				return 'ℹ';
			case 'loading':
				return null; // Will show spinner
		}
	}

	function getClasses(type: Toast['type']) {
		switch (type) {
			case 'success':
				return 'bg-green-600 text-white';
			case 'error':
				return 'bg-red-600 text-white';
			case 'info':
				return 'bg-slate-700 text-white';
			case 'loading':
				return 'bg-slate-700 text-white';
		}
	}
</script>

<div class="fixed bottom-20 sm:bottom-4 right-4 z-[70] flex flex-col gap-2 max-w-sm">
	{#each $toasts as toast (toast.id)}
		<div
			class="flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg {getClasses(toast.type)}"
			transition:fly={{ x: 100, duration: 200 }}
			role="alert"
		>
			{#if toast.type === 'loading'}
				<div class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin flex-shrink-0"></div>
			{:else}
				<span class="text-lg flex-shrink-0">{getIcon(toast.type)}</span>
			{/if}
			<p class="text-sm font-medium">{toast.message}</p>
			{#if toast.type !== 'loading'}
				<button
					on:click={() => toasts.remove(toast.id)}
					class="ml-auto p-1 hover:bg-white/20 rounded transition-colors flex-shrink-0"
					aria-label="Dismiss"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			{/if}
		</div>
	{/each}
</div>
