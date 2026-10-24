// Minimal i18n: flat dictionaries per language, `t('key', {var})` with {var} placeholders.
// To add a language: copy en.ts, translate, register it in DICTIONARIES and in server/tripatlas/api/schemas.py LOCALES.
import de from './de';
import en from './en';

export type Dictionary = Record<keyof typeof en, string>;

const DICTIONARIES: Record<string, Dictionary> = { en, de };
export const LANGUAGES = [
	{ code: 'en', name: 'English' },
	{ code: 'de', name: 'Deutsch' }
];

export const i18n = $state({ locale: 'en' });

export function setLocale(code: string) {
	i18n.locale = code in DICTIONARIES ? code : 'en';
	document.documentElement.lang = i18n.locale;
}

export function t(key: keyof typeof en, vars?: Record<string, string | number>): string {
	let s = DICTIONARIES[i18n.locale]?.[key] ?? en[key] ?? key;
	if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
	return s;
}

/** Choose between singular and plural form: plural('nights', 3) → t('nights_other', {n: 3}) */
export function plural(base: 'nights' | 'photos' | 'places' | 'countries' | 'trips' | 'flights', n: number): string {
	// "0 nights" reads oddly for a bike's day ride: a base may define its own word for zero
	const zero = `${base}_zero` as keyof typeof en;
	const key = (n === 0 && zero in en ? zero : n === 1 ? `${base}_one` : `${base}_other`) as keyof typeof en;
	return t(key, { n: n.toLocaleString(i18n.locale) });
}
