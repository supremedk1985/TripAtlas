// Shapes of the API responses (see server/tripatlas/api/*). Times are Unix seconds.

export type Role = 'admin' | 'member' | 'child';

export interface User {
	id: number;
	username: string;
	display_name: string;
	role: Role;
	locale: string;
	can_see_live: boolean;
	has_immich_key: boolean;
	tracker_ids: number[];
	avatar_version: number | null;
}

export interface SetupStatus {
	busy: boolean;
	has_admin: boolean;
	setup_complete: boolean;
	name: string;
	default_locale: string;
}

export interface Tracker {
	id: number;
	name: string;
	kind: 'vehicle' | 'person';
	color: string;
	traccar_device_id: number | null;
	photo_priority: number;
	has_avatar: boolean;
	position_count: number | null;
	first: number | null;
	last: number | null;
	latest: { t: number; lat: number; lon: number; speed_kmh: number } | null;
}

export interface TripSummary {
	id: number;
	tracker_id: number;
	day_key: string;
	start: number;
	end: number;
	ongoing: boolean;
	distance_km: number;
	farthest_km: number;
	nights: number;
	destination: [number, number];
	auto_title: string | null;
	title: string;
	has_note: boolean;
	places: string[];
	countries: string[];
	photo_count: number;
	cover_asset: string | null;
}

export interface Stay {
	id: number;
	day_key: string;
	arrival: number;
	departure: number;
	lat: number;
	lon: number;
	nights: number;
	place_name: string | null;
	country_code: string | null;
	photo_count: number;
	cover_asset: string | null;
	title: string;
	note_html: string;
}

export interface TripDetail extends TripSummary {
	note_html: string;
	stays: Stay[];
}

/** [t, lat, lon, speed_kmh, altitude_m] */
export type TrackPoint = [number, number, number, number, number];

export interface Photo {
	id: string;
	t: number;
	lat: number;
	lon: number;
	is_video: boolean;
	is_favorite: boolean;
	city: string | null;
	country: string | null;
	width: number | null;
	height: number | null;
	estimated: boolean;
}

export interface TimelineEntry {
	kind: 'drive' | 'stay' | 'ongoing';
	start: number;
	end: number;
	distance_km: number;
	photo_count: number;
	cover_photo: string | null;
	place: string | null;
	lat: number | null;
	lon: number | null;
	nights: number;
	day_key?: string;
	title?: string;
	note_html?: string;
}

export interface PlaceInfo {
	name: string | null;
	country: string | null;
	country_code: string | null;
	summary: string | null;
	url: string | null;
	title?: string | null;
	thumbnail_url: string | null;
	kids_summary?: string | null;
	sights?: { title: string; url: string; distance_m: number }[];
}

export interface Pin {
	lat: number;
	lon: number;
	name: string | null;
	country: string | null;
	nights: number;
	photos: number;
	first: number | null;
	trip_ids: number[];
	kind: 'stay' | 'photos';
	cover_asset?: string;
}

export interface Flight {
	start: number;
	end: number;
	max_altitude_m: number;
	origin: [number, number] | null;
	destination: [number, number] | null;
	origin_name: string | null;
	destination_name: string | null;
	/** positions of the photos taken on board */
	path: [number, number][];
	photo_ids: string[];
	cover_asset: string;
}

export interface Visited {
	pins: Pin[];
	flights: Flight[];
	countries: { country: string; places: number; photos: number; nights: number }[];
}
