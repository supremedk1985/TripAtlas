<script lang="ts">
	// Who is signed in, the other accounts known on this device (one tap to switch) and signing out.
	import { forget, knownAccounts, signOut, switchTo, type KnownAccount } from '$lib/accounts';
	import { t } from '$lib/i18n/index.svelte';
	import { avatarUrl } from '$lib/avatar';
	import { session } from '$lib/stores/session.svelte';
	import Avatar from './Avatar.svelte';
	import { backLayer } from '$lib/back.svelte';

	let { variant = 'icon' }: { variant?: 'icon' | 'button' } = $props();

	let open = $state(false);
	backLayer(() => open, () => (open = false));
	let others = $state<KnownAccount[]>([]);
	let root: HTMLElement | undefined = $state();

	// The menu opens towards the side with room: from the right edge of the button (top bar, button on the right),
	// or from its left edge when the button sits near the left of the screen (children's view).
	let fromLeft = $state(false);

	function toggle() {
		open = !open;
		if (open && root) fromLeft = root.getBoundingClientRect().right < 260;
		if (open) others = knownAccounts().filter((a) => a.username.toLowerCase() !== session.user?.username.toLowerCase());
	}

	function remove(a: KnownAccount) {
		forget(a.username);
		others = others.filter((o) => o !== a);
	}

	function outside(e: PointerEvent) {
		if (open && root && !root.contains(e.target as Node)) open = false;
	}
</script>

<svelte:window onpointerdown={outside} onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<div class="account" bind:this={root}>
	{#if variant === 'icon'}
		<button class="icon-btn me-btn" class:pic={!!session.user?.avatar_version} class:active={open} onclick={toggle} aria-expanded={open} aria-haspopup="menu"
			title={session.user?.display_name} aria-label={t('account_menu')}>
			{#if session.user?.avatar_version}
				<Avatar name={session.user.display_name} src={avatarUrl(session.user)} size={28} />
			{:else}
				<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
			{/if}
		</button>
	{:else}
		<button class="btn small" onclick={toggle} aria-expanded={open} aria-haspopup="menu">{t('account_switch')}</button>
	{/if}

	{#if open}
		<div class="menu card" class:from-left={fromLeft} role="menu">
			{#if session.user}
				<div class="me">
					<Avatar name={session.user.display_name} src={avatarUrl(session.user)} size={40} />
					<div>
						<strong>{session.user.display_name}</strong>
						<span>@{session.user.username}</span>
					</div>
				</div>
			{/if}
			{#if others.length}
				<div class="label">{t('account_switch')}</div>
				{#each others as a (a.username)}
					<div class="other">
						<button role="menuitem" onclick={() => ((open = false), switchTo(a))}>
							<Avatar name={a.display_name} src={a.avatar} size={28} />
							<span class="name">{a.display_name}</span>
							{#if a.saved}
								<svg class="finger" viewBox="0 0 24 24" aria-label={t('account_fingerprint')}><path d="M12 11v3a6 6 0 0 1-1.5 4" /><path d="M8.5 9.5A4 4 0 0 1 16 11v2.5a10 10 0 0 1-1 4.3" /><path d="M5.6 7.6A7.5 7.5 0 0 1 19.5 11v1.5" /><path d="M8 13.5a14 14 0 0 1-1.6 4.5" /></svg>
							{/if}
						</button>
						<button class="x" onclick={() => remove(a)} title={t('account_forget')} aria-label={t('account_forget')}>×</button>
					</div>
				{/each}
			{/if}
			<button role="menuitem" class="plain" onclick={() => ((open = false), switchTo(null))}>{t('account_other')}</button>
			<button role="menuitem" class="plain" onclick={() => ((open = false), signOut())}>{t('logout')}</button>
		</div>
	{/if}
</div>

<style>
	.account {
		position: relative;
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
	.menu {
		position: absolute;
		right: 0;
		top: calc(100% + 6px);
		z-index: 30;
		min-width: 230px;
		max-width: calc(100vw - 32px);
		padding: 6px;
		display: grid;
		gap: 2px;
		box-shadow: 0 8px 24px rgb(0 0 0 / 18%);
	}
	.menu.from-left {
		right: auto;
		left: 0;
	}
	.me {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 10px 10px;
		border-bottom: 1px solid var(--border);
		margin-bottom: 4px;
	}
	.me div {
		display: grid;
	}
	.me-btn.pic {
		padding: 2px;
	}
	.me span,
	.label {
		color: var(--text-2);
		font-size: 0.85em;
	}
	.label {
		padding: 6px 10px 2px;
	}
	.menu button {
		background: none;
		border: 0;
		color: var(--text);
		font: inherit;
		text-align: left;
		cursor: pointer;
		border-radius: 8px;
	}
	.menu button:hover {
		background: var(--surface-2);
	}
	.plain {
		padding: 9px 10px;
	}
	.other {
		display: flex;
		align-items: center;
	}
	.other > button:first-child {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 7px 10px;
		min-width: 0;
	}
	.name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.finger {
		width: 18px;
		height: 18px;
		fill: none;
		stroke: var(--accent);
		stroke-width: 1.8;
		stroke-linecap: round;
		flex: none;
	}
	.x {
		padding: 6px 10px;
		color: var(--text-2) !important;
		font-size: 1.2em !important;
		line-height: 1;
	}
</style>
