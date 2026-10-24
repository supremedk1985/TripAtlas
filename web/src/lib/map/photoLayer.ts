// Photos on the map as small stacks of thumbnails, clustered by MapLibre. Every cluster shows one of its photos plus
// the count; a click opens the photos of that stack. Works for tens of thousands of photos: only the stacks currently
// on screen exist as DOM elements (at most MAX_MARKERS).
import maplibregl, { type GeoJSONSource, type MapGeoJSONFeature } from 'maplibre-gl';
import { thumbUrl } from '$lib/api';

const SOURCE = 'photos';
const MAX_MARKERS = 160;

export type PhotoPoint = { id: string; lat: number; lon: number };

export class PhotoLayer {
	private markers = new Map<string, maplibregl.Marker>();
	private photos: PhotoPoint[] = [];
	private visible = true;
	private readonly refresh = () => this.updateMarkers();
	private readonly onSourceData = (e: maplibregl.MapSourceDataEvent) => {
		if (e.sourceId === SOURCE && e.isSourceLoaded) this.updateMarkers();
	};

	constructor(
		private map: maplibregl.Map,
		private onOpen: (ids: string[], index: number, at: { lat: number; lon: number }) => void
	) {
		map.on('moveend', this.refresh);
		map.on('sourcedata', this.onSourceData);
	}

	/** Call from the map's style callback: (re-)creates source and hit-test layers. */
	install() {
		const map = this.map;
		if (map.getSource(SOURCE)) return;
		map.addSource(SOURCE, {
			type: 'geojson',
			data: this.geojson(),
			cluster: true,
			clusterRadius: 48,
			clusterMaxZoom: 17,
			clusterProperties: { first: ['min', ['get', 'i']] }
		});
		// MapLibre only loads a source that some layer uses — this invisible one; the visible part are HTML thumbnails.
		map.addLayer({ id: 'photo-anchor', type: 'circle', source: SOURCE, paint: { 'circle-radius': 0, 'circle-opacity': 0 } });
		this.updateMarkers();
	}

	/** Where a photo was taken, if it is on the map. */
	position(id: string): { lat: number; lon: number } | null {
		const p = this.photos.find((x) => x.id === id);
		return p ? { lat: p.lat, lon: p.lon } : null;
	}

	/** Photos within `km` of a place (for "photos from here" on a note). */
	photosNear(lat: number, lon: number, km = 0.3): string[] {
		const dLat = km / 111;
		const dLon = km / (111 * Math.cos((lat * Math.PI) / 180));
		return this.photos.filter((p) => Math.abs(p.lat - lat) <= dLat && Math.abs(p.lon - lon) <= dLon).map((p) => p.id);
	}

	setPhotos(photos: PhotoPoint[]) {
		this.photos = photos;
		(this.map.getSource(SOURCE) as GeoJSONSource | undefined)?.setData(this.geojson());
		this.clear();
	}

	setVisible(on: boolean) {
		this.visible = on;
		if (!on) this.clear();
		else this.updateMarkers();
	}

	destroy() {
		this.map.off('moveend', this.refresh);
		this.map.off('sourcedata', this.onSourceData);
		this.clear();
	}

	private geojson(): GeoJSON.FeatureCollection {
		return {
			type: 'FeatureCollection',
			features: this.photos.map((p, i) => ({
				type: 'Feature',
				geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
				properties: { i }
			}))
		};
	}

	private clear() {
		for (const m of this.markers.values()) m.remove();
		this.markers.clear();
	}

	private updateMarkers() {
		if (!this.visible || !this.map.getSource(SOURCE)) return;
		// querySourceFeatures returns the clusters of the current zoom level in all loaded tiles; keep those on screen.
		// (queryRenderedFeatures does not report the invisible hit-test circles.)
		const bounds = this.map.getBounds();
		const features = this.map
			.querySourceFeatures(SOURCE)
			.filter((f) => bounds.contains((f.geometry as GeoJSON.Point).coordinates as [number, number]));
		const seen = new Set<string>();
		const wanted: MapGeoJSONFeature[] = [];
		for (const f of features as MapGeoJSONFeature[]) {
			const key = f.properties.cluster_id !== undefined ? `c${f.properties.cluster_id}` : `p${f.properties.i}`;
			if (seen.has(key)) continue;
			seen.add(key);
			wanted.push(f);
			if (wanted.length >= MAX_MARKERS) break;
		}
		const keep = new Set<string>();
		for (const f of wanted) {
			const isCluster = f.properties.cluster_id !== undefined;
			const index = isCluster ? f.properties.first : f.properties.i;
			const photo = this.photos[index];
			if (!photo) continue;
			const count = isCluster ? f.properties.point_count : 1;
			const key = isCluster ? `c${f.properties.cluster_id}` : `p${index}`;
			keep.add(key);
			if (this.markers.has(key)) continue;
			const coords = (f.geometry as GeoJSON.Point).coordinates as [number, number];
			const el = stackElement(photo.id, count);
			el.addEventListener('click', (ev) => {
				ev.stopPropagation();
				this.open(isCluster ? f.properties.cluster_id : null, index);
			});
			this.markers.set(key, new maplibregl.Marker({ element: el }).setLngLat(coords).addTo(this.map));
		}
		for (const [key, m] of this.markers) {
			if (!keep.has(key)) {
				m.remove();
				this.markers.delete(key);
			}
		}
	}

	private async open(clusterId: number | null, index: number) {
		if (clusterId === null) {
			const p = this.photos[index];
			this.onOpen([p.id], 0, { lat: p.lat, lon: p.lon });
			return;
		}
		const src = this.map.getSource(SOURCE) as GeoJSONSource;
		const leaves = await src.getClusterLeaves(clusterId, 2000, 0);
		const pts = leaves.map((l) => this.photos[l.properties!.i as number]);
		const ids = pts.map((p) => p.id);
		// the middle of the stack's photos: where a note made on this stack is pinned
		const at = { lat: pts.reduce((s, p) => s + p.lat, 0) / pts.length, lon: pts.reduce((s, p) => s + p.lon, 0) / pts.length };
		this.onOpen(ids, Math.max(0, ids.indexOf(this.photos[index].id)), at);
	}
}

/** A thumbnail with a slight random tilt from its id, plus "paper" behind it when there are more photos.
 *  The outer element belongs to MapLibre (it positions it with `transform`), so the tilt goes on the inner one. */
function stackElement(id: string, count: number): HTMLElement {
	const root = document.createElement('div');
	root.className = 'photo-marker';
	const el = document.createElement('button');
	el.className = 'photo-stack';
	el.type = 'button';
	el.setAttribute('aria-label', `${count} photo(s)`);
	let h = 0;
	for (const c of id) h = (h * 31 + c.charCodeAt(0)) | 0;
	const tilt = ((h % 13) - 6) * 0.9;
	const size = count > 1 ? Math.min(64, 40 + Math.log2(count) * 4) : 40;
	el.style.cssText = `--tilt:${tilt}deg;--size:${size}px`;
	el.innerHTML =
		(count > 1 ? '<span class="paper p2"></span><span class="paper p1"></span>' : '') +
		`<img alt="" loading="lazy" src="${thumbUrl(id)}">` +
		(count > 1 ? `<span class="count">${count > 999 ? Math.round(count / 1000) + 'k' : count}</span>` : '');
	root.appendChild(el);
	return root;
}
