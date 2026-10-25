<script lang="ts">
	// Top bar: household name and account actions in the first row, the main views as a segmented control below.
	import { page } from '$app/state';
	import { t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import AccountMenu from './AccountMenu.svelte';

	let { floating = false }: { floating?: boolean } = $props();

	const views = [
		{ href: '/', label: 'nav_map' },
		{ href: '/diary', label: 'nav_diary' },
		{ href: '/visited', label: 'nav_visited' }
	] as const;
</script>

<nav class:floating class="card">
	<div class="row top">
		<a class="brand" href="/">
			<img src="/favicon.svg" alt="" width="24" height="24" />
			<span>{session.status?.name ?? 'TripAtlas'}</span>
		</a>
		<span class="spacer"></span>
		<a class="icon-btn" href="/settings" title={t('nav_settings')} aria-label={t('nav_settings')}
			class:active={page.url.pathname === '/settings'}>
			<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
		</a>
		<AccountMenu />
	</div>
	<div class="segments">
		{#each views as v (v.href)}
			<a href={v.href} class:active={v.href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(v.href)}>{t(v.label)}</a>
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
	.icon-btn svg {
		width: 18px;
		height: 18px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
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
