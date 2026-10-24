<script lang="ts">
	// Household settings: name, home location (tap the map), time zone, detection thresholds.
	import maplibregl from 'maplibre-gl';
	import { api } from '$lib/api';
	import { LANGUAGES, t } from '$lib/i18n/index.svelte';
	import MapView from '$lib/map/MapView.svelte';

	let { onsaved }: { onsaved?: () => void } = $props();

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

	let h = $state<Household | null>(null);
	let zones = $state<string[]>([]);
	let historyDate = $state('');
	let error = $state('');
	let saved = $state(false);
	let marker: maplibregl.Marker | undefined;

	Promise.all([api.get<Household>('/api/settings/household'), api.get<string[]>('/api/settings/timezones')]).then(
		([household, tz]) => {
			if (household.timezone === 'UTC') household.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
			h = household;
			zones = tz;
			historyDate = household.history_start?.slice(0, 10) ?? '';
		}
	);

	function onMap(map: maplibregl.Map) {
		const place = (lat: number, lon: number) => {
			marker ??= new maplibregl.Marker({ color: '#0f766e' }).setLngLat([lon, lat]).addTo(map);
			marker.setLngLat([lon, lat]);
		};
		if (h?.home_lat != null && h.home_lon != null) {
			place(h.home_lat, h.home_lon);
			map.jumpTo({ center: [h.home_lon, h.home_lat], zoom: 11 });
		}
		map.on('click', (e) => {
			if (!h) return;
			h.home_lat = Math.round(e.lngLat.lat * 1e5) / 1e5;
			h.home_lon = Math.round(e.lngLat.lng * 1e5) / 1e5;
			place(h.home_lat, h.home_lon);
		});
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
		try {
			await api.put('/api/settings/household', {
				...h,
				history_start: historyDate ? `${historyDate}T00:00:00Z` : null
			});
			saved = true;
			onsaved?.();
		} catch (err) {
			error = String(err);
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
			<small>{t('home_hint')}</small>
			<div class="map"><MapView onready={onMap} zoom={4} /></div>
			{#if h.home_lat != null}<small>{h.home_lat}, {h.home_lon}</small>{/if}
		</div>
		<div class="grid">
			<label class="field">
				<span>{t('home_radius')}</span>
				<input type="number" min="0.5" max="50" step="0.5" bind:value={h.home_radius_km} />
			</label>
			<label class="field">
				<span>{t('timezone')}</span>
				<select bind:value={h.timezone}>
					{#each zones as z (z)}<option value={z}>{z}</option>{/each}
				</select>
			</label>
			<label class="field">
				<span>{t('default_language')}</span>
				<select bind:value={h.default_locale}>
					{#each LANGUAGES as l (l.code)}<option value={l.code}>{l.name}</option>{/each}
				</select>
			</label>
			<label class="field">
				<span>{t('history_start')}</span>
				<input type="date" bind:value={historyDate} />
			</label>
			<label class="field">
				<span>{t('min_nights')}</span>
				<input type="number" min="1" max="30" bind:value={h.min_trip_nights} />
			</label>
			<label class="field">
				<span>{t('min_distance')}</span>
				<input type="number" min="1" bind:value={h.min_trip_distance_km} />
			</label>
		</div>
		<label class="row check">
			<input type="checkbox" bind:checked={h.place_info_enabled} />
			<span>{t('place_info_enabled')}</span>
		</label>
		<small class="muted">{t('place_info_hint')}</small>
		{#if error}<p class="error">{error}</p>{/if}
		{#if saved}<p class="success">{t('saved')}</p>{/if}
		<div class="row actions"><button class="btn primary">{t('save')}</button></div>
	</form>
{:else}
	<p class="muted">{t('loading')}</p>
{/if}

<style>
	.map {
		position: relative;
		height: 280px;
		border-radius: var(--radius-sm);
		overflow: hidden;
		border: 1px solid var(--border);
		cursor: crosshair;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0 14px;
	}
	.check {
		gap: 0.5em;
		flex-wrap: nowrap;
	}
	.actions {
		margin-top: 14px;
	}
</style>
