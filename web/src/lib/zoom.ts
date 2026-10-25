// Zoom into a photo: pinch with two fingers, double tap (or double click) for 2.5× and back, mouse wheel; drag to
// move while zoomed. The element keeps its layout; only a CSS transform changes. Used as `use:zoomable={…}`.
const MAX = 6;
const DOUBLE_TAP_MS = 300;

export function zoomable(node: HTMLElement, opts: { onchange: (scale: number) => void }) {
	let s = 1;
	let tx = 0;
	let ty = 0;
	const pts = new Map<number, { x: number; y: number }>();
	let pinch: { s: number; tx: number; ty: number; dist: number; mx: number; my: number } | null = null;
	let pan: { x: number; y: number; tx: number; ty: number } | null = null;
	let lastTap = { t: 0, x: 0, y: 0 };

	node.style.touchAction = 'none';
	node.style.transition = 'none';

	// The untransformed centre: the rect moves with translate(tx, ty) and scales around its centre.
	function base() {
		const r = node.getBoundingClientRect();
		return { cx: r.left + r.width / 2 - tx, cy: r.top + r.height / 2 - ty };
	}

	function apply() {
		if (s <= 1.01) {
			s = 1;
			tx = 0;
			ty = 0;
		}
		const mx = ((s - 1) * node.offsetWidth) / 2;
		const my = ((s - 1) * node.offsetHeight) / 2;
		tx = Math.max(-mx, Math.min(mx, tx));
		ty = Math.max(-my, Math.min(my, ty));
		node.style.transform = s === 1 ? '' : `translate(${tx}px, ${ty}px) scale(${s})`;
		opts.onchange(s);
	}

	/** Zoom to `s2` keeping the screen point (px, py) where it is (from the state `from`). */
	function zoomAt(px: number, py: number, s2: number, from = { s, tx, ty }) {
		const { cx, cy } = base();
		s2 = Math.max(1, Math.min(MAX, s2));
		tx = px - cx - (s2 / from.s) * (px - cx - from.tx);
		ty = py - cy - (s2 / from.s) * (py - cy - from.ty);
		s = s2;
		apply();
	}

	function startPinch() {
		const [a, b] = [...pts.values()];
		pinch = { s, tx, ty, dist: Math.hypot(a.x - b.x, a.y - b.y) || 1, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
		pan = null;
	}

	function down(e: PointerEvent) {
		node.setPointerCapture(e.pointerId);
		pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
		if (pts.size === 2) return startPinch();
		if (pts.size > 2) return;
		const now = Date.now();
		if (now - lastTap.t < DOUBLE_TAP_MS && Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) < 30) {
			lastTap.t = 0;
			if (s > 1) {
				s = 1;
				apply();
			} else zoomAt(e.clientX, e.clientY, 2.5);
			return;
		}
		lastTap = { t: now, x: e.clientX, y: e.clientY };
		pan = { x: e.clientX, y: e.clientY, tx, ty };
	}

	function move(e: PointerEvent) {
		if (!pts.has(e.pointerId)) return;
		pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
		if (pinch && pts.size === 2) {
			const [a, b] = [...pts.values()];
			const dist = Math.hypot(a.x - b.x, a.y - b.y);
			const mx = (a.x + b.x) / 2;
			const my = (a.y + b.y) / 2;
			// zoom around where the fingers started, then follow the fingers' midpoint
			zoomAt(pinch.mx, pinch.my, (pinch.s * dist) / pinch.dist, pinch);
			tx += mx - pinch.mx;
			ty += my - pinch.my;
			apply();
		} else if (pan && s > 1) {
			tx = pan.tx + e.clientX - pan.x;
			ty = pan.ty + e.clientY - pan.y;
			apply();
		}
	}

	function up(e: PointerEvent) {
		pts.delete(e.pointerId);
		if (pts.size < 2) pinch = null;
		if (pts.size === 1) {
			const [p] = [...pts.values()];
			pan = { x: p.x, y: p.y, tx, ty };
		} else if (pts.size === 0) pan = null;
	}

	function wheel(e: WheelEvent) {
		e.preventDefault();
		zoomAt(e.clientX, e.clientY, s * Math.exp(-e.deltaY * 0.002));
	}

	node.addEventListener('pointerdown', down);
	node.addEventListener('pointermove', move);
	node.addEventListener('pointerup', up);
	node.addEventListener('pointercancel', up);
	node.addEventListener('wheel', wheel, { passive: false });
	return {
		destroy() {
			node.removeEventListener('pointerdown', down);
			node.removeEventListener('pointermove', move);
			node.removeEventListener('pointerup', up);
			node.removeEventListener('pointercancel', up);
			node.removeEventListener('wheel', wheel);
		}
	};
}
