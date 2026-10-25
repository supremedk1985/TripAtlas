// "Where I've been": visited countries filled, every place a pin (larger = more nights/photos).
import maplibregl, { type GeoJSONSource } from 'maplibre-gl';
import { alive } from './alive';
import type { Flight, Pin } from '$lib/types';

export function installPins(map: maplibregl.Map, pins: Pin[], countries: string[], colors: { pin: string; country: string }) {
	if (!alive(map)) return;
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
	} else {
		// drawn again for another year: other countries
		const filter: maplibregl.FilterSpecification = ['in', ['get', 'iso'], ['literal', countries]];
		map.setFilter('countries-visited', filter);
		map.setFilter('countries-outline', filter);
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

/** Great-circle points between two [lat, lon] positions — straight lines would cut through the globe. */
function greatCircle(a: [number, number], b: [number, number], steps = 48): [number, number][] {
	const r = Math.PI / 180;
	const [la1, lo1, la2, lo2] = [a[0] * r, a[1] * r, b[0] * r, b[1] * r];
	const d = 2 * Math.asin(Math.sqrt(Math.sin((la2 - la1) / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin((lo2 - lo1) / 2) ** 2));
	if (d === 0) return [[a[1], a[0]]];
	const out: [number, number][] = [];
	for (let i = 0; i <= steps; i++) {
		const f = i / steps;
		const A = Math.sin((1 - f) * d) / Math.sin(d);
		const B = Math.sin(f * d) / Math.sin(d);
		const x = A * Math.cos(la1) * Math.cos(lo1) + B * Math.cos(la2) * Math.cos(lo2);
		const y = A * Math.cos(la1) * Math.sin(lo1) + B * Math.cos(la2) * Math.sin(lo2);
		const z = A * Math.sin(la1) + B * Math.sin(la2);
		out.push([Math.atan2(y, x) / r, Math.atan2(z, Math.sqrt(x * x + y * y)) / r]);
	}
	return out;
}

/** Each flight as a dashed great-circle arc from departure to arrival, with a ✈ marker in the middle.
 *  Returns the markers so the caller can remove them. */
export function installFlights(map: maplibregl.Map, flights: Flight[], color: string, onclick: (f: Flight) => void) {
	if (!alive(map)) return [];
	const lines = flights.map((f, i) => {
		const a = f.origin ?? f.path[0];
		const b = f.destination ?? f.path[f.path.length - 1];
		return { i, coords: greatCircle(a, b) };
	});
	const data: GeoJSON.FeatureCollection = {
		type: 'FeatureCollection',
		features: lines.map((l) => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: l.coords }, properties: { i: l.i } }))
	};
	const src = map.getSource('flights') as GeoJSONSource | undefined;
	if (src) src.setData(data);
	else {
		map.addSource('flights', { type: 'geojson', data });
		map.addLayer({
			id: 'flights',
			type: 'line',
			source: 'flights',
			layout: { 'line-cap': 'round' },
			paint: { 'line-color': color, 'line-width': 2.5, 'line-dasharray': [2, 2], 'line-opacity': 0.9 }
		});
		map.on('click', 'flights', (e) => {
			const i = e.features?.[0]?.properties?.i;
			if (i !== undefined) onclick(flights[Number(i)]);
		});
	}
	return lines.map((l) => {
		const el = document.createElement('button');
		el.className = 'flight-marker';
		el.type = 'button';
		el.textContent = '✈';
		el.addEventListener('click', (ev) => {
			ev.stopPropagation();
			onclick(flights[l.i]);
		});
		const mid = l.coords[Math.floor(l.coords.length / 2)];
		return new maplibregl.Marker({ element: el }).setLngLat(mid).addTo(map);
	});
}
