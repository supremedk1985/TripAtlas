<script lang="ts">
	// Top bar: household name and account actions in the first row, the main views as a segmented control below.
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import { session, setUser } from '$lib/stores/session.svelte';

	let { floating = false }: { floating?: boolean } = $props();

	const views = [
		{ href: '/', label: 'nav_map' },
		{ href: '/visited', label: 'nav_visited' }
	] as const;

	async function logout() {
		await api.post('/api/auth/logout');
		setUser(null);
		goto('/login');
	}
</script>

<nav class:floating class="card">
	<div class="row top">
		<a class="brand" href="/">
			<img src="/favicon.svg" alt="" width="24" height="24" />
			<span>{session.status?.name ?? 'TripAtlas'}</span>
		</a>
		<span class="spacer"></span>
		<a class="icon-btn" href="/settings" title={t('nav_settings')} aria-label={t('nav_settings')}
			class:active={page.url.pathname === '/settings'}>⚙</a
		>
		<button class="icon-btn" onclick={logout} title="{t('logout')} ({session.user?.display_name})" aria-label={t('logout')}>⎋</button>
	</div>
	<div class="segments">
		{#each views as v (v.href)}
			<a href={v.href} class:active={page.url.pathname === v.href}>{t(v.label)}</a>
		{/each}
	</div>
</nav>

<style>
	nav {
		display: grid;
		gap: 8px;
		padding: 10px 12px;
		border-radius: var(--radius);
	}
	nav.floating {
		position: absolute;
		top: 12px;
		left: 12px;
		z-index: 5;
		width: min(320px, calc(100% - 24px));
	}
	.top {
		flex-wrap: nowrap;
		gap: 6px;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 8px;
		font-weight: 700;
		font-size: 1.05em;
		color: var(--text);
		text-decoration: none;
		min-width: 0;
	}
	.brand span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.icon-btn {
		text-decoration: none;
		flex: none;
	}
	.icon-btn.active {
		border-color: var(--accent);
		color: var(--accent);
	}
	.segments {
		display: grid;
		grid-auto-flow: column;
		grid-auto-columns: 1fr;
		background: var(--surface-2);
		border-radius: 999px;
		padding: 3px;
	}
	.segments a {
		text-align: center;
		text-decoration: none;
		color: var(--text-2);
		padding: 0.35em 0.6em;
		border-radius: 999px;
		font-weight: 600;
		font-size: 0.92em;
		white-space: nowrap;
	}
	.segments a.active {
		background: var(--surface);
		color: var(--text);
		box-shadow: 0 1px 3px rgb(0 0 0 / 12%);
	}
</style>
