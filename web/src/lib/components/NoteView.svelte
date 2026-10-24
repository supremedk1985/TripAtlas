<script lang="ts">
	// Displays a stored note. The server already restricts notes to an allow-list; sanitising again here means a
	// compromised or old database can never inject script into the page.
	import DOMPurify from 'dompurify';

	let { html }: { html: string } = $props();
	const clean = $derived(
		DOMPurify.sanitize(html, {
			ALLOWED_TAGS: ['p', 'br', 'b', 'strong', 'i', 'em', 'u', 's', 'h2', 'h3', 'ul', 'ol', 'li', 'a', 'blockquote'],
			ALLOWED_ATTR: ['href', 'rel']
		})
	);
</script>

<div class="prose note">{@html clean}</div>

<style>
	.note :global(a) {
		word-break: break-word;
	}
</style>
