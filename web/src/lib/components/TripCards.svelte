<script lang="ts">
	// Trips as big picture cards — the children's home and the diary.
	import { thumbUrl } from '$lib/api';
	import { date, flag, tripTitle } from '$lib/format';
	import { plural, t } from '$lib/i18n/index.svelte';
	import type { Tracker, TripSummary } from '$lib/types';
	import VehicleIcon from './VehicleIcon.svelte';

	let {
		trips,
		href,
		trackers = []
	}: { trips: TripSummary[]; href: (tr: TripSummary) => string; trackers?: Tracker[] } = $props();

	const trackerOf = (id: number) => trackers.find((tk) => tk.id === id);
</script>

<div class="trips">
	{#each trips as tr (tr.id)}
		{@const tk = trackerOf(tr.tracker_id)}
		<a class="trip card" href={href(tr)}>
			{#if tr.cover_asset}<img src={thumbUrl(tr.cover_asset, 'preview')} alt="" loading="lazy" />{:else}<div class="noimg">🚐</div>{/if}
			<div class="text">
				<strong>{tripTitle(tr, t('trip_untitled'))}</strong>
				<span>{date(tr.start, { month: 'long', year: 'numeric' })} · {plural('nights', tr.nights)}</span>
				<span class="flags">
					{#if trackers.length > 1 && tk}<VehicleIcon color={tk.color} kind={tk.kind} title={tk.name} size={20} />{/if}
					{tr.countries.map(flag).join(' ')}
					{#if tr.ongoing}<span class="live">● {t('trip_ongoing')}</span>{/if}
				</span>
			</div>
		</a>
	{/each}
</div>

<style>
	.trips {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
		gap: 16px;
	}
	.trip {
		overflow: hidden;
		border-radius: 22px;
		text-decoration: none;
		color: var(--text);
		transition: transform 0.15s;
	}
	.trip:hover {
		transform: translateY(-3px) rotate(-0.5deg);
	}
	.trip img,
	.noimg {
		width: 100%;
		aspect-ratio: 4/3;
		object-fit: cover;
		display: block;
	}
	.noimg {
		display: grid;
		place-items: center;
		font-size: 4em;
		background: var(--surface-2);
	}
	.text {
		display: grid;
		gap: 2px;
		padding: 12px 14px 14px;
	}
	.text strong {
		font-size: 1.2em;
	}
	.flags {
		font-size: 1.3em;
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
	}
	.live {
		font-size: 0.65em;
		color: var(--danger, #dc2626);
	}
</style>
