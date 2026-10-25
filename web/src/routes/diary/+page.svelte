<script lang="ts">
	// The diary: every trip as a picture card, by year — the same presentation as the children's view, opened with
	// the notes, all photos and the regular texts about each place (lib/components/TripStory.svelte).
	import { api } from '$lib/api';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import TripCards from '$lib/components/TripCards.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import type { Tracker, TripSummary } from '$lib/types';

	let trips = $state<TripSummary[] | null>(null);
	let trackers = $state<Tracker[]>([]);
	Promise.all([api.get<TripSummary[]>('/api/trips'), api.get<Tracker[]>('/api/trackers')]).then(([tr, tk]) => {
		trips = [...tr].sort((a, b) => b.start - a.start);
		trackers = tk;
	});

	const years = $derived.by(() => {
		const out: { year: number; trips: TripSummary[] }[] = [];
		for (const tr of trips ?? []) {
			const y = new Date(tr.start * 1000).getFullYear();
			if (out.at(-1)?.year !== y) out.push({ year: y, trips: [] });
			out.at(-1)!.trips.push(tr);
		}
		return out;
	});
</script>

<div class="page">
	<AppHeader />
	<div class="diary">
		{#if trips === null}
			<p class="muted">{t('loading')}</p>
		{:else if !trips.length}
			<p class="muted">{t('no_trips_title')}</p>
		{/if}
		{#each years as y (y.year)}
			<h2>{y.year}</h2>
			<TripCards trips={y.trips} {trackers} href={(tr) => `/diary/trip/${tr.id}`} />
		{/each}
	</div>
</div>

<style>
	.page {
		max-width: 1100px;
		margin: 0 auto;
		padding: 12px 16px 48px;
	}
	.diary {
		font-size: 17px;
	}
	h2 {
		margin: 26px 0 12px;
		font-size: 1.5em;
	}
</style>
