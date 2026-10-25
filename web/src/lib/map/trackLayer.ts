// Tracks on the map: an overview of all trips (one line per trip in its tracker's colour) and the selected trip
// (coloured per day, limited to the range of the time slider, stays as numbered markers).
import { vehicleMarker } from './vehicleMarker';
import { alive } from './alive';
import maplibregl, { type GeoJSONSource, type LngLatBoundsLike } from 'maplibre-gl';
import { DAY_COLORS } from '$lib/format';
import type { TrackPoint, Tracker } from '$lib/types';

// A jump of more than this between two points is a gap (tracker off), not a straight line through the landscape.
const GAP_KM = 3;

export interface OverviewTrack {
	tripId: number;
	color: string;
	points: TrackPoint[];
}

const empty: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };

export class TrackLayer {
	private overview = empty;
	private selected = empty;
	private stays = empty;
	private vehicle?: maplibregl.Marker;

	constructor(
		private map: maplibregl.Map,
		private onSelectTrip: (tripId: number) => void
	) {
		map.on('click', 'overview-line', (e) => {
			const id = e.features?.[0]?.properties?.tripId;
			if (id !== undefined) this.onSelectTrip(Number(id));
		});
		map.on('mouseenter', 'overview-line', () => (map.getCanvas().style.cursor = 'pointer'));
		map.on('mouseleave', 'overview-line', () => (map.getCanvas().style.cursor = ''));
	}

	/** (Re-)create sources and layers — call from the map's style callback. */
	install() {
		const map = this.map;
		if (!alive(map) || map.getSource('overview')) return;
		map.addSource('overview', { type: 'geojson', data: this.overview });
		map.addSource('selected', { type: 'geojson', data: this.selected });
		map.addSource('stays', { type: 'geojson', data: this.stays });
		map.addLayer({
			id: 'overview-casing',
			type: 'line',
			source: 'overview',
			layout: { 'line-join': 'round', 'line-cap': 'round' },
			paint: { 'line-color': '#ffffff', 'line-width': 6, 'line-opacity': 0.75 }
		});
		map.addLayer({
			id: 'overview-line',
			type: 'line',
			source: 'overview',
			layout: { 'line-join': 'round', 'line-cap': 'round' },
			paint: { 'line-color': ['get', 'color'], 'line-width': 3.5, 'line-opacity': 0.9 }
		});
		map.addLayer({
			id: 'selected-casing',
			type: 'line',
			source: 'selected',
			layout: { 'line-join': 'round', 'line-cap': 'round' },
			paint: { 'line-color': '#ffffff', 'line-width': 8 }
		});
		map.addLayer({
			id: 'selected-line',
			type: 'line',
			source: 'selected',
			layout: { 'line-join': 'round', 'line-cap': 'round' },
			paint: { 'line-color': ['get', 'color'], 'line-width': 4.5 }
		});
		map.addLayer({
			id: 'stays-circle',
			type: 'circle',
			source: 'stays',
			paint: {
				'circle-radius': 11,
				'circle-color': '#ffffff',
				'circle-stroke-color': '#1c2330',
				'circle-stroke-width': 2
			}
		});
		map.addLayer({
			id: 'stays-label',
			type: 'symbol',
			source: 'stays',
			layout: { 'text-field': ['get', 'n'], 'text-font': ['Noto Sans Regular'], 'text-size': 12, 'text-allow-overlap': true },
			paint: { 'text-color': '#1c2330' }
		});
	}

	setOverview(tracks: OverviewTrack[]) {
		this.overview = {
			type: 'FeatureCollection',
			features: tracks.flatMap((t) =>
				splitAtGaps(t.points).map((coords) => ({
					type: 'Feature' as const,
					geometry: { type: 'LineString' as const, coordinates: coords },
					properties: { tripId: t.tripId, color: t.color }
				}))
			)
		};
		if (alive(this.map)) (this.map.getSource('overview') as GeoJSONSource | undefined)?.setData(this.overview);
	}

