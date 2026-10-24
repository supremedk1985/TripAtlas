<script lang="ts">
	// "About this place": encyclopedia summary and nearby sights, loaded on demand (the lookup may take a few seconds
	// the first time, it is cached on the server afterwards).
	import { api, query } from '$lib/api';
	import { countryName, flag } from '$lib/format';
	import { t } from '$lib/i18n/index.svelte';
	import type { PlaceInfo } from '$lib/types';

	let { lat, lon, kids = false }: { lat: number; lon: number; kids?: boolean } = $props();

	let place = $state<PlaceInfo | null>(null);
	let loading = $state(true);
	let failed = $state(false);

	$effect(() => {
		loading = true;
		failed = false;
		api
			.get<PlaceInfo | null>(`/api/places?${query({ lat, lon })}`)
			.then((p) => (place = p))
			.catch(() => (failed = true))
			.finally(() => (loading = false));
	});

	// For children the server already answers with the child-friendly text.
	const text = $derived(place?.summary);
	// When the article is about something larger (no article for the village itself), say what it is about
	const about = $derived.by(() => {
		const title = place?.title?.replace(/\s*\(.*\)$/, '');
		return title && place?.name && !title.toLowerCase().includes(place.name.toLowerCase()) ? title : null;
	});
</script>

<div class="place">
	{#if loading}
		<p class="muted">{t('place_loading')}</p>
	{:else if failed || !place}
		<p class="muted">{t('place_unavailable')}</p>
	{:else}
		{#if place.thumbnail_url && !kids}
			<img class="thumb" src={place.thumbnail_url} alt="" loading="lazy" referrerpolicy="no-referrer" />
		{/if}
		<p class="where">
			{flag(place.country_code)}
			<strong>{place.name ?? ''}</strong>
			{#if place.country_code}<span class="muted">· {countryName(place.country_code)}</span>{/if}
		</p>
		{#if text}
			{#if about}<p class="about muted small">{t('place_about', { name: about })}</p>{/if}
			<p class="summary">{text}</p>
			{#if place.url && !kids}
				<a href={place.url} target="_blank" rel="noopener noreferrer">{kids ? t('kids_read_more') : t('place_read_more')}</a>
			{/if}
		{:else}
			<p class="muted">{t('place_no_article')}</p>
		{/if}
		{#if !kids && place.sights?.length}
			<p class="sights-title">{t('place_nearby')}</p>
			<ul class="sights">
				{#each place.sights as s (s.url)}
					<li>
						<a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a>
						<span class="muted">{(s.distance_m / 1000).toFixed(1)} km</span>
					</li>
				{/each}
			</ul>
		{/if}
		<p class="credit muted">{t('place_credit')}</p>
	{/if}
</div>

<style>
	.place {
		font-size: 0.93em;
	}
	.thumb {
		float: right;
		width: 84px;
		height: 84px;
		object-fit: cover;
		border-radius: 8px;
		margin: 0 0 6px 10px;
	}
	.where {
		margin: 0 0 0.4em;
	}
	.about {
		margin: 0 0 2px;
	}
	.summary {
		margin: 0 0 0.4em;
		white-space: pre-line;
		display: -webkit-box;
		-webkit-line-clamp: 8;
		line-clamp: 8;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.sights-title {
		margin: 0.8em 0 0.2em;
		font-weight: 600;
		clear: both;
	}
	.sights {
		margin: 0;
		padding-left: 1.1em;
	}
	.credit {
		font-size: 0.78em;
		margin: 0.6em 0 0;
		clear: both;
	}
</style>
