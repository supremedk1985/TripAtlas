// What the photo viewer says about a photo: one quiet line underneath, everything else behind the i button.
import { countryName } from '$lib/format';
import { i18n } from '$lib/i18n/index.svelte';

export interface PhotoInfo {
	id: string;
	is_video: boolean;
	taken_at: string | null; // local wall-clock time of the place, written as if UTC
	time_zone: string | null;
	duration: string | null;
	filename: string | null;
	mime: string | null;
	file_size: number | null;
	width: number | null;
	height: number | null;
	city: string | null;
	state: string | null;
	country: string | null;
	country_code: string | null;
	lat: number | null;
	lon: number | null;
	make: string | null;
	model: string | null;
	lens: string | null;
	f_number: number | null;
	exposure_time: string | null;
	iso: number | null;
	focal_length: number | null;
	description: string | null;
	rating: number | null;
	is_favorite: boolean;
}

/** The camera's own wall-clock time, shown as it was there (not converted to the viewer's zone). */
export function takenAt(info: PhotoInfo, long = false): string | null {
	if (!info.taken_at) return null;
	const d = new Date(info.taken_at);
	if (Number.isNaN(d.getTime())) return null;
	return new Intl.DateTimeFormat(i18n.locale, {
		timeZone: 'UTC',
		weekday: long ? 'long' : 'short',
		day: 'numeric',
		month: long ? 'long' : 'short',
		year: 'numeric',
		hour: '2-digit',
		minute: '2-digit',
		...(long ? { second: '2-digit' } : {})
	}).format(d);
}

export function place(info: PhotoInfo): string | null {
	return [info.city, info.country_code ? countryName(info.country_code) : info.country].filter(Boolean).join(', ') || null;
}

export function camera(info: PhotoInfo): string | null {
	const { make, model } = info;
	if (!make && !model) return null;
	if (make && model && model.toLowerCase().startsWith(make.toLowerCase())) return model;
	return [make, model].filter(Boolean).join(' ');
}

export function exposure(info: PhotoInfo): string | null {
	const parts = [
		info.f_number ? `f/${info.f_number}` : null,
		info.exposure_time ? `${info.exposure_time} s` : null,
		info.iso ? `ISO ${info.iso}` : null,
		info.focal_length ? `${Math.round(info.focal_length * 10) / 10} mm` : null
	].filter(Boolean);
	return parts.length ? parts.join(' · ') : null;
}

export function fileSize(bytes: number | null): string | null {
	if (!bytes) return null;
	const mb = bytes / 1024 / 1024;
	return mb >= 1 ? `${mb.toLocaleString(i18n.locale, { maximumFractionDigits: 1 })} MB` : `${Math.round(bytes / 1024)} KB`;
}

export function duration(value: string | null): string | null {
	// Immich: "0:01:23.456"
	const m = value?.match(/^(\d+):(\d+):(\d+)/);
	if (!m) return null;
	const [h, min, s] = [Number(m[1]), m[2], m[3]];
	return h ? `${h}:${min}:${s}` : `${Number(min)}:${s}`;
}
