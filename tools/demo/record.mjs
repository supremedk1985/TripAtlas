// Records the documentation videos and screenshots against the demo (tools/demo, see docs/demo.md).
//
//   LANG=de BASE=http://127.0.0.1:8099 node record.mjs          (needs playwright-core and a fresh demo instance)
//
// Every video is one Playwright context with recordVideo; a visible cursor and captions are injected into the page.
// Output: out/<lang>/videos/*.webm and out/<lang>/images/*.png (converted and copied into docs/ by record.sh).
import { chromium } from 'playwright-core';
import { mkdirSync, renameSync, readdirSync } from 'node:fs';

const LANG = process.env.LANG_UI ?? 'de';
const BASE = process.env.BASE ?? 'http://127.0.0.1:8099';
const OUT = `out/${LANG}`;
const ONLY = process.env.ONLY?.split(',');
mkdirSync(`${OUT}/videos`, { recursive: true });
mkdirSync(`${OUT}/images`, { recursive: true });

const ADMIN = { name: LANG === 'de' ? 'Anna Beispiel' : 'Anna Smith', user: 'anna', pw: 'demo-passwort' };
const HOUSEHOLD = LANG === 'de' ? 'Familie Beispiel' : 'The Smiths';
const VAN = LANG === 'de' ? 'Wohnmobil' : 'Camper van';
const CHILD = { name: 'Mia', user: 'mia', pw: 'mia-passwort' };

const T = {
	de: {
		videos: ['01-einrichtung', '02-karte-und-reisen', '03-wo-war-ich-schon', '04-familie-und-kinder', '05-import', '06-handy'],
		s1: 'Beim ersten Aufruf startet der Einrichtungsassistent.',
		s2: 'Zuerst das Konto für den Administrator – ihr selbst.',
		s3: 'Traccar liefert die Strecken eurer Fahrzeuge. TripAtlas liest dort nur.',
		s4: 'Immich liefert die Fotos. Auch hier wird nur gelesen.',
		s5: '„Testen & speichern“ prüft die Verbindung sofort.',
		s6: 'Welchen Fahrzeugen wollt ihr folgen? Antippen fügt sie hinzu.',
		s7: 'TripAtlas schlägt das Zuhause vor: dort, wo die Fahrzeuge die meisten Nächte stehen.',
		s8: 'Fertig. TripAtlas holt jetzt den Verlauf und erkennt die Reisen.',
		s9: 'Nach kurzer Zeit sind alle Reisen da – mit Strecken und Fotos.',
		m1: 'Alle Reisen auf einer Karte, die Fotos als kleine Stapel darüber.',
		m2: 'Eine Reise antippen öffnet die Einzelheiten.',
		m3: 'Mit ▶ fährt TripAtlas die Strecke ab – Tag für Tag in eigener Farbe.',
		m4: 'Die beiden Griffe zeigen einen Ausschnitt, zum Beispiel nur zwei Tage.',
		m5: 'Titel und Notiz lassen sich für jede Reise und jede Übernachtung schreiben.',
		m6: 'Die Zeitleiste: Fahrten und Übernachtungen mit ihren Fotos.',
		m7: '„Über diesen Ort“ holt den Wikipedia-Text und Sehenswertes in der Nähe.',
		m8: 'Jedes Foto lässt sich groß ansehen und durchblättern.',
		v1: '„Wo war ich schon“: jeder Ort ein Punkt, die besuchten Länder eingefärbt.',
		v2: 'Ein Punkt verrät Nächte, Fotos und was es über den Ort zu wissen gibt.',
		v3: 'Fotos aus dem Flugzeug gehören zum Flug, nicht zu den Orten darunter.',
		f1: 'Unter Einstellungen → Benutzer bekommt jedes Familienmitglied ein Konto.',
		f2: 'Ein Kinderkonto: nur lesen, nie die Live-Position, eine eigene Ansicht.',
		f3: 'So sieht TripAtlas für Kinder aus.',
		f4: 'Jede Reise als Geschichte – mit „Wusstest du schon?“ aus dem Klexikon.',
		i1: 'Alte Reisen ohne Tracker? Unter Einstellungen → Import.',
		i2: 'GPX-Dateien, Google-Standortverlauf oder GeoJSON – für ein Fahrzeug wählen.',
		i3: 'Die neue Reise erscheint nach wenigen Augenblicken in der Liste.',
		p1: 'Auf dem Handy: oben die Karte, darunter die Reisen.',
		p2: 'Fotos lassen sich mit dem Finger durchblättern.',
		title: 'Bretagne 2025',
		note: 'Zwei Wochen am Meer. Der schönste Platz: '
	},
	en: {
		videos: ['01-setup', '02-map-and-trips', '03-where-ive-been', '04-family-and-kids', '05-import', '06-phone'],
		s1: 'The first time you open TripAtlas, the setup wizard starts.',
		s2: 'First the administrator account – that is you.',
		s3: 'Traccar provides the tracks of your vehicles. TripAtlas only reads.',
		s4: 'Immich provides the photos. Again, read only.',
		s5: '"Test & save" checks the connection right away.',
		s6: 'Which vehicles do you want to follow? Tap to add them.',
		s7: 'TripAtlas suggests your home: where the vehicles spend most nights.',
		s8: 'Done. TripAtlas now fetches the history and recognises the trips.',
		s9: 'A moment later all trips are there – with routes and photos.',
		m1: 'All trips on one map, your photos on top as small stacks.',
		m2: 'Tap a trip to open its details.',
		m3: '▶ replays the route – every day in its own colour.',
		m4: 'The two handles select a part, for example just two days.',
		m5: 'Every trip and every overnight stay can have a title and a note.',
		m6: 'The timeline: drives and overnight stays with their photos.',
		m7: '"About this place" brings the Wikipedia summary and sights nearby.',
		m8: 'Every photo opens large; swipe or use the arrows.',
		v1: '"Where I\'ve been": a pin for every place, visited countries filled in.',
		v2: 'A pin tells the nights, the photos and what to know about the place.',
		v3: 'Photos from the plane window belong to the flight, not to the places below.',
		f1: 'Settings → Users: an account for every family member.',
		f2: 'A child account: read only, never the live position, its own view.',
		f3: 'This is TripAtlas for children.',
		f4: 'Every trip as a story – with "Did you know?" written for children.',
		i1: 'Old trips without a tracker? Settings → Import.',
		i2: 'GPX files, Google location history or GeoJSON – choose the vehicle.',
		i3: 'A moment later the new trip shows up in the list.',
		p1: 'On a phone: the map on top, the trips below.',
		p2: 'Swipe through the photos with your finger.',
		title: 'Brittany 2025',
		note: 'Two weeks by the sea. The best spot: '
	}
}[LANG];

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });

