<script lang="ts">
	// Household settings: name, home location, time zone, detection thresholds.
	// Finding your own house on a world map with a finger is hard, so home can be set three ways: TripAtlas suggests
	// it from the trackers' nights (where they park most is home), a place search, or a tap (which zooms in so the
	// spot can be refined). In the setup wizard (`wizard`) the rarely needed thresholds are folded away and one button
	// saves and continues.
	import maplibregl from 'maplibre-gl';
	import { api, errorText, query } from '$lib/api';
	import { LANGUAGES, plural, t } from '$lib/i18n/index.svelte';
	import MapView from '$lib/map/MapView.svelte';

	let { onsaved, wizard = false }: { onsaved?: () => void; wizard?: boolean } = $props();

	type Household = {
		name: string;
		home_lat: number | null;
		home_lon: number | null;
		home_radius_km: number;
		timezone: string;
		default_locale: string;
		history_start: string | null;
		min_trip_nights: number;
		min_trip_distance_km: number;
		place_info_enabled: boolean;
	};
	type Suggestion = { lat: number; lon: number; nights: number; total: number };
	type Hit = { name: string; label: string; lat: number; lon: number };

	let h = $state<Household | null>(null);
	let zones = $state<string[]>([]);
	let historyDate = $state('');
	let error = $state('');
	let saved = $state(false);
	let busy = $state(false);
	let suggestion = $state<Suggestion | null>(null);
	let fromSuggestion = $state(false);
	let search = $state('');
	let hits = $state<Hit[]>([]);
	let searching = $state(false);
	let map: maplibregl.Map | undefined;
	let marker: maplibregl.Marker | undefined;
	const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

	Promise.all([api.get<Household>('/api/settings/household'), api.get<string[]>('/api/settings/timezones')]).then(
		([household, tz]) => {
			if (household.timezone === 'UTC') household.timezone = browserZone;
			h = household;
			zones = tz;
			historyDate = household.history_start?.slice(0, 10) ?? '';
			if (household.home_lat == null) loadSuggestion();
			else showHome(false);
		}
	);

	async function loadSuggestion() {
		suggestion = await api
			.get<Suggestion | null>(`/api/setup/home-suggestion?${query({ tz: h?.timezone ?? browserZone })}`)
			.catch(() => null);
		if (suggestion && h && h.home_lat == null) {
			setHome(suggestion.lat, suggestion.lon);
			fromSuggestion = true;
		}
	}

	function setHome(lat: number, lon: number, zoom = true) {
		if (!h) return;
		h.home_lat = Math.round(lat * 1e5) / 1e5;
		h.home_lon = Math.round(lon * 1e5) / 1e5;
		fromSuggestion = false;
		saved = false;
		showHome(zoom);
	}

	function showHome(fly: boolean) {
		if (!map || !h || h.home_lat == null || h.home_lon == null) return;
		marker ??= new maplibregl.Marker({ color: '#0f766e' }).setLngLat([h.home_lon, h.home_lat]).addTo(map);
		marker.setLngLat([h.home_lon, h.home_lat]);
		const target = { center: [h.home_lon, h.home_lat] as [number, number], zoom: Math.max(map.getZoom(), 13) };
		if (fly) map.flyTo(target);
		else map.jumpTo(target);
	}

	function onMap(m: maplibregl.Map) {
		map = m;
		showHome(false);
		m.on('click', (e) => setHome(e.lngLat.lat, e.lngLat.lng));
	}

	async function runSearch(e: Event) {
		e.preventDefault();
		if (search.trim().length < 3) return;
		searching = true;
		hits = await api.get<Hit[]>(`/api/places/search?${query({ q: search })}`).catch(() => []);
		searching = false;
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!h) return;
		error = '';
		saved = false;
		if (h.home_lat == null) {
			error = t('home_required');
			return;
		}
		busy = true;
		try {
			await api.put('/api/settings/household', { ...h, history_start: historyDate ? `${historyDate}T00:00:00Z` : null });
			saved = true;
			onsaved?.();
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}
</script>

