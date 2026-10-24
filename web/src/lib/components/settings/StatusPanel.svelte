<script lang="ts">
	// What the background job did last and what TripAtlas holds — readable instead of raw JSON.
	import { api } from '$lib/api';
	import { dateTime } from '$lib/format';
	import { i18n, t } from '$lib/i18n/index.svelte';

	type Status = {
		running: boolean;
		last_run_at: number | null;
		last_duration_s: number | null;
		last_result: {
			synced?: Record<string, number>;
			sync_error?: string;
			recomputed?: Record<string, number>;
			places?: number;
			flights?: { candidates: number; checked_now: number; airborne: number; flights: number } | null;
			snapshot?: boolean;
		};
		trackers: { name: string; positions: number; last: number | null }[];
		trips: number;
		places: number;
		flights: number;
		flights_checked_at: number | null;
		snapshots: string[];
	};

	let s = $state<Status | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;

	async function load() {
		s = await api.get<Status>('/api/admin/jobs');
		clearTimeout(timer);
		if (s.running) timer = setTimeout(load, 2000);
	}
	load();
	$effect(() => () => clearTimeout(timer));

	async function run() {
		await api.post('/api/admin/jobs/run');
		setTimeout(load, 800);
	}

	const entries = (o?: Record<string, number>) => Object.entries(o ?? {});
</script>

<p class="muted">{t('status_hint')}</p>
{#if s}
	<div class="state row">
		{#if s.running}<span class="dot busy"></span><strong>{t('status_running')}</strong>
		{:else}<span class="dot ok"></span><strong>{t('status_idle_short')}</strong>{/if}
		{#if s.last_run_at}<span class="muted">· {t('status_last_run', { when: dateTime(s.last_run_at), s: (s.last_duration_s ?? 0).toLocaleString(i18n.locale) })}</span>{/if}
		<span class="spacer"></span>
		<button class="btn small primary" onclick={run} disabled={s.running}>{t('run_now')}</button>
	</div>

	<h4>{t('status_last_round')}</h4>
	<ul class="facts">
		{#if s.last_result.sync_error}<li class="error">{t('status_sync_error')}: {s.last_result.sync_error}</li>{/if}
		{#each entries(s.last_result.synced) as [name, n] (name)}<li>{t('status_new_positions', { name, n: n.toLocaleString(i18n.locale) })}</li>{/each}
		{#each entries(s.last_result.recomputed) as [name, n] (name)}<li>{t('status_recomputed', { name, n })}</li>{/each}
		{#if s.last_result.places}<li>{t('status_places_looked_up', { n: s.last_result.places })}</li>{/if}
		{#if s.last_result.flights}<li>{t('status_flights_checked', { n: s.last_result.flights.checked_now, f: s.last_result.flights.flights })}</li>{/if}
		{#if s.last_result.snapshot}<li>{t('status_snapshot_written')}</li>{/if}
		{#if !Object.keys(s.last_result).length}<li class="muted">{t('status_nothing_yet')}</li>{/if}
	</ul>

	<h4>{t('status_inventory')}</h4>
	<table>
		<tbody>
			{#each s.trackers as tk (tk.name)}
				<tr><td>{tk.name}</td><td>{tk.positions.toLocaleString(i18n.locale)} {t('positions')}{#if tk.last}{' · '}{t('last_seen', { when: dateTime(tk.last) })}{/if}</td></tr>
			{/each}
			<tr><td>{t('status_trips')}</td><td>{s.trips}</td></tr>
			<tr><td>{t('status_places')}</td><td>{s.places}</td></tr>
			<tr><td>{t('status_flights')}</td><td>{s.flights}{#if s.flights_checked_at}{' · '}{t('status_checked', { when: dateTime(s.flights_checked_at) })}{/if}</td></tr>
			<tr>
				<td>{t('status_backups')}</td>
				<td>{#if s.snapshots.length}{s.snapshots.length} · {t('status_latest')} {s.snapshots.at(-1)}{:else}–{/if}</td>
			</tr>
		</tbody>
	</table>
{:else}
	<p class="muted">{t('loading')}</p>
{/if}

<style>
	.state {
		flex-wrap: wrap;
	}
	.dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
	}
	.dot.ok {
		background: var(--ok);
	}
	.dot.busy {
		background: var(--warn);
	}
	h4 {
		margin: 18px 0 6px;
	}
	.facts {
		margin: 0;
		padding-left: 1.2em;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.93em;
	}
	td {
		padding: 6px 4px;
		border-bottom: 1px solid var(--border);
		vertical-align: top;
	}
	td:first-child {
		color: var(--text-2);
		width: 40%;
	}
</style>