// --- helpers ---------------------------------------------------------------------------------------------------
async function newContext({ phone = false, video = true, login = null } = {}) {
	const size = phone ? { width: 390, height: 844 } : { width: 1280, height: 800 };
	const ctx = await browser.newContext({
		viewport: size,
		deviceScaleFactor: phone ? 2 : 1,
		locale: LANG === 'de' ? 'de-DE' : 'en-GB',
		timezoneId: 'Europe/Berlin',
		hasTouch: phone,
		...(video ? { recordVideo: { dir: `${OUT}/videos/raw`, size } } : {})
	});
	await ctx.addInitScript(() => {
		const add = () => {
			if (document.getElementById('__cursor')) return;
			const c = document.createElement('div');
			c.id = '__cursor';
			c.style.cssText =
				'position:fixed;z-index:2147483647;width:24px;height:24px;border-radius:50%;background:rgba(255,90,40,.5);' +
				'border:2px solid #fff;box-shadow:0 0 8px rgba(0,0,0,.45);pointer-events:none;transform:translate(-50%,-50%);' +
				'left:-60px;top:-60px;transition:transform .12s';
			const cap = document.createElement('div');
			cap.id = '__caption';
			cap.style.cssText =
				'position:fixed;z-index:2147483646;left:50%;bottom:26px;transform:translateX(-50%);max-width:88%;' +
				'padding:12px 20px;border-radius:14px;background:rgba(12,18,28,.84);color:#fff;' +
				'font:600 19px/1.35 system-ui,-apple-system,sans-serif;text-align:center;pointer-events:none;opacity:0;transition:opacity .35s';
			document.body.append(c, cap);
			document.addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
			document.addEventListener('mousedown', () => (c.style.transform = 'translate(-50%,-50%) scale(.65)'), true);
			document.addEventListener('mouseup', () => (c.style.transform = 'translate(-50%,-50%)'), true);
		};
		if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add);
		else add();
	});
	if (login) {
		const r = await ctx.request.post(`${BASE}/api/auth/login`, { data: { username: login.user, password: login.pw } });
		if (!r.ok()) throw new Error('login failed ' + r.status());
	}
	const page = await ctx.newPage();
	page.on('pageerror', (e) => console.log('pageerror', e.message));
	return { ctx, page };
}

