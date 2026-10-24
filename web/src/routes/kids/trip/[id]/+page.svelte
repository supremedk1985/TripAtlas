<script lang="ts">
	// A trip told as a story for children: the route on a map, then one chapter per place they slept,
	// with photos and a child-friendly "Did you know?" text.
	import maplibregl from 'maplibre-gl';
	import { page } from '$app/state';
	import { api, thumbUrl } from '$lib/api';
	import PhotoViewer from '$lib/components/PhotoViewer.svelte';
	import PlaceCard from '$lib/components/PlaceCard.svelte';
	import { date, flag, km, tripTitle } from '$lib/format';
	import { plural, t } from '$lib/i18n/index.svelte';
	import MapView from '$lib/map/MapView.svelte';
	import { boundsOf, TrackLayer } from '$lib/map/trackLayer';
	import type { Photo, TrackPoint, TripDetail } from '$lib/types';

	const id = Number(page.params.id);
	let trip = $state<TripDetail | null>(null);
	let points: TrackPoint[] = [];
	let photos = $state<Photo[]>([]);
	let viewer = $state<{ ids: string[]; index: number } | null>(null);
	let map: maplibregl.Map | undefined;
	let layer: TrackLayer | undefined;

	Promise.all([api.get<TripDetail>(`/api/trips/${id}`), api.get<{ points: TrackPoint[] }>(`/api/trips/${id}/track`)]).then(
		([d, tr]) => {
			trip = d;
			points = tr.points;
			draw();
		}
	);
	api.get<{ photos: Photo[] }>(`/api/trips/${id}/photos`).then((r) => (photos = r.photos.filter((p) => !p.is_video)));

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
</script>

<div class="story">
	<a class="back btn small" href="/kids">← {t('kids_back')}</a>
	{#if trip}
		<header>
			{#if trip.cover_asset}<img class="cover" src={thumbUrl(trip.cover_asset, 'preview')} alt="" />{/if}
			<h1>{tripTitle(trip, t('trip_untitled'))} {trip.countries.map(flag).join(' ')}</h1>
			<p class="intro">{t('kids_intro', { nights: trip.nights, km: km(trip.distance_km), places: trip.stays.length })}</p>
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
			{@const list = spread(photosAt(st.arrival, st.departure))}
			<section class="chapter card">
				<div class="num">{i + 1}</div>
				<h2>{st.title || st.place_name || t('stay')} {flag(st.country_code)}</h2>
				<p class="muted">{date(st.arrival, { weekday: 'long', day: 'numeric', month: 'long' })} · {plural('nights', st.nights)}</p>
				{#if list.length}
					<div class="photos">
						{#each list as p, j (p.id)}
							<button onclick={() => (viewer = { ids: photosAt(st.arrival, st.departure).map((x) => x.id), index: photosAt(st.arrival, st.departure).indexOf(list[j]) })}>
								<img src={thumbUrl(p.id, 'preview')} alt="" loading="lazy" />
							</button>
						{/each}
					</div>
				{/if}
				<div class="did-you-know">
					<h3>💡 {t('kids_did_you_know')}</h3>
					<PlaceCard lat={st.lat} lon={st.lon} kids />
				</div>
			</section>
		{/each}
		<p class="end">🏁 {t('kids_the_end')}</p>
	{:else}
		<p class="muted">{t('loading')}</p>
	{/if}
</div>

{#if viewer}
	<PhotoViewer ids={viewer.ids} bind:index={viewer.index} onclose={() => (viewer = null)} />
{/if}

<style>
	.story {
		max-width: 820px;
		margin: 0 auto;
		padding: 16px 16px 60px;
		font-size: 17px;
	}
	.cover {
		width: 100%;
		aspect-ratio: 16/9;
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
	.photos {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 8px;
		margin: 12px 0;
	}
	.photos button {
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
	.did-you-know {
		background: var(--surface-2);
		border-radius: 18px;
		padding: 12px 16px;
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
