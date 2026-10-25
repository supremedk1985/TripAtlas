<script lang="ts">
	// The explorer: trips of all visible trackers on one map, a photo layer independent of trackers, and the detail
	// panel of a selected trip. The selected trip is in the URL (?trip=…) so it can be bookmarked and shared.
	import { vehicleMarker } from '$lib/map/vehicleMarker';
	import maplibregl from 'maplibre-gl';
	import { goto } from '$app/navigation';
	import { backLayer, backTo } from '$lib/back.svelte';
	import { page } from '$app/state';
	import { api, errorText, thumbUrl } from '$lib/api';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import PhotoViewer from '$lib/components/PhotoViewer.svelte';
	import TripPanel from '$lib/components/TripPanel.svelte';
	import VehicleIcon from '$lib/components/VehicleIcon.svelte';
	import { dateRange, dateTime, flag, km, tripTitle } from '$lib/format';
	import { plural, t } from '$lib/i18n/index.svelte';
	import type { MapControl } from '$lib/map/control';
	import MapView from '$lib/map/MapView.svelte';
	import { PhotoLayer } from '$lib/map/photoLayer';
	import { NotesLayer } from '$lib/map/notesLayer';
	import { confirmDialog, promptDialog } from '$lib/stores/dialog.svelte';
	import { canEdit, isAdmin, session } from '$lib/stores/session.svelte';
	import { MAP_STYLES, preferredStyle, rememberStyle, type MapStyleId } from '$lib/map/styles';
	import { boundsOf, positionAt, TrackLayer } from '$lib/map/trackLayer';
	import type { MapNote, Photo, Tracker, TrackPoint, TripSummary } from '$lib/types';

	let map = $state<maplibregl.Map>();
	// $state so effects that use the layers re-run once the map has created them
	let photoLayer = $state<PhotoLayer>();
	let trackLayer = $state<TrackLayer>();
	let liveMarkers: maplibregl.Marker[] = [];

	let trackers = $state<Tracker[]>([]);
	let trips = $state<TripSummary[]>([]);
	let hidden = $state<Set<number>>(new Set());
	let showPhotos = $state(true);
	let showNotes = $state(true);
	let notes = $state<MapNote[]>([]);
	let notesLayer: NotesLayer | undefined;
	let note = $state<MapNote | null>(null);   // the note whose card is open
	backLayer(() => note !== null, () => (note = null));
	let showTracks = $state(true);
	let style = $state<MapStyleId>(preferredStyle());
	let allMarkers = $state<[string, number, number][]>([]);
	let photoNote = $state('');
	let tracks = new Map<number, TrackPoint[]>();
	let viewer = $state<{
		ids: string[];
		index: number;
		times: Record<string, number>;
		videos?: Set<string>;
		overview?: boolean;
		/** where the photos are: a note made in the viewer is pinned here */
		at?: { lat: number; lon: number };
	} | null>(null);
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

	async function loadNotes() {
		notes = await api.get<MapNote[]>('/api/notes').catch(() => []);
		notesLayer?.setNotes(notes);
	}

	$effect(() => notesLayer?.setVisible(showNotes));

	/** Pin a note to the place of the photos in the viewer ("our first campsite"). */
	async function pinNote(photoId: string) {
		// pinned where the photo shown was taken — the middle of a big stack (zoomed out) can be nowhere
		const at = photoLayer?.position(photoId) ?? viewer?.at;
		if (!at) {
			await confirmDialog(t('note_no_place'), { confirmLabel: t('ok') });
			return;
		}
		const text = await promptDialog(t('note_pin_title'), { text: t('note_pin_hint'), confirmLabel: t('note_pin'), maxLength: 500 });
		if (!text?.trim()) return;
		try {
			await api.post('/api/notes', { lat: at.lat, lon: at.lon, text: text.trim(), photo_id: photoId });
		} catch (err) {
			await confirmDialog(errorText(err), { confirmLabel: t('ok') });
			return;
		}
		viewer = null;
		await loadNotes();
	}

	async function editNote(n: MapNote) {
		const text = await promptDialog(t('note_edit'), { value: n.text, confirmLabel: t('save'), maxLength: 500 });
		if (!text?.trim()) return;
		await api.patch(`/api/notes/${n.id}`, { text: text.trim() });
		note = null;
		await loadNotes();
	}

	async function deleteNote(n: MapNote) {
		if (!(await confirmDialog(t('note_delete_confirm', { text: n.text }), { danger: true, confirmLabel: t('delete') }))) return;
		await api.del(`/api/notes/${n.id}`);
		note = null;
		await loadNotes();
	}

	function notePhotos(n: MapNote) {
		const ids = photoLayer?.photosNear(n.lat, n.lon) ?? [];
		const start = n.photo_id ? Math.max(0, ids.indexOf(n.photo_id)) : 0;
		if (ids.length) viewer = { ids, index: start, times: {}, overview: ids.length > 1, at: { lat: n.lat, lon: n.lon } };
		note = null;
	}

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
			const el = vehicleMarker({
				color: tk.color,
				kind: tk.kind,
				avatarUrl: tk.has_avatar ? `/api/trackers/${tk.id}/avatar` : undefined,
				title: tk.name,
				live: true
			});
			liveMarkers.push(new maplibregl.Marker({ element: el }).setLngLat([tk.latest.lon, tk.latest.lat]).addTo(map));
		}
	}

	function onReady(m: maplibregl.Map) {
		map = m;
		photoLayer = new PhotoLayer(m, (ids, index, at) => (viewer = { ids, index, times: {}, overview: true, at }));
		notesLayer = new NotesLayer(m, (n) => (note = n));
		loadNotes();
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
		else {
			// closing a trip opened from the list goes back, so the back gesture afterwards does not reopen it
			url.searchParams.delete('trip');
			return backTo(url.pathname + url.search);
		}
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
		showTrip(points, stays, color, avatarUrl, kind) {
			selectedPoints = points;
			selectedStays = stays;
			trackLayer?.setVehicle(null);
			trackLayer?.setSelected(points, points[0]?.[0] ?? 0, points.at(-1)?.[0] ?? 0, stays);
			trackLayer?.setVehicle(positionAt(points, points.at(-1)?.[0] ?? 0), color, avatarUrl, kind);
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

	// Full screen: only the map. In a browser also the real full-screen mode; in an app's WebView that may be
	// refused, then the map still fills the app.
	let full = $state(false);
	backLayer(() => full, () => full && toggleFull());
	async function toggleFull() {
		full = !full;
		if (full) await document.documentElement.requestFullscreen?.().catch(() => {});
		else if (document.fullscreenElement) await document.exitFullscreen().catch(() => {});
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && full && !viewer && toggleFull()} />
<svelte:document onfullscreenchange={() => !document.fullscreenElement && (full = false)} />

<div class="layout" class:full>
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
								<VehicleIcon color={tk.color} kind={tk.kind} />{tk.name}
							</button>
						{/each}
					</div>
				{/if}
				<div class="row layers">
					<label class="chip" class:on={showTracks}><input type="checkbox" hidden bind:checked={showTracks} />{t('layer_routes')}</label>
					<label class="chip" class:on={showPhotos}><input type="checkbox" hidden bind:checked={showPhotos} />{t('layer_photos')}</label>
					{#if notes.length}<label class="chip" class:on={showNotes}><input type="checkbox" hidden bind:checked={showNotes} />{t('layer_notes')}</label>{/if}
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
						{:else if !trackers.length}
							<h3>{t('no_trips_title')}</h3>
							<p class="muted">{t(isAdmin() ? 'no_trackers_admin' : 'no_trackers_member')}</p>
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
								<span class="noimg" style="background:{tk?.color}" title={t('trip_no_photos')}>{tk?.kind === 'bike' ? '🚲' : tk?.kind === 'camper' ? '🚐' : tk?.kind === 'person' ? '🚶' : '🚗'}</span>
							{/if}
							<span class="info">
								<strong>{tripTitle(tr, t('trip_untitled'))}</strong>
								<span class="muted">{dateRange(tr.start, tr.end)}</span>
								<span class="muted small">
									{plural('nights', tr.nights)} · {km(tr.distance_km)}{#if tr.photo_count}{' · '}{plural('photos', tr.photo_count)}{/if}
								</span>
								<span class="flags">
									{#if trackers.length > 1}<VehicleIcon color={tk?.color} kind={tk?.kind} title={tk?.name} />{/if}
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
		<button class="full-btn icon-btn" onclick={toggleFull} aria-pressed={full}
			title={full ? t('map_fullscreen_exit') : t('map_fullscreen')} aria-label={full ? t('map_fullscreen_exit') : t('map_fullscreen')}>
			<svg viewBox="0 0 24 24" aria-hidden="true">
				{#if full}<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />{:else}<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />{/if}
			</svg>
		</button>
		{#if allMarkers.length || tripPhotos?.length}
			<button class="photos-btn icon-btn" class:off={!showPhotos} onclick={() => (showPhotos = !showPhotos)} aria-pressed={showPhotos}
				title={showPhotos ? t('map_photos_hide') : t('map_photos_show')} aria-label={showPhotos ? t('map_photos_hide') : t('map_photos_show')}>
				<svg viewBox="0 0 24 24" aria-hidden="true">
					<rect x="3" y="6" width="15" height="12" rx="2" /><path d="M7 3h12a2 2 0 0 1 2 2v10" /><circle cx="8" cy="10.5" r="1.5" /><path d="M18 15l-4-4-7 7" />
					{#if !showPhotos}<path class="slash" d="M3 3l18 18" />{/if}
				</svg>
			</button>
		{/if}
	</main>
</div>

{#if note}
	<div class="note-card card" role="dialog" aria-label={t('note_label')}>
		<button class="close icon-btn" onclick={() => (note = null)} aria-label={t('close')}>✕</button>
		<p class="note-text">📌 {note.text}</p>
		<p class="muted small">{note.author ? note.author + ' · ' : ''}{dateTime(new Date(note.created_at).getTime() / 1000)}</p>
		<div class="row">
			{#if photoLayer?.photosNear(note.lat, note.lon).length}
				<button class="btn small primary" onclick={() => notePhotos(note!)}>{t('note_photos')}</button>
			{/if}
			{#if canEdit() && (note.created_by === session.user?.id || isAdmin())}
				<button class="btn small" onclick={() => editNote(note!)}>{t('note_edit')}</button>
				<button class="btn small danger" onclick={() => deleteNote(note!)}>{t('delete')}</button>
			{/if}
		</div>
	</div>
{/if}

{#if viewer}
	<PhotoViewer ids={viewer.ids} bind:index={viewer.index} times={viewer.times} videos={viewer.videos} overview={viewer.overview}
		onnote={canEdit() ? pinNote : undefined} onclose={() => (viewer = null)} />
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
	.note-card {
		position: fixed;
		left: 50%;
		bottom: 16px;
		transform: translateX(-50%);
		z-index: 60;
		width: min(380px, calc(100% - 32px));
		padding: 14px 16px 12px;
		background: #fef3c7;
		color: #422006;
		box-shadow: 0 8px 24px rgb(0 0 0 / 25%);
	}
	.note-card .close {
		position: absolute;
		top: 8px;
		right: 8px;
	}
	.note-text {
		margin: 0 32px 6px 0;
		font-size: 1.05em;
		font-weight: 600;
		white-space: pre-wrap;
	}
	.note-card .muted {
		color: #78350f;
		margin: 0 0 10px;
	}
	.full-btn,
	.photos-btn {
		position: absolute;
		top: 10px;
		left: 10px;
		z-index: 4;
		box-shadow: 0 1px 4px rgb(0 0 0 / 25%);
	}
	.photos-btn {
		top: 58px;
	}
	.photos-btn.off {
		color: var(--text-2);
	}
	.photos-btn .slash {
		stroke-width: 2.4;
	}
	.full-btn svg,
	.photos-btn svg {
		width: 18px;
		height: 18px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	/* two classes beat the phone layout's .layout below */
	.layout.full {
		grid-template-columns: 1fr;
		grid-template-rows: 1fr;
		grid-template-areas: 'map';
	}
	.layout.full aside {
		display: none;
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
	/* a phone turned sideways: list and map next to each other, the list a bit narrower */
	@media (max-width: 1000px) and (orientation: landscape) and (max-height: 560px) {
		.layout {
			grid-template-columns: minmax(290px, 42%) 1fr;
		}
	}
	@media (max-width: 860px) and (orientation: portrait) {
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
