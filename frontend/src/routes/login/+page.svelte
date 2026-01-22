<script lang="ts">
	import { goto } from '$app/navigation';
	import { login } from '$lib/api';
	import { isAuthenticated } from '$stores/documents';

	let password = '';
	let error = '';
	let loading = false;

	async function handleSubmit() {
		if (!password) {
			error = 'Please enter a password';
			return;
		}

		loading = true;
		error = '';

		try {
			const result = await login(password);
			if (result.success) {
				$isAuthenticated = true;
				goto('/');
			} else {
				error = result.message || 'Login failed';
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Login failed';
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-screen flex items-center justify-center bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
	<div class="max-w-md w-full space-y-8">
		<div>
			<h1 class="text-center text-3xl font-bold text-primary-600">DocStore</h1>
			<h2 class="mt-6 text-center text-xl text-slate-600">Sign in to your documents</h2>
		</div>

		<form class="mt-8 space-y-6" on:submit|preventDefault={handleSubmit}>
			{#if error}
				<div class="rounded-md bg-red-50 p-4">
					<p class="text-sm text-red-700">{error}</p>
				</div>
			{/if}

			<div>
				<label for="password" class="sr-only">Password</label>
				<input
					id="password"
					name="password"
					type="password"
					required
					class="appearance-none rounded-lg relative block w-full px-3 py-3 border border-slate-300 placeholder-slate-400 text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
					placeholder="Enter password"
					bind:value={password}
					disabled={loading}
				/>
			</div>

			<button
				type="submit"
				class="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
				disabled={loading}
			>
				{#if loading}
					<span class="spinner mr-2"></span>
				{/if}
				Sign in
			</button>
		</form>
	</div>
</div>
