import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// During development the API runs separately: TRIPATLAS_API=http://127.0.0.1:8097 npm run dev
export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: { '/api': process.env.TRIPATLAS_API ?? 'http://127.0.0.1:8097' }
	}
});
