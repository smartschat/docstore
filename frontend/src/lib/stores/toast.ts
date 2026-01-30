import { writable } from 'svelte/store';

export type ToastType = 'success' | 'error' | 'info' | 'loading';

export interface Toast {
	id: string;
	type: ToastType;
	message: string;
	duration?: number; // ms, undefined = persistent (for loading)
}

function createToastStore() {
	const { subscribe, update } = writable<Toast[]>([]);

	function add(toast: Omit<Toast, 'id'>): string {
		const id = crypto.randomUUID();
		update((toasts) => [...toasts, { ...toast, id }]);

		// Auto-remove after duration (unless persistent)
		if (toast.duration) {
			setTimeout(() => remove(id), toast.duration);
		}

		return id;
	}

	function remove(id: string) {
		update((toasts) => toasts.filter((t) => t.id !== id));
	}

	function success(message: string, duration = 3000): string {
		return add({ type: 'success', message, duration });
	}

	function error(message: string, duration = 5000): string {
		return add({ type: 'error', message, duration });
	}

	function info(message: string, duration = 3000): string {
		return add({ type: 'info', message, duration });
	}

	function loading(message: string): string {
		return add({ type: 'loading', message });
	}

	return {
		subscribe,
		add,
		remove,
		success,
		error,
		info,
		loading
	};
}

export const toasts = createToastStore();
