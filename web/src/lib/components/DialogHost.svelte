<script lang="ts">
	// Renders the dialog requested through lib/stores/dialog.svelte.ts. Mounted once in the root layout.
	import { t } from '$lib/i18n/index.svelte';
	import { dialog } from '$lib/stores/dialog.svelte';

	let value = $state('');
	let input = $state<HTMLInputElement>();

	$effect(() => {
		if (dialog.current) {
			value = dialog.current.value ?? '';
			queueMicrotask(() => input?.focus());
		}
	});

	function close(result: string | boolean | null) {
		const d = dialog.current;
		dialog.current = null;
		d?.resolve(result);
	}

	const tooShort = $derived(
		!!dialog.current?.minLength && dialog.current.kind === 'prompt' && value.length > 0 && value.length < dialog.current.minLength
	);
</script>

{#if dialog.current}
	{@const d = dialog.current}
	<div class="backdrop" role="presentation" onclick={() => close(d.kind === 'confirm' ? false : null)}>
		<div
			class="dialog card"
			role="dialog"
			aria-modal="true"
			aria-labelledby="dialog-title"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.key === 'Escape' && close(d.kind === 'confirm' ? false : null)}
		>
		<form
			onsubmit={(e) => {
				e.preventDefault();
				if (tooShort) return;
				close(d.kind === 'confirm' ? true : value);
			}}
		>
			<h3 id="dialog-title">{d.title}</h3>
			{#if d.text}<p class="muted">{d.text}</p>{/if}
			{#if d.kind === 'prompt'}
				<input bind:this={input} type={d.inputType ?? 'text'} bind:value autocomplete="off" maxlength={d.maxLength} />
				{#if d.maxLength && value.length > d.maxLength * 0.8}<small class="muted">{value.length} / {d.maxLength}</small>{/if}
				{#if tooShort}<p class="error small">{t('password_too_short')}</p>{/if}
			{/if}
			<div class="row actions">
				<span class="spacer"></span>
				<button type="button" class="btn" onclick={() => close(d.kind === 'confirm' ? false : null)}>{t('cancel')}</button>
				<button type="submit" class="btn primary" class:danger-fill={d.danger}>{d.confirmLabel ?? t('ok')}</button>
			</div>
		</form>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 200;
		background: rgb(0 0 0 / 45%);
		display: grid;
		place-items: center;
		padding: 16px;
	}
	.dialog {
		width: min(420px, 100%);
		padding: 18px 18px 14px;
	}
	h3 {
		margin: 0 0 6px;
	}
	p {
		margin: 0 0 10px;
	}
	.small {
		font-size: 0.86em;
		margin-top: 6px;
	}
	.actions {
		margin-top: 14px;
	}
	.danger-fill {
		background: var(--danger);
		border-color: var(--danger);
		color: #fff;
	}
</style>
