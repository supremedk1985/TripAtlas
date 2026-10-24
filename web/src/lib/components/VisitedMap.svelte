<script lang="ts">
	// Globe with pins for every visited place and the visited countries filled. Used by /visited and the kids' area.
	import maplibregl from 'maplibre-gl';
	import { api } from '$lib/api';
	import MapView from '$lib/map/MapView.svelte';
	import { installFlights, installPins } from '$lib/map/pinsLayer';
	import { boundsOf } from '$lib/map/trackLayer';
	import type { MapStyleId } from '$lib/map/styles';
	import type { Flight, Pin, Visited } from '$lib/types';

	let {
		style,
		onpin,
		onflight,
		onloaded
	}: {
		style?: MapStyleId;
		onpin: (pin: Pin) => void;
		onflight?: (f: Flight) => void;
		onloaded?: (v: Visited) => void;
	} = $props();

	let visited: Visited | null = null;
	let flightMarkers: maplibregl.Marker[] = [];

	function colors() {
		const css = getComputedStyle(document.documentElement);
		return { pin: css.getPropertyValue('--accent').trim() || '#0f766e', country: css.getPropertyValue('--accent-2').trim() || '#14b8a6' };
	}

	function draw(map: maplibregl.Map) {
		if (!visited) return;
		installPins(map, visited.pins, visited.countries.map((c) => c.country), colors());
		flightMarkers.forEach((m) => m.remove());
		flightMarkers = installFlights(map, visited.flights ?? [], colors().pin, (f) => onflight?.(f));
	}

	function onReady(map: maplibregl.Map) {
		api.get<Visited>('/api/visited').then((v) => {
			visited = v;
			onloaded?.(v);
			draw(map);
			// Show the part of the world that has pins, not the whole globe.
			const b = boundsOf(v.pins);
			if (b) map.fitBounds(b, { padding: 60, maxZoom: 5, duration: 0 });
		});
		map.on('click', 'pins', (e) => {
			const i = e.features?.[0]?.properties?.i;
			if (visited && i !== undefined) onpin(visited.pins[Number(i)]);
		});
		map.on('mouseenter', 'pins', () => (map.getCanvas().style.cursor = 'pointer'));
		map.on('mouseleave', 'pins', () => (map.getCanvas().style.cursor = ''));
	}
</script>

<MapView {style} globe zoom={1.6} center={[10, 30]} onready={onReady} onstyle={draw} />
