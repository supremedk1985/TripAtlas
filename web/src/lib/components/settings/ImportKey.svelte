<script lang="ts">
	// Automatic import for one tracker: a key with which an app (a bike computer, HTTP Shortcuts, Tasker, a script)
	// sends each recording to /api/imports/push. The key is shown once, right after it was made.
	import { api, errorText } from '$lib/api';
	import { confirmDialog } from '$lib/stores/dialog.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import type { Tracker } from '$lib/types';

	let { tracker }: { tracker: Tracker } = $props();

	let key = $state('');
	let error = $state('');
	let copied = $state('');
	const address = `${location.origin}/api/imports/push`;

	async function make() {
		if (tracker.has_import_key && !(await confirmDialog(t('import_key_replace_confirm'), { confirmLabel: t('import_key_new') })))
			return;
		try {
			key = (await api.post<{ key: string }>(`/api/trackers/${tracker.id}/import-key`)).key;
			tracker.has_import_key = true;
		} catch (e) {
			error = errorText(e);
		}
	}

	async function revoke() {
		if (!(await confirmDialog(t('import_key_revoke_confirm'), { danger: true, confirmLabel: t('import_key_revoke') })))
			return;
		await api.del(`/api/trackers/${tracker.id}/import-key`);
		tracker.has_import_key = false;
		key = '';
	}

	async function copy(text: string, what: string) {
		try {
			await navigator.clipboard.writeText(text);
			copied = what;
		} catch {
			copied = '';
		}
	}
</script>

<details class="import-key">
	<summary>{t('import_key_title')}{#if tracker.has_import_key} · <span class="on">{t('import_key_active')}</span>{/if}</summary>
	<p class="muted small">{t('import_key_hint')}</p>
	{#if key}
		<div class="shown card">
			<p class="small"><strong>{t('import_key_once')}</strong></p>
			<span class="label small">{t('import_key_address')}</span>
			<div class="row"><code>{address}</code><button class="btn small" onclick={() => copy(address, 'a')}>{copied === 'a' ? '✓' : t('copy')}</button></div>
			<span class="label small">{t('import_key_key')}</span>
			<div class="row"><code>{key}</code><button class="btn small" onclick={() => copy(key, 'k')}>{copied === 'k' ? '✓' : t('copy')}</button></div>
			<p class="muted small">{t('import_key_how')}</p>
			<code class="example">curl -H "Authorization: Bearer …" -H "Content-Type: application/gpx+xml" --data-binary @ride.gpx {address}</code>
		</div>
	{/if}
	<div class="row">
		<button class="btn small" onclick={make}>{tracker.has_import_key ? t('import_key_new') : t('import_key_make')}</button>
		{#if tracker.has_import_key}<button class="btn small danger" onclick={revoke}>{t('import_key_revoke')}</button>{/if}
	</div>
	{#if error}<p class="error">{error}</p>{/if}
</details>

<style>
	.import-key {
		margin-top: 8px;
	}
	.small {
		font-size: 0.85em;
	}
	summary {
		cursor: pointer;
		font-size: 0.9em;
		padding: 6px 0;
	}
	.on {
		color: var(--accent);
	}
	.shown {
		display: grid;
		gap: 4px;
		padding: 10px 12px;
		margin: 6px 0 10px;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}
	code {
		font-size: 0.85em;
		word-break: break-all;
		min-width: 0;
		flex: 1;
	}
	.example {
		display: block;
		background: var(--surface-2);
		padding: 6px 8px;
		border-radius: 8px;
	}
	.label {
		color: var(--text-2);
		margin-top: 4px;
	}
</style>
