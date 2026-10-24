<script lang="ts">
	// Traccar and Immich connections. Each is tested before it is saved; stored secrets are never sent back
	// (empty secret field = keep the stored one).
	import { api } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';

	let { onsaved }: { onsaved?: () => void } = $props();

	let traccar = $state({ url: '', email: '', password: '', token: '', has_token: false, has_password: false, useToken: true });
	let immich = $state({ url: '', api_key: '', has_api_key: false });
	let traccarResult = $state<{ ok: boolean; text: string } | null>(null);
	let immichResult = $state<{ ok: boolean; text: string } | null>(null);

	api.get<{ url: string; email: string; has_token: boolean; has_password: boolean }>('/api/settings/traccar').then((r) => {
		Object.assign(traccar, r, { useToken: !r.email });
	});
	api.get<{ url: string; has_api_key: boolean }>('/api/settings/immich').then((r) => Object.assign(immich, r));

	const traccarBody = () =>
		traccar.useToken
			? { url: traccar.url, token: traccar.token }
			: { url: traccar.url, email: traccar.email, password: traccar.password };

	async function saveTraccar(e: SubmitEvent) {
		e.preventDefault();
		traccarResult = null;
		try {
			const r = await api.post<{ version: string; devices: unknown[] }>('/api/settings/traccar/test', traccarBody());
			await api.put('/api/settings/traccar', traccarBody());
			traccarResult = { ok: true, text: t('traccar_ok', { version: r.version, n: r.devices.length }) };
			onsaved?.();
		} catch (err) {
			traccarResult = { ok: false, text: (err as Error).message };
		}
	}

	async function saveImmich(e: SubmitEvent) {
		e.preventDefault();
		immichResult = null;
		try {
			const body = { url: immich.url, api_key: immich.api_key };
			const r = await api.post<{ version: string; user: string }>('/api/settings/immich/test', body);
			await api.put('/api/settings/immich', body);
			immichResult = { ok: true, text: t('immich_ok', { version: r.version, user: r.user }) };
			onsaved?.();
		} catch (err) {
			immichResult = { ok: false, text: (err as Error).message };
		}
	}
</script>

<section>
	<h3>Traccar</h3>
	<p class="muted">{t('traccar_hint')}</p>
	<form onsubmit={saveTraccar}>
		<label class="field">
			<span>{t('server_url')}</span>
			<input type="url" bind:value={traccar.url} placeholder="http://traccar:8082" required />
		</label>
		<div class="row">
			<label class="chip" class:on={traccar.useToken}>
				<input type="radio" hidden bind:group={traccar.useToken} value={true} />{t('api_token')}
			</label>
			<label class="chip" class:on={!traccar.useToken}>
				<input type="radio" hidden bind:group={traccar.useToken} value={false} />{t('email_password')}
			</label>
		</div>
		<br />
		{#if traccar.useToken}
			<label class="field">
				<span>{t('api_token')}</span>
				<input type="password" bind:value={traccar.token} placeholder={traccar.has_token ? t('stored_keep') : ''} autocomplete="off" />
				<small>{t('traccar_token_hint')}</small>
			</label>
		{:else}
			<label class="field">
				<span>{t('email')}</span>
				<input type="text" bind:value={traccar.email} autocomplete="off" />
			</label>
			<label class="field">
				<span>{t('password')}</span>
				<input type="password" bind:value={traccar.password} placeholder={traccar.has_password ? t('stored_keep') : ''} autocomplete="new-password" />
			</label>
		{/if}
		{#if traccarResult}<p class={traccarResult.ok ? 'success' : 'error'}>{traccarResult.text}</p>{/if}
		<button class="btn primary">{t('test_and_save')}</button>
	</form>
</section>

<section>
	<h3>Immich</h3>
	<p class="muted">{t('immich_hint')}</p>
	<form onsubmit={saveImmich}>
		<label class="field">
			<span>{t('server_url')}</span>
			<input type="url" bind:value={immich.url} placeholder="http://immich-server:2283" required />
		</label>
		<label class="field">
			<span>{t('api_key')}</span>
			<input type="password" bind:value={immich.api_key} placeholder={immich.has_api_key ? t('stored_keep') : ''} autocomplete="off" />
			<small>{t('immich_key_hint')}</small>
		</label>
		{#if immichResult}<p class={immichResult.ok ? 'success' : 'error'}>{immichResult.text}</p>{/if}
		<button class="btn primary">{t('test_and_save')}</button>
	</form>
</section>

<style>
	section + section {
		margin-top: 28px;
		padding-top: 20px;
		border-top: 1px solid var(--border);
	}
</style>
