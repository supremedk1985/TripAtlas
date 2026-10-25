<script lang="ts">
	// The children's home: a globe with every place they have been, and their trips as big picture cards.
	// Read-only by design — the API refuses every change from a child account anyway.
	import { api, pinPhotos, thumbUrl } from '$lib/api';
	import AccountMenu from '$lib/components/AccountMenu.svelte';
	import PhotoViewer from '$lib/components/PhotoViewer.svelte';
	import PlaceCard from '$lib/components/PlaceCard.svelte';
	import TripCards from '$lib/components/TripCards.svelte';
	import VisitedMap from '$lib/components/VisitedMap.svelte';
	import { countryName, flag } from '$lib/format';
	import { t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import FlightSheet from '$lib/components/FlightSheet.svelte';
	import type { Flight, Pin, TripSummary, Visited } from '$lib/types';

	let trips = $state<TripSummary[]>([]);
	let visited = $state<Visited | null>(null);
	let pin = $state<Pin | null>(null);
	let flight = $state<Flight | null>(null);
	let viewer = $state<{ ids: string[]; index: number; overview?: boolean } | null>(null);
	async function openPinPhotos(p: Pin) {
		const v = await pinPhotos(p, p.cover_asset);
		if (v.ids.length) viewer = { ...v, overview: true };
	}

	api.get<TripSummary[]>('/api/trips').then((r) => (trips = r));

</script>

<div class="kids">
	<header class="row">
		<h1>{t('kids_hello', { name: session.user?.display_name ?? '' })}</h1>
		<span class="spacer"></span>
		<AccountMenu variant="button" />
	</header>

	<section class="globe card">
		<VisitedMap
			style="liberty"
			onpin={(p) => ((pin = p), (flight = null))}
			onflight={(f) => ((flight = f), (pin = null))}
			onloaded={(v) => (visited = v)}
		/>
		{#if visited}
			<div class="badge">
				{t('kids_countries', { n: visited.countries.length })}
				<span class="flags">{visited.countries.map((c) => flag(c.country)).join(' ')}</span>
			</div>
		{/if}
		{#if flight}
			<div class="pin flight">
				<FlightSheet {flight} kids onphotos={(ids, index) => (viewer = { ids, index })} onclose={() => (flight = null)} />
			</div>
		{/if}
		{#if pin}
			<div class="pin card">
				<button class="icon-btn close" onclick={() => (pin = null)} aria-label={t('close')}>✕</button>
				{#if pin.cover_asset}
					<button class="cover-btn" onclick={() => openPinPhotos(pin!)} aria-label={t('show_photos')}>
						<img src={thumbUrl(pin.cover_asset, 'preview')} alt="" />
					</button>
				{/if}
				<h2>{flag(pin.country)} {pin.name ?? countryName(pin.country)}</h2>
				<PlaceCard lat={pin.lat} lon={pin.lon} kids />
			</div>
		{/if}
	</section>

	<h2 class="section">{t('kids_our_trips')}</h2>
	{#if trips.length}
		<TripCards {trips} href={(tr) => `/kids/trip/${tr.id}`} />
	{:else}
		<p class="empty-kids">{t('kids_no_trips')}</p>
	{/if}
</div>

{#if viewer}
	<PhotoViewer ids={viewer.ids} bind:index={viewer.index} overview={viewer.overview} onclose={() => (viewer = null)} />
{/if}

<style>
	.kids {
		max-width: 1100px;
		margin: 0 auto;
		padding: 16px 16px 48px;
		font-size: 17px;
	}
	h1 {
		font-size: 1.9em;
		margin: 8px 0;
	}
	.globe {
		position: relative;
		height: clamp(340px, 110vw, 560px); /* not vh: 0 in an Android WebView */
		overflow: hidden;
		border-radius: 24px;
	}
	.badge {
		position: absolute;
		left: 14px;
		top: 14px; /* the map's sources fold out along the bottom edge */
		background: var(--surface);
		border-radius: 18px;
		padding: 8px 14px;
		font-weight: 700;
		box-shadow: var(--shadow);
		/* leaves the zoom buttons in the top right corner free */
		max-width: calc(100% - 72px);
	}
	.badge .flags {
		display: block;
		font-size: 1.3em;
		font-weight: 400;
	}
	.pin {
		position: absolute;
		top: 12px;
		right: 12px;
		width: min(380px, calc(100% - 24px));
		max-height: calc(100% - 24px);
		overflow-y: auto;
		padding: 16px;
		border-radius: 20px;
	}
	.cover-btn {
		display: block;
		width: 100%;
		padding: 0;
		border: 0;
		background: none;
		cursor: zoom-in;
	}
	.pin img {
		width: 100%;
		border-radius: 14px;
		aspect-ratio: 4/3;
		object-fit: cover;
	}
	.pin.flight {
		padding: 0;
		background: none;
	}
	.pin.flight :global(.sheet) {
		position: relative;
		border-radius: 20px;
	}
	.pin h2 {
		margin: 10px 0 6px;
	}
	.pin :global(.place) {
		font-size: 1.05em;
	}
	.close {
		position: absolute;
		top: 10px;
		right: 10px;
		z-index: 1;
	}
	.section {
		margin: 28px 0 12px;
	}
	.empty-kids {
		font-size: 1.1em;
		color: var(--text-2);
	}
</style>
