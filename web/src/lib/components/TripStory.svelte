<script lang="ts">
	// A trip told as a story: the route on a map, then one chapter per place they slept, with photos and a text about
	// the place. Children see it with child-friendly texts ("Did you know?"); the diary for everyone else adds the
	// notes of the trip and of each place, videos and every photo of a place.
	import maplibregl from 'maplibre-gl';
	import { api, thumbUrl } from '$lib/api';
	import { backTo } from '$lib/back.svelte';
	import { onPhotoDeleted } from '$lib/photoDeleted.svelte';
	import { canEdit } from '$lib/stores/session.svelte';
	import { date, flag, km, tripTitle } from '$lib/format';
	import { plural, t } from '$lib/i18n/index.svelte';
	import MapView from '$lib/map/MapView.svelte';
	import { boundsOf, TrackLayer } from '$lib/map/trackLayer';
	import type { Photo, TrackPoint, TripDetail } from '$lib/types';
	import NoteView from './NoteView.svelte';
	import PhotoViewer from './PhotoViewer.svelte';
	import PlaceCard from './PlaceCard.svelte';

	let { id, kids = false, back }: { id: number; kids?: boolean; back: { href: string; label: string } } = $props();

	let trip = $state<TripDetail | null>(null);
	let points: TrackPoint[] = [];
	let photos = $state<Photo[]>([]);
	let viewer = $state<{ ids: string[]; index: number; overview?: boolean } | null>(null);
	let map: maplibregl.Map | undefined;
	let layer: TrackLayer | undefined;

	$effect(() => {
		const tripId = id;
		trip = null;
		photos = [];
		Promise.all([
			api.get<TripDetail>(`/api/trips/${tripId}`),
			api.get<{ points: TrackPoint[] }>(`/api/trips/${tripId}/track`)
		]).then(([d, tr]) => {
			trip = d;
			points = tr.points;
			draw();
		});
		api
			.get<{ photos: Photo[] }>(`/api/trips/${tripId}/photos`)
			.then((r) => (photos = kids ? r.photos.filter((p) => !p.is_video) : r.photos));
	});

	function draw() {
		if (!map || !layer || !trip) return;
		layer.install();
		layer.setSelected(points, trip.start, trip.end, trip.stays);
		const b = boundsOf(points.map((p) => ({ lat: p[1], lon: p[2] })));
		if (b) map.fitBounds(b, { padding: 40, duration: 0 });
	}

	function photosAt(from: number, to: number) {
		return photos.filter((p) => p.t >= from && p.t <= to);
	}

	/** A handful of photos spread over the stay, not ten of the same moment. */
	function spread(list: Photo[], n = 6) {
		if (list.length <= n) return list;
		return Array.from({ length: n }, (_, i) => list[Math.floor((i * list.length) / n)]);
	}

	function drop(photoId: string) {
		photos = photos.filter((p) => p.id !== photoId);
		if (viewer) {
			const ids = viewer.ids.filter((x) => x !== photoId);
			viewer = ids.length ? { ...viewer, ids, index: Math.min(viewer.index, ids.length - 1) } : null;
		}
	}
	onPhotoDeleted(drop);

	/** "Does not belong to this trip" from the viewer: the trip forgets the photo, the viewer moves on. */
	async function exclude(photoId: string) {
		drop(photoId);
		await api.post(`/api/trips/${id}/photos/${photoId}/exclude`);
	}

	function open(list: Photo[], p: Photo | null) {
		const ids = list.map((x) => x.id);
		viewer = { ids, index: p ? ids.indexOf(p.id) : 0, overview: !p };
	}
</script>

