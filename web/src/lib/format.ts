import { i18n } from './i18n/index.svelte';

export function date(ts: number, opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' }) {
	return new Date(ts * 1000).toLocaleDateString(i18n.locale, opts);
}

export function dateTime(ts: number) {
	return new Date(ts * 1000).toLocaleString(i18n.locale, {
		day: 'numeric',
		month: 'short',
		hour: '2-digit',
		minute: '2-digit'
	});
}

/** "7–17 Aug 2025" style range, shortened when month/year are shared. */
export function dateRange(start: number, end: number) {
	const a = new Date(start * 1000);
	const b = new Date(end * 1000);
	const fmt = new Intl.DateTimeFormat(i18n.locale, { day: 'numeric', month: 'short', year: 'numeric' });
	return typeof fmt.formatRange === 'function' ? fmt.formatRange(a, b) : `${fmt.format(a)} – ${fmt.format(b)}`;
}

export function km(value: number) {
	return `${Math.round(value).toLocaleString(i18n.locale)} km`;
}

export function countryName(code: string | null | undefined): string {
	if (!code) return '';
	try {
		return new Intl.DisplayNames([i18n.locale], { type: 'region' }).of(code) ?? code;
	} catch {
		return code;
	}
}

/** 🇩🇪 from "DE" (regional indicator symbols). */
export function flag(code: string | null | undefined): string {
	if (!code || code.length !== 2) return '';
	return String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1f1a5 + c.charCodeAt(0)));
}

export function tripTitle(trip: { title: string; auto_title: string | null; places: string[] }, fallback: string) {
	return trip.title || trip.auto_title || trip.places[0] || fallback;
}

/** Colours for the days of a trip — distinguishable, readable on light and dark maps. */
export const DAY_COLORS = ['#e4572e', '#17bebb', '#ffc914', '#76b041', '#7e5bef', '#ef476f', '#118ab2', '#f78c6b'];
