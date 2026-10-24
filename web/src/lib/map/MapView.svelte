<script lang="ts">
	// A MapLibre map filling its container. Parents get the map instance through `onready` and add their own layers.
	// Layers must be (re-)added in `onstyle`, which also fires after a style switch (a new style drops all layers).
	import maplibregl from 'maplibre-gl';
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
</script>

<div class="map" bind:this={container}></div>

<style>
	.map {
		position: absolute;
		inset: 0;
	}
</style>
