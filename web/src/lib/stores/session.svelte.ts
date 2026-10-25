// Who is signed in, and what the household is called. Loaded once by the root layout.
import { api } from '$lib/api';
import { setAccount } from '$lib/deviceCache/client';
import { setLocale } from '$lib/i18n/index.svelte';
import type { SetupStatus, User } from '$lib/types';

export const session = $state<{ user: User | null; status: SetupStatus | null; loaded: boolean }>({
	user: null,
	status: null,
	loaded: false
});

export async function loadSession() {
	session.status = await api.get<SetupStatus>('/api/setup/status');
	try {
		session.user = await api.get<User>('/api/auth/me');
	} catch {
		session.user = null;
	}
	setAccount(session.user?.id ?? null);
	// Before the first account exists nobody has chosen a language yet: follow the browser.
	const browser = navigator.language.slice(0, 2);
	setLocale(session.user?.locale ?? (session.status.has_admin ? session.status.default_locale : browser));
	session.loaded = true;
}

export function setUser(user: User | null) {
	session.user = user;
	setAccount(user?.id ?? null);
	if (user) setLocale(user.locale);
}

export const isAdmin = () => session.user?.role === 'admin';
export const isChild = () => session.user?.role === 'child';
export const canEdit = () => !!session.user && session.user.role !== 'child';
