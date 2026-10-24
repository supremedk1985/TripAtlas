<script lang="ts">
	import '../app.css';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onUnauthorized } from '$lib/api';
	import DialogHost from '$lib/components/DialogHost.svelte';
	import { loadSession, session } from '$lib/stores/session.svelte';
	import { installAppSignIn, remember } from '$lib/accounts';
	import { t } from '$lib/i18n/index.svelte';

	let { children } = $props();
	let error = $state('');

	// Route guard: setup → login → children's area. Runs on every navigation.
	$effect(() => {
		if (!session.loaded) return;
		const path = page.url.pathname;
		const s = session.status;
		if (s && !s.has_admin && path !== '/setup') goto('/setup');
		else if (s?.has_admin && !session.user && path !== '/login')
			goto(`/login?next=${encodeURIComponent(page.url.pathname + page.url.search)}`);
		else if (session.user?.role === 'admin' && s && !s.setup_complete && path !== '/setup') goto('/setup');
		else if (session.user?.role === 'child' && !path.startsWith('/kids')) goto('/kids');
	});

	// Session expired or ended elsewhere: forget the user; the guard above then shows the sign-in page.
	onUnauthorized(() => (session.user = null));
	// Whoever is signed in on this device shows up under "Switch account" later
	$effect(() => {
		if (session.user) remember(session.user);
	});
	installAppSignIn();
	loadSession().catch((e) => (error = e instanceof Error ? e.message : String(e)));
</script>

<DialogHost />

{#if error}
	<main class="center"><p class="error">{t('error_server')}</p><p class="muted">{error}</p></main>
{:else if session.loaded}
	{@render children()}
{:else}
	<main class="center"><div class="spinner" aria-label="Loading"></div></main>
{/if}

<style>
	.center {
		position: fixed;
		inset: 0;
		display: grid;
		place-items: center;
		align-content: center;
		gap: 0.5rem;
		padding: 16px;
		text-align: center;
	}
	.spinner {
		width: 34px;
		height: 34px;
		border-radius: 50%;
		border: 3px solid var(--border);
		border-top-color: var(--accent);
		animation: spin 0.9s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
