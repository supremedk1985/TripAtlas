<script lang="ts">
	// A person's picture, or the first letter of the name on the accent colour.
	let { name, src = null, size = 30 }: { name: string; src?: string | null; size?: number } = $props();
	let failed = $state(false);
</script>

<span class="avatar" style="width:{size}px;height:{size}px;font-size:{Math.round(size * 0.45)}px">
	{#if src && !failed}
		<img {src} alt="" onerror={() => (failed = true)} />
	{:else}
		{name.slice(0, 1).toUpperCase()}
	{/if}
</span>

<style>
	.avatar {
		border-radius: 50%;
		display: inline-grid;
		place-items: center;
		background: var(--accent);
		color: #fff;
		font-weight: 700;
		flex: none;
		overflow: hidden;
	}
	img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
</style>
