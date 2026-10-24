// Who is signed in, and what the household is called. Loaded once by the root layout.
import { api } from '$lib/api';
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
	setLocale(session.user?.locale ?? session.status.default_locale ?? navigator.language.slice(0, 2));
	session.loaded = true;
}

export function setUser(user: User | null) {
	session.user = user;
	if (user) setLocale(user.locale);
}

export const isAdmin = () => session.user?.role === 'admin';
export const isChild = () => session.user?.role === 'child';
export const canEdit = () => !!session.user && session.user.role !== 'child';
