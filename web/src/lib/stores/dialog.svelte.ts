// In-page replacements for confirm() and prompt(): they look like the rest of TripAtlas and behave the same in a
// browser and in an Android WebView (where native JS dialogs look foreign or are suppressed).
export interface DialogRequest {
	kind: 'confirm' | 'prompt';
	title: string;
	text?: string;
	value?: string;
	inputType?: 'text' | 'password' | 'url';
	confirmLabel?: string;
	danger?: boolean;
	minLength?: number;
	maxLength?: number;
	resolve: (value: string | boolean | null) => void;
}

export const dialog = $state<{ current: DialogRequest | null }>({ current: null });

export function confirmDialog(title: string, opts: { text?: string; confirmLabel?: string; danger?: boolean } = {}) {
	return new Promise<boolean>((resolve) => {
		dialog.current = { kind: 'confirm', title, ...opts, resolve: (v) => resolve(v === true) };
	});
}

export function promptDialog(
	title: string,
	opts: { text?: string; value?: string; inputType?: 'text' | 'password' | 'url'; confirmLabel?: string; minLength?: number; maxLength?: number } = {}
) {
	return new Promise<string | null>((resolve) => {
		dialog.current = { kind: 'prompt', title, ...opts, resolve: (v) => resolve(typeof v === 'string' ? v : null) };
	});
}