async function caption(page, text, hold = 2600) {
	await page.evaluate((t) => {
		const c = document.getElementById('__caption');
		if (!c) return;
		c.textContent = t;
		c.style.opacity = t ? '1' : '0';
	}, text);
	if (hold) await page.waitForTimeout(hold);
}

async function moveTo(page, x, y) {
	await page.mouse.move(x, y, { steps: 22 });
	await page.waitForTimeout(220);
}

async function click(page, locator, after = 700) {
	const loc = locator.first();
	await loc.scrollIntoViewIfNeeded();
	const b = await loc.boundingBox();
	await moveTo(page, b.x + b.width / 2, b.y + b.height / 2);
	await page.mouse.down();
	await page.mouse.up();
	await page.waitForTimeout(after);
}

async function type(page, locator, text) {
	await click(page, locator, 200);
	await page.keyboard.type(text, { delay: 45 });
	await page.waitForTimeout(250);
}

async function shot(page, name) {
	await page.evaluate(() => {
		for (const id of ['__cursor', '__caption']) {
			const e = document.getElementById(id);
			if (e) e.style.visibility = 'hidden';
		}
	});
	await page.screenshot({ path: `${OUT}/images/${name}.png` });
	await page.evaluate(() => {
		for (const id of ['__cursor', '__caption']) {
			const e = document.getElementById(id);
			if (e) e.style.visibility = 'visible';
		}
	});
}

async function finish(ctx, page, name) {
	await caption(page, '', 0);
	await page.waitForTimeout(800);
	const video = page.video();
	await ctx.close();
	if (video) renameSync(await video.path(), `${OUT}/videos/${name}.webm`);
}

const want = (i) => !ONLY || ONLY.includes(String(i));

// --- 1: setup ----------------------------------------------------------------------------------------------------
if (want(1)) {
	const { ctx, page } = await newContext();
	await page.goto(BASE + '/');
	await page.waitForTimeout(1500);
	await caption(page, T.s1);
	await caption(page, T.s2, 0);
	await page.selectOption('select', LANG);
	const f = page.locator('form input');
	await type(page, f.nth(0), ADMIN.name);
	await type(page, f.nth(1), ADMIN.user);
	await type(page, f.nth(2), ADMIN.pw);
	await click(page, page.locator('form button.primary'), 1500);

	await caption(page, T.s3, 0);
	await click(page, page.locator('label.chip').nth(1)); // e-mail & password
	const tc = page.locator('section section').nth(0);
	await type(page, tc.locator('input[type=url]'), 'http://traccar:8082');
	await type(page, tc.locator('input[type=text]'), 'tripatlas@example.org');
	await type(page, tc.locator('input[type=password]'), 'read-only-user');
	await caption(page, T.s5, 0);
	await click(page, tc.locator('button.primary'), 2200);
	await caption(page, T.s4, 0);
	const im = page.locator('section section').nth(1);
	await type(page, im.locator('input[type=url]'), 'http://immich:2283');
	await type(page, im.locator('input[type=password]'), 'demo-api-key-0123456789');
	await click(page, im.locator('button.primary'), 2200);
	await shot(page, 'setup-connections');
	await click(page, page.locator('.nav button.primary'), 2000);

	await caption(page, T.s6, 0);
	for (const chip of await page.locator('button.chip').all()) await click(page, chip, 1200);
	await page.waitForTimeout(800);
	await shot(page, 'setup-trackers');
	await click(page, page.locator('.nav button.primary'), 6000);

	await caption(page, T.s7, 0);
	await page.locator('.callout').waitFor({ timeout: 30000 });
	await page.waitForTimeout(2500);
	await shot(page, 'setup-home');
	const nameField = page.locator('form input[type=text]').first();
	await click(page, nameField, 200);
	await page.keyboard.press('Control+a');
	await page.keyboard.type(HOUSEHOLD, { delay: 45 });
	await page.waitForTimeout(800);
	await click(page, page.locator('form button.primary'), 1500);
	await caption(page, T.s8, 0);
	await click(page, page.locator('.nav button.primary'), 2500);
	await page.waitForTimeout(3000);
	await page.locator('.trip').first().waitFor({ timeout: 240000 });
	await caption(page, T.s9, 4500);
	await finish(ctx, page, T.videos[0]);
}

