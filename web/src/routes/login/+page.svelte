<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import { ApiError } from '$lib/api';
	import { homeOf, knownAccounts, offerSave, signIn, switchTo, type KnownAccount } from '$lib/accounts';
	import { t } from '$lib/i18n/index.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import { session } from '$lib/stores/session.svelte';

	const failed = page.url.searchParams.get('failed');
	let username = $state(page.url.searchParams.get('user') ?? '');
	let password = $state('');
	let error = $state(failed === 'saved' ? t('login_saved_failed') : failed === 'throttled' ? t('login_throttled') : '');
	let busy = $state(false);
	let passwordField: HTMLInputElement | undefined = $state();
	const accounts = knownAccounts();

	// Name already filled in when the page opens (switching accounts): start in the password field. Only then —
	// reading `username` here without untrack made every typed letter jump to the password field.
	$effect(() => {
		if (passwordField && untrack(() => username)) passwordField.focus();
	});

	function pick(a: KnownAccount) {
		error = '';
		if (a.saved) switchTo(a);   // the app asks for the fingerprint and signs in
		else {
			username = a.username;
			password = '';
			passwordField?.focus();
		}
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			const user = await signIn(username, password);
			offerSave(password, user);
			// back to where the user was when the session ended (only paths inside TripAtlas)
			const next = page.url.searchParams.get('next');
			const fits = next && next.startsWith('/') && !next.startsWith('//') && next.startsWith('/kids') === (user.role === 'child');
			goto(fits ? next : homeOf(user));
		} catch (err) {
			error = err instanceof ApiError && err.status === 429 ? t('login_throttled') : t('login_failed');
		} finally {
			busy = false;
		}
	}
</script>

<main>
	<form class="card" onsubmit={submit}>
		<img src="/favicon.svg" alt="" width="48" height="48" />
		<h1>{session.status?.name ?? 'TripAtlas'}</h1>
		{#if accounts.length}
			<div class="accounts">
				{#each accounts as a (a.username)}
					<button type="button" class:current={a.username.toLowerCase() === username.toLowerCase()} onclick={() => pick(a)}>
						<Avatar name={a.display_name} src={a.avatar} size={30} />
						<span class="name">{a.display_name}</span>
						{#if a.saved}
							<svg viewBox="0 0 24 24" aria-label={t('account_fingerprint')}><path d="M12 11v3a6 6 0 0 1-1.5 4" /><path d="M8.5 9.5A4 4 0 0 1 16 11v2.5a10 10 0 0 1-1 4.3" /><path d="M5.6 7.6A7.5 7.5 0 0 1 19.5 11v1.5" /><path d="M8 13.5a14 14 0 0 1-1.6 4.5" /></svg>
						{/if}
					</button>
				{/each}
			</div>
		{/if}
		<label class="field">
			<span>{t('username')}</span>
			<input type="text" name="username" bind:value={username} autocomplete="username" autocapitalize="none" required />
		</label>
		<label class="field">
			<span>{t('password')}</span>
			<input type="password" name="password" bind:value={password} bind:this={passwordField} autocomplete="current-password" required />
		</label>
		{#if error}<p class="error">{error}</p>{/if}
		<button class="btn primary" disabled={busy}>{t('login')}</button>
	</form>
</main>

<style>
	main {
		min-height: 100vh;
		display: grid;
		place-items: center;
		padding: 16px;
	}
	form {
		width: min(360px, 100%);
		padding: 28px 24px;
		display: grid;
		justify-items: stretch;
	}
	img {
		justify-self: center;
	}
	h1 {
		text-align: center;
		margin: 10px 0 20px;
	}
	.accounts {
		display: grid;
		gap: 6px;
		margin-bottom: 16px;
	}
	.accounts button {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 10px;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--surface);
		color: var(--text);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	.accounts button.current {
		border-color: var(--accent);
	}
	.accounts .name {
		flex: 1;
		font-weight: 600;
	}
	.accounts svg {
		width: 20px;
		height: 20px;
		fill: none;
		stroke: var(--accent);
		stroke-width: 1.8;
		stroke-linecap: round;
	}
</style>
