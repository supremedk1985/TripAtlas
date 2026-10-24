<script lang="ts">
	// "Where I've been": globe with pins. On wide screens the country list sits left and a selected place right;
	// on phones both live at the bottom — the country list collapsed to one line, a selected place as a sheet that
	// replaces it — so the globe stays visible.
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
	let listOpen = $state(false);
	const totalPlaces = $derived(visited?.pins.length ?? 0);
</script>

<div class="page" class:has-pin={pin !== null}>
	<VisitedMap onpin={(p) => (pin = p)} onloaded={(v) => (visited = v)} />
	<AppHeader floating />

	<div class="stats card" class:open={listOpen}>
		{#if visited}
			<button class="summary" onclick={() => (listOpen = !listOpen)} aria-expanded={listOpen}>
				<span class="numbers">
					<span><strong>{visited.countries.length}</strong> {t('stat_countries')}</span>
					<span><strong>{totalPlaces}</strong> {t('stat_places')}</span>
				</span>
				<span class="toggle" aria-hidden="true">{listOpen ? '▾' : '▴'}</span>
				<span class="flags">{visited.countries.map((c) => flag(c.country)).join(' ')}</span>
			</button>
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
			<div class="head">
				{#if pin.cover_asset}<img class="cover" src={thumbUrl(pin.cover_asset, 'preview')} alt="" />{/if}
				<div>
					<h3>{flag(pin.country)} {pin.name ?? ''}</h3>
					<p class="muted">
						{#if pin.nights}{plural('nights', pin.nights)} · {/if}{plural('photos', pin.photos)}
						{#if pin.first}· {t('first_visit')} {date(pin.first)}{/if}
					</p>
				</div>
			</div>
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
		position: fixed;
		inset: 0;
		overflow: hidden;
	}
	.stats {
		position: absolute;
		left: 12px;
		top: 124px;
		width: min(320px, calc(100% - 24px));
		max-height: calc(100% - 148px);
		overflow-y: auto;
		padding: 12px 16px;
		z-index: 3;
	}
	.summary {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 4px 8px;
		width: 100%;
		padding: 0;
		border: 0;
		background: none;
		text-align: left;
		cursor: default;
	}
	.numbers {
		display: flex;
		gap: 16px;
		color: var(--text-2);
	}
	.numbers strong {
		font-size: 1.6em;
		color: var(--accent);
	}
	.flags {
		grid-column: 1 / -1;
		font-size: 1.15em;
		line-height: 1.3;
	}
	.toggle {
		display: none;
	}
	.countries {
		list-style: none;
		padding: 0;
		margin: 10px 0 0;
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
		z-index: 1;
	}
	.head {
		display: grid;
		gap: 8px;
	}
	.cover {
		width: 100%;
		aspect-ratio: 16/10;
		object-fit: cover;
		border-radius: var(--radius-sm);
	}
	.head h3 {
		margin: 0 2.4em 0.2em 0;
	}
	.head p {
		margin: 0 0 8px;
	}

	/* Phones: everything at the bottom, the globe stays free */
	@media (max-width: 640px) {
		.stats {
			top: auto;
			bottom: 12px;
			max-height: 45%;
		}
		.summary {
			cursor: pointer;
		}
		.toggle {
			display: block;
			color: var(--text-2);
		}
		.flags {
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.stats:not(.open) .countries {
			display: none;
		}
		/* a selected place replaces the country list */
		.has-pin .stats {
			display: none;
		}
		.detail {
			top: auto;
			bottom: 0;
			right: 0;
			width: 100%;
			max-height: 58%;
			border-radius: var(--radius) var(--radius) 0 0;
		}
		.head {
			grid-template-columns: 96px 1fr;
			align-items: center;
		}
		.cover {
			width: 96px;
			height: 96px;
			aspect-ratio: auto;
		}
	}
</style>