<div class="story" class:kids>
	<div class="top">
		<a class="back btn small" href={back.href} onclick={(e) => (e.preventDefault(), backTo(back.href))}>← {back.label}</a>
		{#if !kids}<a class="btn small" href="/?trip={id}">🗺 {t('diary_on_map')}</a>{/if}
	</div>
	{#if trip}
		<header>
			{#if trip.cover_asset}<img class="cover" src={thumbUrl(trip.cover_asset, 'preview')} alt="" />{/if}
			<h1>{tripTitle(trip, t('trip_untitled'))} {trip.countries.map(flag).join(' ')}</h1>
			{#if kids}
				<p class="intro">{t('kids_intro', { nights: trip.nights, km: km(trip.distance_km), places: trip.stays.length })}</p>
			{:else}
				<p class="intro">
					{date(trip.start, { day: 'numeric', month: 'long', year: 'numeric' })} · {plural('nights', trip.nights)} ·
					{km(trip.distance_km)} · {plural('places', trip.stays.length)}{#if photos.length}{' · '}{plural('photos', photos.length)}{/if}
				</p>
				{#if trip.note_html}<div class="note card"><NoteView html={trip.note_html} /></div>{/if}
			{/if}
		</header>

		<div class="map card">
			<MapView
				style="liberty"
				onready={(m) => {
					map = m;
					layer = new TrackLayer(m, () => {});
					draw();
				}}
				onstyle={() => draw()}
			/>
		</div>

		{#each trip.stays as st, i (st.id)}
			{@const all = photosAt(st.arrival, st.departure)}
			{@const list = spread(all)}
			<section class="chapter card">
				<div class="num">{i + 1}</div>
				<h2>{st.title || st.place_name || t('stay')} {flag(st.country_code)}</h2>
				<p class="muted">{date(st.arrival, { weekday: 'long', day: 'numeric', month: 'long' })} · {plural('nights', st.nights)}</p>
				{#if !kids && st.note_html}<div class="stay-note"><NoteView html={st.note_html} /></div>{/if}
				{#if list.length}
					<div class="photos">
						{#each list as p (p.id)}
							<button onclick={() => open(all, p)}>
								<img src={thumbUrl(p.id, 'preview')} alt="" loading="lazy" />
								{#if p.is_video}<span class="play" aria-label="Video">▶</span>{/if}
							</button>
						{/each}
					</div>
					{#if !kids && all.length > list.length}
						<button class="btn small" onclick={() => open(all, null)}>{t('diary_all_photos', { n: all.length })}</button>
					{/if}
				{/if}
				<div class="did-you-know">
					<h3>{kids ? `💡 ${t('kids_did_you_know')}` : `📖 ${t('about_place')}`}</h3>
					<PlaceCard lat={st.lat} lon={st.lon} {kids} />
				</div>
			</section>
		{/each}
		{#if !trip.ongoing}<p class="end">🏁 {kids ? t('kids_the_end') : t('diary_the_end')}</p>{/if}
	{:else}
		<p class="muted">{t('loading')}</p>
	{/if}
</div>

{#if viewer}
	<PhotoViewer ids={viewer.ids} bind:index={viewer.index} overview={viewer.overview}
		onexclude={!kids && canEdit() ? exclude : undefined} onclose={() => (viewer = null)} />
{/if}

<style>
	.story {
		max-width: 820px;
		margin: 0 auto;
		padding: 16px 16px 60px;
		font-size: 17px;
	}
	.top {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
	.cover {
		width: 100%;
		aspect-ratio: 16/9;
		/* turned phone: no taller than most of the screen (dvh is ignored where unknown) */
		max-height: 70dvh;
		object-fit: cover;
		border-radius: 24px;
		margin-top: 12px;
	}
	h1 {
		font-size: 2em;
		margin: 14px 0 6px;
	}
	.intro {
		font-size: 1.15em;
	}
	.story:not(.kids) .intro {
		color: var(--text-2);
		font-size: 1em;
	}
	.note {
		padding: 14px 18px;
		border-radius: 18px;
		margin-top: 10px;
	}
	.map {
		position: relative;
		height: 340px;
		border-radius: 24px;
		overflow: hidden;
		margin: 18px 0 26px;
	}
	.chapter {
		position: relative;
		padding: 20px 20px 20px 74px;
		margin-bottom: 18px;
		border-radius: 24px;
	}
	.num {
		position: absolute;
		left: 18px;
		top: 18px;
		width: 40px;
		height: 40px;
		border-radius: 50%;
		background: var(--accent);
		color: var(--accent-text);
		display: grid;
		place-items: center;
		font-weight: 800;
		font-size: 1.2em;
	}
	.chapter h2 {
		margin: 4px 0 2px;
	}
	.stay-note {
		margin: 10px 0;
	}
	.photos {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 8px;
		margin: 12px 0;
	}
	.photos button {
		position: relative;
		padding: 0;
		border: 0;
		background: none;
		cursor: zoom-in;
	}
	.photos img {
		width: 100%;
		aspect-ratio: 1;
		object-fit: cover;
		border-radius: 14px;
		display: block;
	}
	.play {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		color: #fff;
		font-size: 26px;
		text-shadow: 0 1px 4px rgb(0 0 0 / 70%);
		pointer-events: none;
	}
	.did-you-know {
		background: var(--surface-2);
		border-radius: 18px;
		padding: 12px 16px;
		margin-top: 12px;
	}
	.did-you-know h3 {
		margin: 0 0 6px;
	}
	.end {
		text-align: center;
		font-size: 1.3em;
		margin-top: 30px;
	}
	@media (max-width: 560px) {
		.chapter {
			padding: 64px 16px 16px;
		}
		.photos {
			grid-template-columns: repeat(2, 1fr);
		}
	}
</style>
