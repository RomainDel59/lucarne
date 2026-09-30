<template>
	<div class="lucarne-video-grid">
		<VideoCard v-for="job in pending" :key="`pending-${job.id}`" :video="job" pending />
		<VideoCard
			v-for="video in videos"
			:key="video.id"
			:video="video"
			:playlist-id="playlistId"
			:removable="removable"
			@remove="$emit('remove', $event)" />
	</div>
</template>

<script setup>
import VideoCard from './VideoCard.vue'

defineProps({
	videos: { type: Array, required: true },
	pending: { type: Array, default: () => [] },
	playlistId: { type: Number, default: null },
	removable: { type: Boolean, default: false },
})
defineEmits(['remove'])
</script>

<style scoped>
.lucarne-video-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
	gap: calc(var(--default-grid-baseline) * 5);
}
</style>
