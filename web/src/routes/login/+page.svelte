<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import { session, setUser } from '$lib/stores/session.svelte';
	import type { User } from '$lib/types';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			const r = await api.post<{ user: User }>('/api/auth/login', { username, password });
			setUser(r.user);
			goto(r.user.role === 'child' ? '/kids' : '/');
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
		<label class="field">
			<span>{t('username')}</span>
			<input type="text" bind:value={username} autocomplete="username" autocapitalize="none" required />
		</label>
		<label class="field">
			<span>{t('password')}</span>
			<input type="password" bind:value={password} autocomplete="current-password" required />
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
</style>
