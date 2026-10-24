<script lang="ts">
	// Import GPX, Google location history or GeoJSON into a tracker. Duplicates (same tracker, same second) are skipped,
	// so importing the same file twice is harmless.
	import { api } from '$lib/api';
	import { date } from '$lib/format';
	import { t } from '$lib/i18n/index.svelte';
	import type { Tracker } from '$lib/types';

	type Job = { id: number; tracker_id: number; kind: string; filename: string; status: string; added: number; skipped: number; message: string; created_at: string };

	let trackers = $state<Tracker[]>([]);
	let jobs = $state<Job[]>([]);
	let trackerId = $state<number | null>(null);
	let files = $state<FileList | null>(null);
	let busy = $state(false);
	let result = $state<{ ok: boolean; text: string } | null>(null);

	async function load() {
		[trackers, jobs] = await Promise.all([api.get<Tracker[]>('/api/trackers'), api.get<Job[]>('/api/imports')]);
		trackerId ??= trackers[0]?.id ?? null;
	}
	load();

	async function upload(e: SubmitEvent) {
		e.preventDefault();
		if (!files?.length || trackerId === null) return;
		busy = true;
		result = null;
		try {
			let added = 0, total = 0;
			for (const f of files) {
				const form = new FormData();
				form.append('tracker_id', String(trackerId));
				form.append('file', f);
				const r = await api.post<{ points: number; added: number }>('/api/imports', form);
				added += r.added;
				total += r.points;
			}
			result = { ok: true, text: t('import_done', { added: added.toLocaleString(), total: total.toLocaleString() }) };
			await load();
		} catch (err) {
			result = { ok: false, text: (err as Error).message };
		} finally {
			busy = false;
		}
	}
</script>

<p class="muted">{t('import_hint')}</p>
<form onsubmit={upload}>
	<label class="field">
		<span>{t('tracker')}</span>
		<select bind:value={trackerId}>{#each trackers as tk (tk.id)}<option value={tk.id}>{tk.name}</option>{/each}</select>
	</label>
	<label class="field">
		<span>{t('files')}</span>
		<input type="file" multiple accept=".gpx,.json,.geojson" bind:files />
	</label>
	{#if result}<p class={result.ok ? 'success' : 'error'}>{result.text}</p>{/if}
	<button class="btn primary" disabled={busy || !files?.length}>{busy ? t('importing') : t('import')}</button>
</form>

{#if jobs.length}
	<h4>{t('import_history')}</h4>
	<table>
		<tbody>
			{#each jobs as j (j.id)}
				<tr>
					<td>{date(new Date(j.created_at).getTime() / 1000)}</td>
					<td class="name">{j.filename}</td>
					<td>{trackers.find((tk) => tk.id === j.tracker_id)?.name}</td>
					<td class={j.status === 'failed' ? 'error' : ''}>{j.status === 'failed' ? j.message : `+${j.added.toLocaleString()}`}</td>
				</tr>
			{/each}
		</tbody>
	</table>
{/if}

<style>
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.88em;
	}
	td {
		padding: 6px 4px;
		border-bottom: 1px solid var(--border);
	}
	.name {
		word-break: break-all;
	}
</style>