// --- 2: map and trips -------------------------------------------------------------------------------------------
if (want(2)) {
	const { ctx, page } = await newContext({ login: ADMIN });
	await page.goto(BASE + '/');
	await page.locator('.trip').first().waitFor();
	await page.waitForTimeout(7000);
	await shot(page, 'map');
	await caption(page, T.m1, 3500);
	await page.mouse.move(800, 400, { steps: 20 });
	await page.mouse.wheel(0, -300);
	await page.waitForTimeout(2500);
	await caption(page, T.m2, 0);
	const brittany = page.locator('.trip', { hasText: '2025' }).last();
	await click(page, brittany, 7000);

	await caption(page, T.m5, 0);
	await click(page, page.locator('header button.btn'), 900);
	await type(page, page.locator('.edit input[type=text]'), T.title);
	await click(page, page.locator('.tiptap'), 300);
	await page.keyboard.type(T.note, { delay: 40 });
	await page.keyboard.press('Control+b');
	await page.keyboard.type('Camaret-sur-Mer', { delay: 40 });
	await page.keyboard.press('Control+b');
	await page.waitForTimeout(600);
	await click(page, page.locator('.edit button.primary'), 1800);

	// the whole trip in day colours first, then the two handles, then the replay
	await page.waitForTimeout(1500);
	await shot(page, 'trip');
	await caption(page, T.m4, 0);
	const left = page.locator('.range input').first();
	const lb = await left.boundingBox();
	await moveTo(page, lb.x + 11, lb.y + lb.height / 2);
	await page.mouse.down();
	await page.mouse.move(lb.x + lb.width * 0.3, lb.y + lb.height / 2, { steps: 30 });
	await page.mouse.up();
	const right = page.locator('.range input').nth(1);
	const rb = await right.boundingBox();
	await moveTo(page, rb.x + rb.width - 11, rb.y + rb.height / 2);
	await page.mouse.down();
	await page.mouse.move(rb.x + rb.width * 0.6, rb.y + rb.height / 2, { steps: 30 });
	await page.mouse.up();
	await page.waitForTimeout(3500);
	await caption(page, T.m3, 0);
	await click(page, page.locator('.replay .icon-btn').first(), 12000);
	await click(page, page.locator('.replay .icon-btn').first(), 1500);
	await click(page, page.locator('.replay .btn.small', { hasText: LANG === 'de' ? 'Ganze Reise' : 'Whole trip' }), 3000);

	await caption(page, T.m6, 0);
	await page.locator('aside').evaluate((a) => a.scrollTo({ top: 900, behavior: 'smooth' }));
	await page.waitForTimeout(3000);
	await caption(page, T.m7, 0);
	// the second overnight stay's "About this place" (each stay also has a "Note" button next to it)
	const about = LANG === 'de' ? 'Über diesen Ort' : 'About this place';
	await click(page, page.locator('.timeline li.stay').nth(1).locator('button.btn.small', { hasText: about }), 1000);
	await page.locator('.timeline .place .summary').first().waitFor({ timeout: 30000 }).catch(() => {});
	await page.locator('.timeline .place').first().evaluate((e) => e.scrollIntoView({ block: 'center', behavior: 'smooth' }));
	await page.waitForTimeout(2500);
	await shot(page, 'timeline');
	await page.waitForTimeout(1500);
	await caption(page, T.m8, 0);
	await click(page, page.locator('.timeline .strip button').first(), 2500);
	for (let i = 0; i < 3; i++) {
		await page.keyboard.press('ArrowRight');
		await page.waitForTimeout(1700);
	}
	await page.keyboard.press('Escape');
	await page.waitForTimeout(800);
	await finish(ctx, page, T.videos[1]);
}

// --- 3: where I've been -----------------------------------------------------------------------------------------
let PIN = { x: 0, y: 0 };
if (want(3)) {
	const probe = await newContext({ login: ADMIN, video: false });
	await probe.page.goto(BASE + '/visited');
	await probe.page.waitForTimeout(9000);
	outer: for (let y = 200; y < 660; y += 10) {
		for (let x = 500; x < 1100; x += 10) {
			await probe.page.mouse.click(x, y);
			if (await probe.page.locator('.detail.card').count()) {
				PIN = { x, y };
				break outer;
			}
		}
	}
	await probe.ctx.close();
	console.log('pin at', PIN);
}
if (want(3)) {
	const { ctx, page } = await newContext({ login: ADMIN });
	await page.goto(BASE + '/visited');
	await page.waitForTimeout(9000);
	await shot(page, 'visited');
	await caption(page, T.v1, 3500);
	// Pins are drawn on the canvas, not DOM elements: a hidden run beforehand found where one is (PIN), so the
	// visible cursor can go straight there.
	await caption(page, T.v2, 0);
	await moveTo(page, PIN.x, PIN.y);
	await page.mouse.down();
	await page.mouse.up();
	await page.waitForTimeout(5000);
	await click(page, page.locator('.detail .row .btn.small').first(), 2500);
	await page.keyboard.press('ArrowRight');
	await page.waitForTimeout(1600);
	await page.keyboard.press('Escape');
	await click(page, page.locator('.detail .close'), 1000);
	await caption(page, T.v3, 0);
	await click(page, page.locator('.flight-marker'), 3000);
	await shot(page, 'flight');
	await click(page, page.locator('.flight-detail .strip button').nth(1), 2500);
	await page.keyboard.press('ArrowRight');
	await page.waitForTimeout(1800);
	await page.keyboard.press('Escape');
	await finish(ctx, page, T.videos[2]);
}

