<script lang="ts">
	// First-run wizard: account → connections → trackers → home → done.
	// Home comes last on purpose: with trackers connected, TripAtlas can suggest it from where they spend the nights.
	import { goto } from '$app/navigation';
	import { api, errorText } from '$lib/api';
	import ConnectionsForm from '$lib/components/settings/ConnectionsForm.svelte';
	import HouseholdForm from '$lib/components/settings/HouseholdForm.svelte';
	import TrackersForm from '$lib/components/settings/TrackersForm.svelte';
	import { i18n, LANGUAGES, setLocale, t } from '$lib/i18n/index.svelte';
	import { loadSession, session, setUser } from '$lib/stores/session.svelte';
	import type { User } from '$lib/types';

	const steps = ['setup_step_account', 'setup_step_connections', 'setup_step_trackers', 'setup_step_home', 'setup_step_done'] as const;
	let step = $state(session.user ? 1 : 0);
	let admin = $state({ username: '', display_name: '', password: '', locale: i18n.locale });
	let error = $state('');
	let busy = $state(false);
	let connections = $state<ConnectionsForm>();

	async function createAdmin(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		try {
			const r = await api.post<{ user: User }>('/api/setup/admin', admin);
			setUser(r.user);
			step = 1;
		} catch (err) {
			error = errorText(err);
		}
	}

	async function afterConnections() {
		busy = true;
		const ok = (await connections?.saveUnsaved()) ?? true;
		busy = false;
		if (ok) step = 2;
	}

	// "Done!" already counts: whoever closes the tab here instead of tapping the button finds everything set up
	async function done() {
		step = 4;
		try {
			await api.post('/api/setup/complete');
		} catch (err) {
			error = errorText(err);
		}
	}

	async function finish() {
		error = '';
		busy = true;
		try {
			await api.post('/api/setup/complete');
			await loadSession();
			goto('/');
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}
</script>

<main>
	<header>
		<img src="/favicon.svg" alt="" width="40" height="40" />
		<h1>{t('setup_title')}</h1>
		<ol class="steps">
			{#each steps as s, i (s)}
				<li class:done={i < step} class:current={i === step}>{t(s)}</li>
			{/each}
		</ol>
	</header>

	<section class="card">
		{#if step === 0}
			<p>{t('setup_welcome')}</p>
			<form onsubmit={createAdmin}>
				<label class="field">
					<span>{t('language')}</span>
					<select bind:value={admin.locale} onchange={() => setLocale(admin.locale)}>
						{#each LANGUAGES as l (l.code)}<option value={l.code}>{l.name}</option>{/each}
					</select>
				</label>
				<label class="field"><span>{t('display_name')}</span><input type="text" bind:value={admin.display_name} required /><small class="muted">{t('display_name_hint')}</small></label>
				<label class="field"><span>{t('username')}</span><input type="text" bind:value={admin.username} pattern="[A-Za-z0-9._\-]+" required autocapitalize="none" /><small class="muted">{t('username_hint')}</small></label>
				<label class="field">
					<span>{t('password')}</span>
					<input type="password" bind:value={admin.password} minlength="8" required autocomplete="new-password" />
					<small>{t('password_rule')}</small>
				</label>
				{#if error}<p class="error">{error}</p>{/if}
				<div class="nav row"><span class="spacer"></span><button class="btn primary">{t('next')}</button></div>
			</form>
		{:else if step === 1}
			<h2>{t('setup_step_connections')}</h2>
			<p class="muted">{t('setup_connections_text')}</p>
			<ConnectionsForm bind:this={connections} />
			<div class="nav row">
				<span class="spacer"></span>
				<button class="btn primary" onclick={afterConnections} disabled={busy}>{t('next')}</button>
			</div>
		{:else if step === 2}
			<h2>{t('setup_step_trackers')}</h2>
			<p class="muted">{t('setup_trackers_text')}</p>
			<TrackersForm />
			<div class="nav row">
				<button class="btn" onclick={() => (step = 1)}>{t('back')}</button><span class="spacer"></span>
				<button class="btn primary" onclick={() => (step = 3)}>{t('next')}</button>
			</div>
		{:else if step === 3}
			<h2>{t('setup_step_home')}</h2>
			<p class="muted">{t('setup_home_text')}</p>
			<HouseholdForm wizard onsaved={done} />
			<div class="nav row"><button class="btn" onclick={() => (step = 2)}>{t('back')}</button></div>
		{:else}
			<h2>{t('setup_done_title')}</h2>
			<p>{t('setup_done_text')}</p>
			{#if error}<p class="error">{error}</p>{/if}
			<div class="nav row">
				<button class="btn" onclick={() => (step = 3)}>{t('back')}</button><span class="spacer"></span>
				<button class="btn primary" onclick={finish} disabled={busy}>{t('setup_finish')}</button>
			</div>
		{/if}
	</section>
</main>

<style>
	main {
		max-width: 760px;
		margin: 0 auto;
		padding: 24px 16px 48px;
	}
	header {
		text-align: center;
		margin-bottom: 18px;
	}
	h1 {
		margin: 8px 0 14px;
	}
	.steps {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 6px;
		padding: 0;
		list-style: none;
		counter-reset: s;
	}
	.steps li {
		counter-increment: s;
		font-size: 0.85em;
		padding: 0.25em 0.75em;
		border-radius: 999px;
		background: var(--surface-2);
		color: var(--text-2);
	}
	.steps li::before {
		content: counter(s) '. ';
	}
	.steps li.current {
		background: var(--accent);
		color: var(--accent-text);
	}
	.steps li.done {
		color: var(--ok);
	}
	section {
		padding: 22px;
		box-shadow: none;
	}
	.nav {
		margin-top: 22px;
		padding-top: 16px;
		border-top: 1px solid var(--border);
	}
</style>
