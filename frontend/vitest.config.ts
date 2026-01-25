import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}'],
    environment: 'jsdom',
    globals: true,
    alias: {
      $lib: new URL('./src/lib', import.meta.url).pathname,
      '$lib/': new URL('./src/lib/', import.meta.url).pathname,
      $stores: new URL('./src/lib/stores', import.meta.url).pathname,
      '$stores/': new URL('./src/lib/stores/', import.meta.url).pathname,
    }
  }
});