	/** Draw the selected trip between `from` and `to` (Unix seconds), one colour per calendar day. */
	setSelected(points: TrackPoint[], from: number, to: number, stays: { lat: number; lon: number }[]) {
		const part = points.filter((p) => p[0] >= from && p[0] <= to);
		const days = new Map<string, TrackPoint[]>();
		for (const p of part) {
			const key = new Date(p[0] * 1000).toDateString();
			if (!days.has(key)) {
				// start each day at the previous day's last point so the line is continuous
				const prev = [...days.values()].at(-1)?.at(-1);
				days.set(key, prev ? [prev] : []);
			}
			days.get(key)!.push(p);
		}
		const features: GeoJSON.Feature[] = [];
		[...days.values()].forEach((pts, i) => {
			for (const coords of splitAtGaps(pts)) {
				features.push({
					type: 'Feature',
					geometry: { type: 'LineString', coordinates: coords },
					properties: { color: DAY_COLORS[i % DAY_COLORS.length] }
				});
			}
		});
		this.selected = { type: 'FeatureCollection', features };
		this.stays = {
			type: 'FeatureCollection',
			features: stays.map((s, i) => ({
				type: 'Feature',
				geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
				properties: { n: String(i + 1) }
			}))
		};
		if (!alive(this.map)) return;
		(this.map.getSource('selected') as GeoJSONSource | undefined)?.setData(this.selected);
		(this.map.getSource('stays') as GeoJSONSource | undefined)?.setData(this.stays);
	}

	clearSelected() {
		this.setSelected([], 0, 0, []);
		this.setVehicle(null);
	}

	/** The marker for "where was the vehicle at this moment" (end of the slider range). */
	setVehicle(pos: [number, number] | null, color = '#e4572e', avatarUrl?: string, kind?: Tracker['kind']) {
		if (!pos) {
			this.vehicle?.remove();
			this.vehicle = undefined;
			return;
		}
		if (!this.vehicle) {
			const el = vehicleMarker({ color, kind, avatarUrl });
			this.vehicle = new maplibregl.Marker({ element: el }).setLngLat([pos[1], pos[0]]).addTo(this.map);
		} else this.vehicle.setLngLat([pos[1], pos[0]]);
	}
}

function distKm(a: TrackPoint, b: TrackPoint) {
	const r = Math.PI / 180;
	const x = (b[2] - a[2]) * r * Math.cos(((a[1] + b[1]) / 2) * r);
	const y = (b[1] - a[1]) * r;
	return Math.sqrt(x * x + y * y) * 6371;
}

function splitAtGaps(points: TrackPoint[]): [number, number][][] {
	const out: [number, number][][] = [];
	let cur: [number, number][] = [];
	points.forEach((p, i) => {
		if (i && distKm(points[i - 1], p) > GAP_KM && cur.length) {
			if (cur.length > 1) out.push(cur);
			cur = [];
		}
		cur.push([p[2], p[1]]);
	});
	if (cur.length > 1) out.push(cur);
	return out;
}

export function boundsOf(points: { lat: number; lon: number }[]): LngLatBoundsLike | null {
	if (!points.length) return null;
	let w = 180, s = 90, e = -180, n = -90;
	for (const p of points) {
		w = Math.min(w, p.lon);
		e = Math.max(e, p.lon);
		s = Math.min(s, p.lat);
		n = Math.max(n, p.lat);
	}
	return [
		[w, s],
		[e, n]
	];
}

/** Interpolated position at time t, or null outside the track or across a gap. */
export function positionAt(points: TrackPoint[], t: number): [number, number] | null {
	if (!points.length || t < points[0][0]) return null;
	let lo = 0, hi = points.length - 1;
	if (t >= points[hi][0]) return [points[hi][1], points[hi][2]];
	while (hi - lo > 1) {
		const m = (lo + hi) >> 1;
		if (points[m][0] <= t) lo = m;
		else hi = m;
	}
	const a = points[lo], b = points[hi];
	if (distKm(a, b) > GAP_KM || b[0] - a[0] > 3600) return [a[1], a[2]];
	const f = (t - a[0]) / (b[0] - a[0] || 1);
	return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}
