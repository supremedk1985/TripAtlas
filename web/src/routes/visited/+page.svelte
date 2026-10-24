<script lang="ts">
	import { goto } from '$app/navigation';
	import { thumbUrl } from '$lib/api';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import PlaceCard from '$lib/components/PlaceCard.svelte';
	import VisitedMap from '$lib/components/VisitedMap.svelte';
	import { countryName, date, flag } from '$lib/format';
	import { plural, t } from '$lib/i18n/index.svelte';
	import type { Pin, Visited } from '$lib/types';

	let visited = $state<Visited | null>(null);
	let pin = $state<Pin | null>(null);
	const totalPlaces = $derived(visited?.pins.length ?? 0);
</script>

<div class="page">
	<VisitedMap onpin={(p) => (pin = p)} onloaded={(v) => (visited = v)} />
	<AppHeader floating />

	<div class="stats card">
		{#if visited}
			<div class="numbers">
				<div><strong>{visited.countries.length}</strong><span>{t('stat_countries')}</span></div>
				<div><strong>{totalPlaces}</strong><span>{t('stat_places')}</span></div>
			</div>
			<ul class="countries">
				{#each visited.countries as c (c.country)}
					<li title={plural('places', c.places)}>{flag(c.country)} {countryName(c.country)} <span class="muted">{c.places}</span></li>
				{/each}
			</ul>
		{:else}
			<p class="muted">{t('loading')}</p>
		{/if}
	</div>

	{#if pin}
		<div class="detail card">
			<button class="icon-btn close" onclick={() => (pin = null)} aria-label={t('close')}>✕</button>
			{#if pin.cover_asset}<img class="cover" src={thumbUrl(pin.cover_asset, 'preview')} alt="" />{/if}
			<h3>{flag(pin.country)} {pin.name ?? ''}</h3>
			<p class="muted">
				{#if pin.nights}{plural('nights', pin.nights)} · {/if}{plural('photos', pin.photos)}
				{#if pin.first}· {t('first_visit')} {date(pin.first)}{/if}
			</p>
			{#if pin.trip_ids.length}
				<div class="row">
					{#each pin.trip_ids as id (id)}<button class="btn small" onclick={() => goto(`/?trip=${id}`)}>{t('open_trip')}</button>{/each}
				</div>
			{/if}
			<PlaceCard lat={pin.lat} lon={pin.lon} />
		</div>
	{/if}
</div>

<style>
	.page {
		position: relative;
		height: 100vh;
		height: 100dvh;
		overflow: hidden;
	}
	.stats {
		position: absolute;
		left: 12px;
		top: 112px;
		width: min(320px, calc(100% - 24px));
		max-height: calc(100% - 136px);
		overflow-y: auto;
		padding: 14px 16px;
		z-index: 3;
	}
	.numbers {
		display: flex;
		gap: 22px;
	}
	.numbers div {
		display: grid;
	}
	.numbers strong {
		font-size: 2em;
		line-height: 1;
		color: var(--accent);
	}
	.numbers span {
		color: var(--text-2);
		font-size: 0.9em;
	}
	.countries {
		list-style: none;
		padding: 0;
		margin: 12px 0 0;
		display: grid;
		gap: 3px;
		font-size: 0.93em;
	}
	.detail {
		position: absolute;
		right: 12px;
		top: 72px;
		width: min(360px, calc(100% - 24px));
		max-height: calc(100% - 96px);
		overflow-y: auto;
		padding: 14px 16px;
		z-index: 4;
	}
	.close {
		position: absolute;
		top: 10px;
		right: 10px;
	}
	.cover {
		width: 100%;
		aspect-ratio: 16/10;
		object-fit: cover;
		border-radius: var(--radius-sm);
		margin-bottom: 8px;
	}
	@media (max-width: 640px) {
		.stats {
			top: auto;
			bottom: 12px;
			max-height: 34vh;
		}
		.detail {
			top: 64px;
			max-height: 52vh;
		}
	}
</style>
