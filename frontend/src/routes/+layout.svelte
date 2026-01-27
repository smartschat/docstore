<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { isAuthenticated } from '$stores/documents';
	import { logout } from '$lib/api';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';

	// Register service worker for PWA support
	onMount(() => {
		if (browser && 'serviceWorker' in navigator) {
			navigator.serviceWorker.register('/sw.js').catch((error) => {
				console.warn('Service worker registration failed:', error);
			});
		}
	});

	const navItems = [
		{ href: '/', label: 'Dashboard', icon: 'home' },
		{ href: '/documents', label: 'Documents', icon: 'folder' },
		{ href: '/entities', label: 'Entities', icon: 'users' },
		{ href: '/ask', label: 'Ask', icon: 'chat' }
	];

	async function handleLogout() {
		await logout();
		$isAuthenticated = false;
		goto('/login');
	}
</script>

{#if $page.url.pathname === '/login'}
	<slot />
{:else}
	<div class="min-h-screen bg-slate-50">
		<!-- Header -->
		<header class="bg-white border-b border-slate-200 sticky top-0 z-50">
			<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
				<div class="flex justify-between items-center h-16">
					<div class="flex items-center gap-8">
						<a href="/" class="text-xl font-bold text-primary-600">DocStore</a>

						<nav class="hidden md:flex gap-1">
							{#each navItems as item}
								<a
									href={item.href}
									class="px-3 py-2 rounded-md text-sm font-medium transition-colors
										{$page.url.pathname === item.href ||
									($page.url.pathname.startsWith(item.href) && item.href !== '/')
										? 'bg-primary-50 text-primary-700'
										: 'text-slate-600 hover:bg-slate-100'}"
								>
									{item.label}
								</a>
							{/each}
						</nav>
					</div>

					<div class="flex items-center gap-4">
						<a
							href="/documents?scan=true"
							class="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-slate-700 bg-slate-100 hover:bg-slate-200"
						>
							<svg
								class="w-4 h-4 mr-1.5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
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
							Scan
						</a>
						<a
							href="/documents?upload=true"
							class="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-slate-700 bg-slate-100 hover:bg-slate-200"
						>
							<svg
								class="w-4 h-4 mr-1.5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M12 4v16m8-8H4"
								/>
							</svg>
							Upload
						</a>

						<button
							on:click={handleLogout}
							class="text-sm text-slate-500 hover:text-slate-700"
						>
							Logout
						</button>
					</div>
				</div>
			</div>
		</header>

		<!-- Main content -->
		<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-24 md:pb-8">
			<slot />
		</main>

		<!-- Mobile bottom navigation -->
		<nav class="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 z-50">
			<div class="flex justify-around items-center h-16">
				{#each navItems as item}
					<a
						href={item.href}
						class="flex flex-col items-center justify-center flex-1 h-full transition-colors
							{$page.url.pathname === item.href ||
						($page.url.pathname.startsWith(item.href) && item.href !== '/')
							? 'text-primary-600'
							: 'text-slate-500'}"
					>
						{#if item.icon === 'home'}
							<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
							</svg>
						{:else if item.icon === 'folder'}
							<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
							</svg>
						{:else if item.icon === 'users'}
							<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
							</svg>
						{:else if item.icon === 'chat'}
							<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
							</svg>
						{/if}
						<span class="text-xs mt-1">{item.label}</span>
					</a>
				{/each}
			</div>
		</nav>
	</div>
{/if}
