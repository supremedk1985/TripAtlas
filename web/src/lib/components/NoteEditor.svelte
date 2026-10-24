<script lang="ts">
	// Rich-text editor for trip/stay notes (TipTap). Only the formatting the server keeps is offered.
	import { Editor } from '@tiptap/core';
	import StarterKit from '@tiptap/starter-kit';
	import { onDestroy, onMount } from 'svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { promptDialog } from '$lib/stores/dialog.svelte';

	let { html, onchange }: { html: string; onchange: (html: string) => void } = $props();

	let element: HTMLDivElement;
	let editor = $state<Editor>();
	let tick = $state(0); // re-evaluates the toolbar state on every editor transaction

	onMount(() => {
		editor = new Editor({
			element,
			extensions: [
				// StarterKit (v3) already contains Link and Underline
				StarterKit.configure({
					heading: { levels: [2, 3] },
					code: false,
					codeBlock: false,
					horizontalRule: false,
					link: { openOnClick: false, autolink: true, protocols: ['http', 'https', 'mailto'] }
				})
			],
			content: html,
			onTransaction: () => tick++,
			onUpdate: ({ editor }) => onchange(editor.isEmpty ? '' : editor.getHTML())
		});
	});
	onDestroy(() => editor?.destroy());

	async function link() {
		const url = await promptDialog(t('note_link'), {
			text: t('note_link_prompt'),
			inputType: 'url',
			value: editor?.getAttributes('link').href ?? 'https://'
		});
		if (url === null) return;
		if (!url) editor?.chain().focus().unsetLink().run();
		else editor?.chain().focus().setLink({ href: url }).run();
	}

	const tools = [
		{ label: 'B', title: 'note_bold', run: () => editor?.chain().focus().toggleBold().run(), active: 'bold' },
		{ label: 'I', title: 'note_italic', run: () => editor?.chain().focus().toggleItalic().run(), active: 'italic' },
		{ label: 'U', title: 'note_underline', run: () => editor?.chain().focus().toggleUnderline().run(), active: 'underline' },
		{ label: 'H', title: 'note_heading', run: () => editor?.chain().focus().toggleHeading({ level: 3 }).run(), active: 'heading' },
		{ label: '•', title: 'note_list', run: () => editor?.chain().focus().toggleBulletList().run(), active: 'bulletList' },
		{ label: '1.', title: 'note_numbered', run: () => editor?.chain().focus().toggleOrderedList().run(), active: 'orderedList' },
		{ label: '🔗', title: 'note_link', run: link, active: 'link' }
	] as const;
</script>

<div class="editor card">
	<div class="toolbar">
		{#each tools as tool (tool.label)}
			<button
				type="button"
				class:on={tick >= 0 && editor?.isActive(tool.active)}
				title={t(tool.title)}
				onclick={tool.run}>{tool.label}</button
			>
		{/each}
	</div>
	<div class="content prose" bind:this={element}></div>
</div>

<style>
	.editor {
		box-shadow: none;
		overflow: hidden;
	}
	.toolbar {
		display: flex;
		gap: 2px;
		padding: 4px;
		border-bottom: 1px solid var(--border);
		background: var(--surface-2);
	}
	.toolbar button {
		min-width: 2em;
		border: 0;
		background: none;
		border-radius: 6px;
		padding: 0.25em 0.5em;
		cursor: pointer;
		font-weight: 700;
	}
	.toolbar button.on {
		background: var(--accent);
		color: var(--accent-text);
	}
	.content :global(.tiptap) {
		min-height: 120px;
		padding: 0.7em 0.9em;
		outline: none;
	}
</style>
