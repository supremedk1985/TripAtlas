<script lang="ts">
	// The explorer: trips of all visible trackers on one map, a photo layer independent of trackers, and the detail
	// panel of a selected trip. The selected trip is in the URL (?trip=…) so it can be bookmarked and shared.
	import maplibregl from 'maplibre-gl';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, thumbUrl } from '$lib/api';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import PhotoViewer from '$lib/components/PhotoViewer.svelte';
	import TripPanel from '$lib/components/TripPanel.svelte';
	import { dateRange, flag, km, tripTitle } from '$lib/format';
	import { plural, t } from '$lib/i18n/index.svelte';
	import type { MapControl } from '$lib/map/control';
	import MapView from '$lib/map/MapView.svelte';
	import { PhotoLayer } from '$lib/map/photoLayer';
	import { MAP_STYLES, preferredStyle, rememberStyle, type MapStyleId } from '$lib/map/styles';
	import { boundsOf, positionAt, TrackLayer } from '$lib/map/trackLayer';
	import type { Photo, Tracker, TrackPoint, TripSummary } from '$lib/types';

	let map = $state<maplibregl.Map>();
	// $state so effects that use the layers re-run once the map has created them
	let photoLayer = $state<PhotoLayer>();
	let trackLayer = $state<TrackLayer>();
	let liveMarkers: maplibregl.Marker[] = [];

	let trackers = $state<Tracker[]>([]);
	let trips = $state<TripSummary[]>([]);
	let hidden = $state<Set<number>>(new Set());
	let showPhotos = $state(true);
	let showTracks = $state(true);
	let style = $state<MapStyleId>(preferredStyle());
	let allMarkers = $state<[string, number, number][]>([]);
	let photoNote = $state('');
	let tracks = new Map<number, TrackPoint[]>();
	let viewer = $state<{ ids: string[]; index: number; times: Record<string, number>; videos?: Set<string> } | null>(null);
	let selectedPoints: TrackPoint[] = [];
	let selectedStays: { lat: number; lon: number }[] = [];

	const selectedId = $derived(Number(page.url.searchParams.get('trip')) || null);
	const visibleTrips = $derived(trips.filter((tr) => !hidden.has(tr.tracker_id)));
	const byYear = $derived.by(() => {
		const groups = new Map<number, TripSummary[]>();
		for (const tr of visibleTrips) {
			const y = new Date(tr.start * 1000).getFullYear();
			if (!groups.has(y)) groups.set(y, []);
			groups.get(y)!.push(tr);
		}
		return [...groups.entries()];
	});
	const trackerOf = (id: number) => trackers.find((tk) => tk.id === id);

	let loaded = $state(false);
	let busy = $state(false);

	async function loadData() {
		[trackers, trips] = await Promise.all([api.get<Tracker[]>('/api/trackers'), api.get<TripSummary[]>('/api/trips')]);
		loaded = true;
		if (!trips.length) watchFirstSync();
		api.get<{ markers: [string, number, number][]; error?: string }>('/api/photos/markers').then((r) => {
			allMarkers = r.markers;
			photoNote = r.error ? t('photos_unavailable') : '';
		});
		// Tracks for the overview, newest first so the recent trips appear quickly.
		for (const tr of trips) {
			if (tracks.has(tr.id)) continue;
			const r = await api.get<{ points: TrackPoint[] }>(`/api/trips/${tr.id}/track`);
			tracks.set(tr.id, r.points);
			drawOverview();
		}
	}

	/** Right after setup the history is still being fetched: say so, and load the trips as soon as it is done. */
	async function watchFirstSync() {
		for (let i = 0; i < 120; i++) {
			const s = await api.get<{ busy: boolean }>('/api/setup/status').catch(() => ({ busy: false }));
			busy = s.busy;
			if (!s.busy && i > 0) break;
			await new Promise((r) => setTimeout(r, 5000));
		}
		busy = false;
		const fresh = await api.get<TripSummary[]>('/api/trips');
		if (fresh.length) {
			trips = fresh;
			for (const tr of trips) {
				const r = await api.get<{ points: TrackPoint[] }>(`/api/trips/${tr.id}/track`);
				tracks.set(tr.id, r.points);
			}
			drawOverview();
			fitAll();
		}
	}

	function drawOverview() {
		if (!trackLayer) return;
		// With a trip open, the map shows only that trip — the others would cover its route.
		const list = showTracks && selectedId === null ? visibleTrips : [];
		trackLayer.setOverview(
			list
				.filter((tr) => tracks.has(tr.id))
				.map((tr) => ({ tripId: tr.id, color: trackerOf(tr.tracker_id)?.color ?? '#3b82f6', points: tracks.get(tr.id)! }))
		);
	}

	function drawLive() {
		liveMarkers.forEach((m) => m.remove());
		liveMarkers = [];
		if (!map) return;
		if (selectedId) return; // a selected trip has its own vehicle marker
		for (const tk of trackers) {
			if (!tk.latest || hidden.has(tk.id)) continue;
			const el = document.createElement('div');
			el.className = 'vehicle-marker live';
			el.style.setProperty('--c', tk.color);
			if (tk.has_avatar) el.style.backgroundImage = `url(/api/trackers/${tk.id}/avatar)`;
			el.title = tk.name;
			liveMarkers.push(new maplibregl.Marker({ element: el }).setLngLat([tk.latest.lon, tk.latest.lat]).addTo(map));
		}
	}

	function onReady(m: maplibregl.Map) {
		map = m;
		photoLayer = new PhotoLayer(m, (ids, index) => (viewer = { ids, index, times: {} }));
		trackLayer = new TrackLayer(m, (id) => selectTrip(id));
		installLayers(m);
		loadData().then(() => {
			drawLive();
			if (!selectedId) fitAll();
		});
	}

	function installLayers(m: maplibregl.Map) {
		trackLayer?.install();
		photoLayer?.install();
		drawOverview();
	}

	function fitAll() {
		const pts = visibleTrips.map((tr) => ({ lat: tr.destination[0], lon: tr.destination[1] }));
		trackers.forEach((tk) => tk.latest && pts.push({ lat: tk.latest.lat, lon: tk.latest.lon }));
		const b = boundsOf(pts);
		if (b && map) map.fitBounds(b, { padding: 80, maxZoom: 9, duration: 0 });
	}

	function selectTrip(id: number | null) {
		const url = new URL(page.url);
		if (id) url.searchParams.set('trip', String(id));
		else url.searchParams.delete('trip');
		goto(url, { replaceState: false, keepFocus: true, noScroll: true });
	}

	// The photo layer shows all photos — or only the selected trip's photos.
	let tripPhotos = $state<Photo[] | null>(null);
	$effect(() => {
		if (!photoLayer) return;
		const pts = tripPhotos ?? allMarkers.map(([id, lat, lon]) => ({ id, lat, lon }));
		photoLayer.setPhotos(pts);
		photoLayer.setVisible(showPhotos);
	});

	$effect(() => {
		// re-draw when filters or the selection change
		void [showTracks, hidden, selectedId, trips.length];
		drawOverview();
		drawLive();
		if (!selectedId) {
			tripPhotos = null;
			trackLayer?.clearSelected();
		}
	});

	const control: MapControl = {
		showTrip(points, stays, color, avatarUrl) {
			selectedPoints = points;
			selectedStays = stays;
			trackLayer?.setVehicle(null);
			trackLayer?.setSelected(points, points[0]?.[0] ?? 0, points.at(-1)?.[0] ?? 0, stays);
			trackLayer?.setVehicle(positionAt(points, points.at(-1)?.[0] ?? 0), color, avatarUrl);
		},
		setRange(from, to, follow) {
			trackLayer?.setSelected(selectedPoints, from, to, selectedStays);
			const pos = positionAt(selectedPoints, to);
			trackLayer?.setVehicle(pos);
			if (follow && pos && map) map.easeTo({ center: [pos[1], pos[0]], duration: 0 });
		},
		clearTrip() {
			trackLayer?.clearSelected();
		},
		fit(points) {
			const b = boundsOf(points);
			const left = matchMedia('(min-width: 860px)').matches ? 40 : 30;
			if (b && map) map.fitBounds(b, { padding: { top: 70, bottom: 40, left, right: 40 }, maxZoom: 14 });
		},
		focus(lat, lon, zoom = 12) {
			map?.flyTo({ center: [lon, lat], zoom });
		},
		showTripPhotos(photos) {
			tripPhotos = photos;
		},
		openPhotos(ids, index, times = {}, videos) {
			viewer = { ids, index, times, videos };
		}
	};

	function toggleTracker(id: number) {
		const next = new Set(hidden);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		hidden = next;
	}