// --- 4: family and children -------------------------------------------------------------------------------------
if (want(4)) {
	const { ctx, page } = await newContext({ login: ADMIN });
	await page.goto(BASE + '/settings?tab=users');
	await page.waitForTimeout(1500);
	await caption(page, T.f1, 0);
	const form = page.locator('form.new');
	await type(page, form.locator('input').nth(0), CHILD.name);
	await type(page, form.locator('input').nth(1), CHILD.user);
	await type(page, form.locator('input').nth(2), CHILD.pw);
	await caption(page, T.f2, 0);
	await form.locator('select').first().selectOption('child');
	await page.waitForTimeout(800);
	await click(page, form.locator('label.chip', { hasText: VAN }), 600);
	await click(page, form.locator('button.primary'), 2500);
	await shot(page, 'users');
	await page.waitForTimeout(1000);
	await finish(ctx, page, T.videos[3] + '-a');

	const kid = await newContext({ login: CHILD });
	await kid.page.goto(BASE + '/kids');
	await kid.page.waitForTimeout(9000);
	await shot(kid.page, 'kids');
	await caption(kid.page, T.f3, 3000);
	await kid.page.evaluate(() => window.scrollTo({ top: 600, behavior: 'smooth' }));
	await kid.page.waitForTimeout(2000);
	await caption(kid.page, T.f4, 0);
	await click(kid.page, kid.page.locator('a.trip').last(), 8000);
	await kid.page.evaluate(() => window.scrollTo({ top: 1250, behavior: 'smooth' }));
	await kid.page.waitForTimeout(4000);
	await shot(kid.page, 'kids-story');
	await kid.page.evaluate(() => window.scrollBy({ top: 700, behavior: 'smooth' }));
	await kid.page.waitForTimeout(3500);
	await finish(kid.ctx, kid.page, T.videos[3] + '-b');
}

// --- 5: import --------------------------------------------------------------------------------------------------
if (want(5)) {
	const { ctx, page } = await newContext({ login: ADMIN });
	await page.goto(BASE + '/settings?tab=import');
	await page.waitForTimeout(1500);
	await caption(page, T.i1, 2500);
	await caption(page, T.i2, 0);
	await page.locator('form select').selectOption({ index: 0 });
	await click(page, page.locator('label.picker'), 400);
	await page.locator('input[type=file]').setInputFiles('data/sauerland-weekend.gpx');
	await page.waitForTimeout(1200);
	await click(page, page.locator('form button.primary'), 3000);
	await shot(page, 'import');
	await caption(page, T.i3, 0);
	await page.goto(BASE + '/');
	await page.waitForTimeout(15000);
	await page.reload();
	await page.waitForTimeout(7000);
	// the imported weekend is the oldest trip of 2025 (June, the Brittany trip was in August)
	await click(page, page.locator('.trip', { hasText: '2025' }).last(), 6000);
	await finish(ctx, page, T.videos[4]);
}

// --- 6: phone -----------------------------------------------------------------------------------------------------
if (want(6)) {
	const { ctx, page } = await newContext({ phone: true, login: ADMIN });
	await page.goto(BASE + '/');
	await page.waitForTimeout(8000);
	await caption(page, T.p1, 3000);
	await shot(page, 'phone-map');
	await click(page, page.locator('.trip').nth(1), 7000);
	await page.locator('aside').evaluate((a) => a.scrollTo({ top: 500, behavior: 'smooth' }));
	await page.waitForTimeout(2000);
	await caption(page, T.p2, 0);
	await click(page, page.locator('.replay .strip button').first(), 2500);
	for (let i = 0; i < 3; i++) await click(page, page.locator('.viewer .next'), 1600);
	await shot(page, 'phone-viewer');
	await finish(ctx, page, T.videos[5]);
}

await browser.close();
for (const f of readdirSync(`${OUT}/videos`)) console.log('video', f);
