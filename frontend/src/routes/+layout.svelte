<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { isAuthenticated } from '$stores/documents';
	import { logout } from '$lib/api';
	import { goto } from '$app/navigation';

	const navItems = [
		{ href: '/', label: 'Dashboard', icon: 'home' },
		{ href: '/documents', label: 'Documents', icon: 'folder' },
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
							href="/documents?upload=true"
							class="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
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
		<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
			<slot />
		</main>
	</div>
{/if}
