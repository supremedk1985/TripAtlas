<script lang="ts">
	// "Videos may stutter": shown when Immich streams videos at full size (no smaller copies for playback). The
	// details say how an Immich administrator changes that. Asked from the server once per page load.
	import { api } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import { backLayer } from '$lib/back.svelte';

	let { variant = 'viewer' }: { variant?: 'viewer' | 'settings' } = $props();

	let ok = $state<boolean | null>(null);
	let open = $state(false);
	backLayer(() => open, () => (open = false));
	check().then((v) => (ok = v));
</script>

<script lang="ts" module>
	let asked: Promise<boolean | null> | null = null;
	function check() {
		asked ??= api
			.get<{ ok: boolean | null }>('/api/photos/video-check')
			.then((r) => r.ok)
			.catch(() => null);
		return asked;
	}
</script>

{#if ok === false}
	<div class="hint {variant}">
		<span title={t('video_hint')}>⚠ {t('video_hint')}</span>
		<button class="link" onclick={() => (open = true)}>{t('video_hint_details')}</button>
	</div>
	{#if open}
		<div class="help card" role="dialog" aria-label={t('video_help_title')}>
			<button class="close icon-btn" onclick={() => (open = false)} aria-label={t('close')}>×</button>
			<h3>{t('video_help_title')}</h3>
			<p>{t('video_help_text')}</p>
			<ol>
				<li>{t('video_help_step1')}</li>
				<li>{t('video_help_step2')}</li>
				<li>{t('video_help_step3')}</li>
			</ol>
			<p class="muted">{t('video_help_note')}</p>
		</div>
	{/if}
{/if}

<style>
	.hint {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		font-size: 0.85em;
	}
	.hint.viewer {
		position: absolute;
		left: 50%;
		bottom: 44px;
		transform: translateX(-50%);
		max-width: calc(100% - 32px);
		flex-wrap: nowrap;
		white-space: nowrap;
		padding: 5px 12px;
		border-radius: 999px;
		background: rgb(0 0 0 / 55%);
		color: rgb(255 255 255 / 85%);
		z-index: 3;
	}
	.hint.viewer span {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.hint.settings {
		margin: 8px 0;
		color: var(--warn, #b45309);
	}
	.link {
		background: none;
		border: 0;
		padding: 0;
		color: inherit;
		font: inherit;
		text-decoration: underline;
		cursor: pointer;
	}
	.help {
		position: fixed;
		left: 50%;
		top: 50%;
		transform: translate(-50%, -50%);
		width: min(460px, calc(100vw - 32px));
		max-height: calc(100vh - 48px);
		overflow-y: auto;
		padding: 18px 20px;
		z-index: 60;
		color: var(--text);
		box-shadow: 0 12px 40px rgb(0 0 0 / 40%);
	}
	.help h3 {
		margin: 0 28px 8px 0;
	}
	.help ol {
		padding-left: 1.3em;
		display: grid;
		gap: 6px;
	}
	.close {
		position: absolute;
		right: 10px;
		top: 10px;
	}
</style>