</script>

<div class="layout">
	<aside class:trip-open={selectedId !== null}>
		<AppHeader />
		{#if selectedId && map}
			<TripPanel
				tripId={selectedId}
				tracker={trackerOf(trips.find((tr) => tr.id === selectedId)?.tracker_id ?? -1)}
				{control}
				onclose={() => selectTrip(null)}
			/>
		{:else if selectedId}
			<p class="muted pad">{t('loading')}</p>
		{:else}
			<div class="list">
				{#if trackers.length > 1}
					<div class="row filters">
						{#each trackers as tk (tk.id)}
							<button class="chip" class:on={!hidden.has(tk.id)} onclick={() => toggleTracker(tk.id)}>
								<span class="dot" style="background:{tk.color}"></span>{tk.name}
							</button>
						{/each}
					</div>
				{/if}
				<div class="row layers">
					<label class="chip" class:on={showTracks}><input type="checkbox" hidden bind:checked={showTracks} />{t('layer_routes')}</label>
					<label class="chip" class:on={showPhotos}><input type="checkbox" hidden bind:checked={showPhotos} />{t('layer_photos')}</label>
					<span class="spacer"></span>
					<select bind:value={style} onchange={() => rememberStyle(style)} aria-label={t('map_style')}>
						{#each MAP_STYLES as s (s.id)}<option value={s.id}>{t(s.label)}</option>{/each}
					</select>
				</div>
				{#if photoNote}<p class="muted small">{photoNote}</p>{/if}

				{#if !trips.length && loaded}
					<div class="empty card">
						{#if busy}
							<h3><span class="spin" aria-hidden="true"></span> {t('loading_history_title')}</h3>
							<p class="muted">{t('loading_history_text')}</p>
						{:else}
							<h3>{t('no_trips_title')}</h3>
							<p class="muted">{t('no_trips_text')}</p>
						{/if}
					</div>
				{/if}
				{#each byYear as [year, list] (year)}
					<h3 class="year">{year} <span class="muted">· {plural('trips', list.length)}</span></h3>
					{#each list as tr (tr.id)}
						{@const tk = trackerOf(tr.tracker_id)}
						<button class="trip card" onclick={() => selectTrip(tr.id)}>
							{#if tr.cover_asset}
								<img src={thumbUrl(tr.cover_asset)} alt="" loading="lazy" />
							{:else}
								<span class="noimg" style="background:{tk?.color}">✦</span>
							{/if}
							<span class="info">
								<strong>{tripTitle(tr, t('trip_untitled'))}</strong>
								<span class="muted">{dateRange(tr.start, tr.end)}</span>
								<span class="muted small">
									{plural('nights', tr.nights)} · {km(tr.distance_km)}{#if tr.photo_count}{' · '}{plural('photos', tr.photo_count)}{/if}
								</span>
								<span class="flags">
									{#if trackers.length > 1}<span class="dot" style="background:{tk?.color}" title={tk?.name}></span>{/if}
									{tr.countries.map(flag).join(' ')}
									{#if tr.ongoing}<span class="live">● {t('trip_ongoing')}</span>{/if}
								</span>
							</span>
						</button>
					{/each}
				{/each}
			</div>
		{/if}
	</aside>
	<main>
		<MapView {style} onready={onReady} onstyle={installLayers} />
	</main>
</div>

{#if viewer}
	<PhotoViewer ids={viewer.ids} bind:index={viewer.index} times={viewer.times} videos={viewer.videos} onclose={() => (viewer = null)} />
{/if}

<style>
	/* Pinned to the window instead of 100vh/100dvh: in an Android WebView the viewport units resolved to 0. */
	.layout {
		position: fixed;
		inset: 0;
		display: grid;
		grid-template-columns: var(--sidebar) 1fr;
	}
	aside {
		overflow-y: auto;
		border-right: 1px solid var(--border);
		background: var(--bg);
		padding: 12px 0 0;
	}
	aside > :global(nav) {
		margin: 0 12px;
	}
	main {
		position: relative;
		min-height: 0;
	}
	.list {
		padding: 12px 16px 24px;
	}
	.filters,
	.layers {
		margin-bottom: 10px;
	}
	.layers select {
		width: auto;
		padding: 0.25em 0.5em;
		font-size: 0.86em;
		border-radius: 999px;
	}
	.dot {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 50%;
	}
	.year {
		margin: 18px 0 8px;
		font-size: 1.05em;
	}
	.trip {
		display: flex;
		gap: 12px;
		width: 100%;
		padding: 8px;
		margin-bottom: 8px;
		text-align: left;
		cursor: pointer;
		box-shadow: none;
	}
	.trip:hover {
		border-color: var(--accent);
	}
	.trip img,
	.noimg {
		width: 76px;
		height: 76px;
		border-radius: 10px;
		object-fit: cover;
		flex: none;
	}
	.noimg {
		display: grid;
		place-items: center;
		color: #fff;
		font-size: 1.6em;
	}
	.info {
		display: grid;
		align-content: center;
		gap: 1px;
		min-width: 0;
	}
	.info strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.small {
		font-size: 0.86em;
	}
	.flags {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 0.95em;
	}
	.live {
		color: var(--danger);
		font-size: 0.85em;
	}
	.pad {
		padding: 16px;
	}
	.spin {
		display: inline-block;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		animation: spin 0.9s linear infinite;
		vertical-align: -1px;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.empty {
		padding: 16px;
		box-shadow: none;
	}
	@media (max-width: 860px) {
		.layout {
			grid-template-columns: 1fr;
			grid-template-rows: minmax(240px, 46%) 1fr;
			grid-template-areas: 'map' 'side';
		}
		main {
			grid-area: map;
		}
		/* with a trip open the back button is enough; the header would take a fifth of the screen */
		aside.trip-open > :global(nav) {
			display: none;
		}
		aside {
			grid-area: side;
			border-right: 0;
			border-top: 1px solid var(--border);
		}
	}
</style>
