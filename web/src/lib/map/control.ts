// What panels may ask the map page to do. Keeps components independent of MapLibre.
import type { Photo, TrackPoint, Tracker } from '$lib/types';

export interface MapControl {
	showTrip(
		points: TrackPoint[],
		stays: { lat: number; lon: number }[],
		color: string,
		avatarUrl?: string,
		kind?: Tracker['kind']
	): void;
	setRange(from: number, to: number, follow: boolean): void;
	clearTrip(): void;
	fit(points: { lat: number; lon: number }[]): void;
	focus(lat: number, lon: number, zoom?: number): void;
	showTripPhotos(photos: Photo[]): void;
	openPhotos(ids: string[], index: number, times?: Record<string, number>, videos?: Set<string>): void;
}
