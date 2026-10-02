<template>
	<div class="lucarne-video-grid">
		<VideoCard v-for="job in pending" :key="`pending-${job.id}`" :video="job" pending />
		<VideoCard
			v-for="video in videos"
			:key="video.id"
			:video="video"
			:playlist-id="playlistId"
			:reorderable="reorderable"
			@reorder="$emit('reorder', $event)" />
		<!-- Invisible tiles keep the grid, and so the pagination buttons, at the same place on the last page. -->
		<VideoCard
			v-for="index in missing"
			:key="`filler-${index}`"
			class="lucarne-video-grid__filler"
			aria-hidden="true"
			:video="{}"
			pending />
	</div>
</template>

<script setup>
import { computed } from 'vue'
import VideoCard from './VideoCard.vue'

const props = defineProps({
	videos: { type: Array, required: true },
	pending: { type: Array, default: () => [] },
	playlistId: { type: Number, default: null },
	reorderable: { type: Boolean, default: false },
	/** Tiles of a full page and total of tiles: on a paginated list, the last page is completed with empty tiles. */
	pageSize: { type: Number, default: 0 },
	total: { type: Number, default: 0 },
})
defineEmits(['reorder'])

const missing = computed(() => (
	props.total > props.pageSize ? Math.max(0, props.pageSize - props.videos.length - props.pending.length) : 0
))
</script>

<style scoped>
.lucarne-video-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
	gap: calc(var(--default-grid-baseline) * 5);
}

.lucarne-video-grid__filler {
	visibility: hidden;
}
</style>
