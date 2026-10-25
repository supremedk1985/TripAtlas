<script lang="ts">
	import { api, errorText } from '$lib/api';
	import { LANGUAGES, t } from '$lib/i18n/index.svelte';
	import { session, setUser } from '$lib/stores/session.svelte';
	import AvatarPicker from '$lib/components/AvatarPicker.svelte';
	import type { User } from '$lib/types';
	import { clearStorage, getLimitMb, LIMITS_MB, setLimitMb, storageUsage } from '$lib/deviceCache/client';
	import { onMount } from 'svelte';

	let displayName = $state(session.user?.display_name ?? '');
	let locale = $state(session.user?.locale ?? 'en');
	let current = $state('');
	let next = $state('');
	let immichKey = $state('');
	let msg = $state<{ ok: boolean; text: string } | null>(null);

	// storage on this device
	const canStore = typeof caches !== 'undefined' && 'serviceWorker' in navigator;
	let limitMb = $state(0);
	let used = $state<{ total: number; mine: number; tiles: number } | null>(null);
	let storeMsg = $state('');
	const mb = (bytes: number) => (bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : `${Math.round(bytes / 1024 ** 2)} MB`);
	const limitLabel = (m: number) => (m ? mb(m * 1024 ** 2) : t('device_storage_off'));

	async function refreshStorage() {
		limitMb = await getLimitMb();
		used = await storageUsage();
	}
	onMount(() => {
		if (canStore) refreshStorage();
	});
	async function changeLimit() {
		storeMsg = '';
		await setLimitMb(limitMb);
		await refreshStorage();
	}
	async function emptyStorage() {
		await clearStorage();
		await refreshStorage();
		storeMsg = t('device_storage_cleared');
	}

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
	<h4 class="first">{t('profile_picture')}</h4>
	<p class="muted small">{t('profile_picture_hint')}</p>
	<div class="avatar-row"><AvatarPicker user={session.user} path="/api/auth/me/avatar" onchange={setUser} /></div>
	<h4>{t('profile_details')}</h4>
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

<h4>{t('device_storage')}</h4>
{#if canStore}
	<p class="muted">{t('device_storage_hint')}</p>
	<div class="row">
		<select bind:value={limitMb} onchange={changeLimit} aria-label={t('device_storage')}>
			{#each LIMITS_MB as m (m)}<option value={m}>{limitLabel(m)}</option>{/each}
		</select>
		<button type="button" class="btn" onclick={emptyStorage} disabled={!used?.total}>{t('device_storage_clear')}</button>
	</div>
	{#if used && limitMb}
		<p class="muted small">{t('device_storage_used', { used: mb(used.total), limit: limitLabel(limitMb), mine: mb(used.mine), tiles: mb(used.tiles) })}</p>
	{/if}
	{#if storeMsg}<p class="success">{storeMsg}</p>{/if}
{:else}
	<p class="muted">{t('device_storage_unsupported')}</p>
{/if}

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
	h4.first {
		margin-top: 0;
	}
	.avatar-row {
		margin-bottom: 16px;
	}
</style>
