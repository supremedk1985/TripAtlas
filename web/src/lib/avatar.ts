// Profile pictures: cropped to a square and scaled down in the browser, so the server stores a few KB per person.
import type { User } from '$lib/types';

export const AVATAR_SIZE = 256;

export function avatarUrl(user: Pick<User, 'id' | 'avatar_version'>): string | null {
	return user.avatar_version ? `/api/users/${user.id}/avatar?v=${user.avatar_version}` : null;
}

async function draw(src: CanvasImageSource, w: number, h: number, size: number, type = 'image/jpeg'): Promise<Blob> {
	const side = Math.min(w, h);
	const canvas = document.createElement('canvas');
	canvas.width = canvas.height = size;
	canvas.getContext('2d')!.drawImage(src, (w - side) / 2, (h - side) / 2, side, side, 0, 0, size, size);
	return new Promise((ok, fail) => canvas.toBlob((b) => (b ? ok(b) : fail(new Error('encode'))), type, 0.86));
}

/** The middle square of a picture the user chose, as a small JPEG. */
export async function squareJpeg(file: Blob, size = AVATAR_SIZE): Promise<Blob> {
	const bmp = await createImageBitmap(file, { imageOrientation: 'from-image' });
	try {
		return await draw(bmp, bmp.width, bmp.height, size);
	} finally {
		bmp.close();
	}
}

/** A tiny copy for the account list on this device (shown before signing in, when the server would refuse). */
export async function tinyDataUrl(url: string): Promise<string | null> {
	try {
		const blob = await squareJpeg(await (await fetch(url, { credentials: 'same-origin' })).blob(), 72);
		return await new Promise((ok) => {
			const r = new FileReader();
			r.onload = () => ok(String(r.result));
			r.readAsDataURL(blob);
		});
	} catch {
		return null;
	}
}
