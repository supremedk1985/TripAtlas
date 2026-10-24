<script lang="ts">
	// A MapLibre map filling its container. Parents get the map instance through `onready` and add their own layers.
	// Layers must be (re-)added in `onstyle`, which also fires after a style switch (a new style drops all layers).
	import maplibregl from 'maplibre-gl';
	import { i18n } from '$lib/i18n/index.svelte';
	import { onDestroy, onMount } from 'svelte';
	import { preferredStyle, styleUrl, type MapStyleId } from './styles';

	let {
		style = preferredStyle(),
		globe = false,
		center = [10, 50] as [number, number],
		zoom = 3,
		onready,
		onstyle
	}: {
		style?: MapStyleId;
		globe?: boolean;
		center?: [number, number];
		zoom?: number;
		onready?: (map: maplibregl.Map) => void;
		onstyle?: (map: maplibregl.Map) => void;
	} = $props();

	let container: HTMLDivElement;
	let map: maplibregl.Map | undefined;
	let currentStyle: MapStyleId | undefined;

	onMount(() => {
		map = new maplibregl.Map({
			container,
			style: styleUrl(style),
			center,
			zoom,
			attributionControl: { compact: true },
			fadeDuration: 0
		});
		currentStyle = style;
		map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
		// the handlers keep their own reference: `map` may already be cleared when a late event arrives
		const m = map;
		m.on('style.load', () => {
			if (globe) m.setProjection({ type: 'globe' });
			localiseLabels(m);
			onstyle?.(m);
		});
		m.once('load', () => onready?.(m));
	});

	$effect(() => {
		if (map && style !== currentStyle) {
			currentStyle = style;
			map.setStyle(styleUrl(style));
		}
	});

	onDestroy(() => map?.remove());

	/** Country and place names in the reader's language where the map data has them (otherwise the local name). */
	function localiseLabels(m: maplibregl.Map) {
		const lang = i18n.locale;
		for (const layer of m.getStyle().layers ?? []) {
			if (layer.type !== 'symbol') continue;
			const field = m.getLayoutProperty(layer.id, 'text-field');
			if (!field || !JSON.stringify(field).includes('name')) continue;
			m.setLayoutProperty(layer.id, 'text-field', ['coalesce', ['get', `name:${lang}`], ['get', 'name']]);
		}
	}
</script>

<div class="map" bind:this={container}></div>

<style>
	.map {
		position: absolute;
		inset: 0;
	}
</style>
