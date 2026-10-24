<script lang="ts">
	// A flight on the "where I've been" globe: route, date, altitude and the photos taken on board.
	import { thumbUrl } from '$lib/api';
	import { dateRange } from '$lib/format';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import type { Flight } from '$lib/types';

	let {
		flight,
		kids = false,
		onphotos,
		onclose
	}: { flight: Flight; kids?: boolean; onphotos: (ids: string[], index: number) => void; onclose: () => void } = $props();

	const route = $derived(
		[flight.origin_name ?? '?', flight.destination_name ?? '?'].join(' → ')
	);
</script>

<div class="sheet card">
	<button class="icon-btn close" onclick={onclose} aria-label={t('close')}>✕</button>
	<p class="kicker">✈ {kids ? t('kids_flight') : t('flight')}</p>
	<h3>{route}</h3>
	<p class="muted">
		{dateRange(flight.start, flight.end)}
		{#if !kids}· {t('flight_altitude', { m: Math.round(flight.max_altitude_m).toLocaleString(i18n.locale) })}{/if}
	</p>
	<button class="link" onclick={() => onphotos(flight.photo_ids, 0)}>{t('flight_photos', { n: flight.photo_ids.length })}</button>
	<div class="strip">
		{#each flight.photo_ids.slice(0, 12) as id, i (id)}
			<button onclick={() => onphotos(flight.photo_ids, i)}><img src={thumbUrl(id)} alt="" loading="lazy" /></button>
		{/each}
	</div>
</div>

<style>
	.sheet {
		padding: 14px 16px;
	}
	.close {
		position: absolute;
		top: 10px;
		right: 10px;
	}
	.kicker {
		margin: 0;
		color: var(--accent);
		font-weight: 700;
	}
	h3 {
		margin: 4px 2.4em 2px 0;
	}
	p {
		margin: 0 0 6px;
	}
	.link {
		padding: 0;
		border: 0;
		background: none;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
	}
	.strip {
		display: flex;
		gap: 6px;
		overflow-x: auto;
		padding-top: 8px;
	}
	.strip button {
		flex: none;
		padding: 0;
		border: 0;
		background: none;
		cursor: zoom-in;
	}
	.strip img {
		width: 72px;
		height: 72px;
		object-fit: cover;
		border-radius: 8px;
		display: block;
	}
</style>
