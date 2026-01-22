import { checkAuth } from '$lib/api';
import { isAuthenticated } from '$stores/documents';
import { redirect } from '@sveltejs/kit';
import type { LayoutLoad } from './$types';

export const ssr = false;
export const prerender = false;

export const load: LayoutLoad = async ({ url }) => {
	// Skip auth check for login page
	if (url.pathname === '/login') {
		return {};
	}

	try {
		const { authenticated } = await checkAuth();
		isAuthenticated.set(authenticated);

		if (!authenticated) {
			throw redirect(302, '/login');
		}
	} catch (error) {
		if (error && typeof error === 'object' && 'status' in error && error.status === 302) {
			throw error;
		}
		throw redirect(302, '/login');
	}

	return {};
};
