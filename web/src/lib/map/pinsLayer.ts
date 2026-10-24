// "Where I've been": visited countries filled, every place a pin (larger = more nights/photos).
import type maplibregl from 'maplibre-gl';
import type { GeoJSONSource } from 'maplibre-gl';
import type { Pin } from '$lib/types';

export function installPins(map: maplibregl.Map, pins: Pin[], countries: string[], colors: { pin: string; country: string }) {
	if (!map.getSource('countries')) {
		map.addSource('countries', { type: 'geojson', data: '/countries.geojson' });
		// below the labels of the base map, if it has any
		const firstSymbol = map.getStyle().layers.find((l) => l.type === 'symbol')?.id;
		map.addLayer(
			{
				id: 'countries-visited',
				type: 'fill',
				source: 'countries',
				filter: ['in', ['get', 'iso'], ['literal', countries]],
				paint: { 'fill-color': colors.country, 'fill-opacity': 0.35 }
			},
			firstSymbol
		);
		map.addLayer(
			{
				id: 'countries-outline',
				type: 'line',
				source: 'countries',
				filter: ['in', ['get', 'iso'], ['literal', countries]],
				paint: { 'line-color': colors.country, 'line-width': 1.2 }
			},
			firstSymbol
		);
	}
	const data: GeoJSON.FeatureCollection = {
		type: 'FeatureCollection',
		features: pins.map((p, i) => ({
			type: 'Feature',
			geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
			properties: { i, weight: p.nights * 10 + p.photos, stay: p.kind === 'stay' }
		}))
	};
	const src = map.getSource('pins') as GeoJSONSource | undefined;
	if (src) {
		src.setData(data);
		return;
	}
	map.addSource('pins', { type: 'geojson', data });
	map.addLayer({
		id: 'pins',
		type: 'circle',
		source: 'pins',
		paint: {
			'circle-radius': ['interpolate', ['linear'], ['ln', ['+', 1, ['get', 'weight']]], 0, 5, 8, 13],
			'circle-color': ['case', ['get', 'stay'], colors.pin, '#ffffff'],
			'circle-stroke-color': colors.pin,
			'circle-stroke-width': 2.5,
			'circle-opacity': 0.95
		}
	});
}