{#if h}
	<form onsubmit={save}>
		<label class="field">
			<span>{t('household_name')}</span>
			<input type="text" bind:value={h.name} maxlength="80" required />
		</label>

		<div class="field">
			<span>{t('home')}</span>
			{#if fromSuggestion && suggestion}
				<p class="callout">📍 {t('home_suggested', { nights: suggestion.nights, total: suggestion.total })}</p>
			{:else}
				<small>{t('home_hint')}</small>
			{/if}
			<div class="search row">
				<input type="text" bind:value={search} placeholder={t('home_search')} onkeydown={(e) => e.key === 'Enter' && runSearch(e)} />
				<button type="button" class="btn" onclick={runSearch} disabled={searching}>{t('search')}</button>
			</div>
			{#if hits.length}
				<ul class="hits card">
					{#each hits as hit, i (i)}
						<li><button type="button" onclick={() => ((hits = []), setHome(hit.lat, hit.lon))}>{hit.label}</button></li>
					{/each}
				</ul>
			{/if}
			<div class="map"><MapView onready={onMap} zoom={4} /></div>
			{#if h.home_lat != null}
				<small class="muted">{h.home_lat}, {h.home_lon} · {t('home_refine')}</small>
			{/if}
		</div>

		<label class="field">
			<span>{t('timezone')}</span>
			<select bind:value={h.timezone}>
				{#each zones as z (z)}<option value={z}>{z}</option>{/each}
			</select>
		</label>

		<label class="row check">
			<input type="checkbox" bind:checked={h.place_info_enabled} />
			<span>{t('place_info_enabled')}</span>
		</label>
		<small class="muted">{t('place_info_hint')}</small>

		<details open={!wizard}>
			<summary>{t('detection_settings')}</summary>
			<div class="grid">
				<label class="field">
					<span>{t('home_radius')}</span>
					<input type="number" min="0.5" max="50" step="0.5" bind:value={h.home_radius_km} />
				</label>
				<label class="field">
					<span>{t('min_nights')}</span>
					<input type="number" min="1" max="30" bind:value={h.min_trip_nights} />
				</label>
				<label class="field">
					<span>{t('min_distance')}</span>
					<input type="number" min="1" bind:value={h.min_trip_distance_km} />
				</label>
				<label class="field">
					<span>{t('history_start')}</span>
					<input type="date" bind:value={historyDate} />
				</label>
				{#if !wizard}
					<label class="field">
						<span>{t('default_language')}</span>
						<select bind:value={h.default_locale}>
							{#each LANGUAGES as l (l.code)}<option value={l.code}>{l.name}</option>{/each}
						</select>
					</label>
				{/if}
			</div>
			<small class="muted">{t('detection_hint', { nights: plural('nights', h.min_trip_nights) })}</small>
		</details>

		{#if error}<p class="error">{error}</p>{/if}
		{#if saved && !wizard}<p class="success">{t('saved')}</p>{/if}
		<div class="row actions">
			<span class="spacer"></span>
			<button class="btn primary" disabled={busy}>{wizard ? t('save_and_next') : t('save')}</button>
		</div>
	</form>
{:else}
	<p class="muted">{t('loading')}</p>
{/if}

<style>
	.map {
		position: relative;
		height: 300px;
		border-radius: var(--radius-sm);
		overflow: hidden;
		border: 1px solid var(--border);
		cursor: crosshair;
		margin-top: 6px;
	}
	.callout {
		margin: 0;
		padding: 8px 10px;
		border-radius: var(--radius-sm);
		background: color-mix(in srgb, var(--accent) 12%, transparent);
	}
	.search {
		flex-wrap: nowrap;
		margin-top: 6px;
	}
	.hits {
		list-style: none;
		margin: 4px 0 0;
		padding: 4px;
		box-shadow: none;
	}
	.hits button {
		width: 100%;
		text-align: left;
		border: 0;
		background: none;
		padding: 6px 8px;
		border-radius: 6px;
		cursor: pointer;
	}
	.hits button:hover {
		background: var(--surface-2);
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0 14px;
		margin-top: 10px;
	}
	.check {
		gap: 0.5em;
		flex-wrap: nowrap;
	}
	details {
		margin-top: 16px;
		padding: 10px 12px;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
	}
	summary {
		cursor: pointer;
		font-weight: 600;
	}
	.actions {
		margin-top: 16px;
	}
</style>
