// Switching between accounts on one device.
//
// In a browser TripAtlas remembers the names of the accounts recently used on this device (no passwords — the
// browser's password manager fills those in). Inside a host app that provides the optional bridge
// `window.TripAtlasApp`, the app keeps passwords in the phone's secure storage behind the fingerprint and signs in on
// the user's behalf by calling `window.tripAtlasSignIn(username, password)`. See docs/architecture.md, "App bridge".
import { goto } from '$app/navigation';
import { api, ApiError } from '$lib/api';
import { setUser } from '$lib/stores/session.svelte';
import { avatarUrl, tinyDataUrl } from '$lib/avatar';
import { clearAccountStorage } from '$lib/deviceCache/client';
import type { User } from '$lib/types';

export interface KnownAccount {
	username: string;
	display_name: string;
	/** the host app holds the password: signing in only needs the fingerprint */
	saved: boolean;
	/** tiny copy of the profile picture (data URL), kept on this device */
	avatar?: string;
}

interface Bridge {
	/** JSON array of {username, display_name} the app holds a password for */
	accounts(): string;
	/** JSON {username, password, display_name}; the app asks the user whether to keep it */
	offerSave(json: string): void;
	/** the app verifies the user (fingerprint) and then calls window.tripAtlasSignIn */
	signIn(username: string): void;
	forget(username: string): void;
}

type Entry = { username: string; display_name: string; avatar?: string; avatar_version?: number | null; id?: number };

const KEY = 'tripatlas.accounts';
const MAX_RECENT = 6;

const bridge = (): Bridge | undefined => (window as unknown as { TripAtlasApp?: Bridge }).TripAtlasApp;
export const hasApp = () => !!bridge();

function readRecent(): Entry[] {
	try {
		const list = JSON.parse(localStorage.getItem(KEY) ?? '[]');
		return Array.isArray(list) ? list.filter((e) => typeof e?.username === 'string') : [];
	} catch {
		return [];
	}
}

function writeRecent(list: Entry[]) {
	try {
		localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX_RECENT)));
	} catch {
		// private window or storage blocked: switching still works, just without the list
	}
}

function appAccounts(): Entry[] {
	try {
		return JSON.parse(bridge()?.accounts() ?? '[]');
	} catch {
		return [];
	}
}

const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

/** Accounts known on this device, most recently used first; saved ones (app) are marked. */
export function knownAccounts(): KnownAccount[] {
	const saved = appAccounts();
	const out: KnownAccount[] = readRecent().map((e) => ({
		username: e.username,
		display_name: e.display_name,
		avatar: e.avatar,
		saved: saved.some((s) => same(s.username, e.username))
	}));
	for (const s of saved) if (!out.some((e) => same(e.username, s.username))) out.push({ ...s, saved: true });
	return out;
}

export function remember(user: User) {
	const others = readRecent().filter((e) => !same(e.username, user.username));
	const old = readRecent().find((e) => same(e.username, user.username));
	const entry: Entry = { id: user.id, username: user.username, display_name: user.display_name, avatar_version: user.avatar_version };
	if (old?.avatar_version === user.avatar_version) entry.avatar = old.avatar;
	writeRecent([entry, ...others]);
	const url = avatarUrl(user);
	if (url && !entry.avatar)
		tinyDataUrl(url).then((avatar) => {
			if (avatar) writeRecent(readRecent().map((e) => (same(e.username, user.username) ? { ...e, avatar } : e)));
		});
}

export function forget(username: string) {
	const id = readRecent().find((e) => same(e.username, username))?.id;
	if (id) clearAccountStorage(id);
	writeRecent(readRecent().filter((e) => !same(e.username, username)));
	bridge()?.forget(username);
}

export function homeOf(user: User) {
	return user.role === 'child' ? '/kids' : '/';
}

/** Ends the current session and signs in as `username`. Throws ApiError on a wrong password. */
export async function signIn(username: string, password: string): Promise<User> {
	await api.post('/api/auth/logout').catch(() => {});
	const r = await api.post<{ user: User }>('/api/auth/login', { username, password });
	setUser(r.user);
	remember(r.user);
	return r.user;
}

/** After a sign-in with a typed password: let the host app offer to keep it (it asks the user first). */
export function offerSave(password: string, user: User) {
	if (knownAccounts().some((a) => a.saved && same(a.username, user.username))) return;
	bridge()?.offerSave(JSON.stringify({ username: user.username, password, display_name: user.display_name }));
}

// Order matters: first leave the page, then forget the user — otherwise the layout's guard sends us to
// /login?next=<this page>, and the next account (maybe an adult after a child) would land there.
async function toLogin(url: string) {
	await api.post('/api/auth/logout').catch(() => {});
	await goto(url);
	setUser(null);
}

export async function signOut() {
	await toLogin('/login');
}

/** Switch to a known account: with the fingerprint if the app holds its password, else via the sign-in form. */
export async function switchTo(account: KnownAccount | null) {
	const b = bridge();
	if (account?.saved && b) {
		b.signIn(account.username);
		return;
	}
	await toLogin(account ? `/login?user=${encodeURIComponent(account.username)}` : '/login');
}

/** Entry point for the host app once the user has been verified. */
export function installAppSignIn() {
	(window as unknown as { tripAtlasSignIn: (u: string, p: string) => Promise<void> }).tripAtlasSignIn = async (
		username,
		password
	) => {
		try {
			goto(homeOf(await signIn(username, password)));
		} catch (err) {
			const reason = err instanceof ApiError && err.status === 429 ? 'throttled' : 'saved';
			await toLogin(`/login?user=${encodeURIComponent(username)}&failed=${reason}`);
		}
	};
}
