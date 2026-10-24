<script lang="ts">
	import { api, errorText } from '$lib/api';
	import { LANGUAGES, t } from '$lib/i18n/index.svelte';
	import { session, setUser } from '$lib/stores/session.svelte';
	import AvatarPicker from '$lib/components/AvatarPicker.svelte';
	import type { User } from '$lib/types';

	let displayName = $state(session.user?.display_name ?? '');
	let locale = $state(session.user?.locale ?? 'en');
	let current = $state('');
	let next = $state('');
	let immichKey = $state('');
	let msg = $state<{ ok: boolean; text: string } | null>(null);

	async function send(body: Record<string, unknown>) {
		msg = null;
		try {
			setUser(await api.put<User>('/api/auth/me', body));
			msg = { ok: true, text: t('saved') };
		} catch (err) {
			msg = { ok: false, text: errorText(err) };
		}
	}
</script>

{#if session.user && session.user.role !== 'child'}
	<div class="avatar-row"><AvatarPicker user={session.user} path="/api/auth/me/avatar" onchange={setUser} /></div>
{/if}

<form onsubmit={(e) => (e.preventDefault(), send({ display_name: displayName, locale }))}>
	<label class="field"><span>{t('display_name')}</span><input type="text" bind:value={displayName} required /></label>
	<label class="field">
		<span>{t('language')}</span>
		<select bind:value={locale}>{#each LANGUAGES as l (l.code)}<option value={l.code}>{l.name}</option>{/each}</select>
	</label>
	<button class="btn primary">{t('save')}</button>
</form>

<h4>{t('change_password')}</h4>
<form onsubmit={(e) => (e.preventDefault(), send({ current_password: current, new_password: next }).then(() => (current = next = '')))}>
	<label class="field"><span>{t('current_password')}</span><input type="password" bind:value={current} autocomplete="current-password" required /></label>
	<label class="field"><span>{t('new_password')}</span><input type="password" bind:value={next} minlength="8" autocomplete="new-password" required /></label>
	<button class="btn">{t('change_password')}</button>
</form>

<h4>{t('own_immich_key')}</h4>
<p class="muted">{t('own_immich_key_hint')}</p>
<form class="row" onsubmit={(e) => (e.preventDefault(), send({ immich_api_key: immichKey }).then(() => (immichKey = '')))}>
	<input type="password" bind:value={immichKey} placeholder={session.user?.has_immich_key ? t('stored_keep') : t('api_key')} autocomplete="off" />
	<button class="btn">{t('save')}</button>
	{#if session.user?.has_immich_key}<button type="button" class="btn danger" onclick={() => send({ immich_api_key: '' })}>{t('remove')}</button>{/if}
</form>
{#if msg}<p class={msg.ok ? 'success' : 'error'}>{msg.text}</p>{/if}

<style>
	form {
		margin-bottom: 8px;
	}
	form.row {
		flex-wrap: nowrap;
	}
	h4 {
		margin-top: 24px;
	}
	.avatar-row {
		margin-bottom: 16px;
	}
</style>
