<template>
	<div class="lucarne-video-card">
		<component
			:is="pending ? 'div' : RouterLink"
			v-bind="pending ? {} : { to: { name: 'video', params: { id: video.id }, query: playlistId ? { playlistId } : {} } }"
			class="lucarne-video-card__link">
			<div class="lucarne-video-card__media">
				<img v-if="thumbnail" :src="thumbnail" alt="" loading="lazy">
				<VideoOutlineIcon v-else :size="48" />
				<span v-if="video.duration" class="lucarne-video-card__duration">{{ formatDuration(video.duration) }}</span>
				<NcChip
					v-if="unavailable"
					class="lucarne-video-card__unavailable"
					variant="error"
					no-close
					:text="t('Unavailable')" />
				<span v-if="progress > 0" class="lucarne-video-card__progress" :style="{ width: `${progress}%` }" />
			</div>
			<div class="lucarne-video-card__body">
				<span class="lucarne-video-card__title" :title="title">{{ title }}</span>
				<span class="lucarne-video-card__meta">
						<span v-if="channelName" class="lucarne-video-card__channel" :title="channelName">{{ channelName }}</span>
						<span v-if="channelName" aria-hidden="true">·</span>
						<span class="lucarne-video-card__date">{{ date }}</span>
					</span>
			</div>
		</component>
		<NcButton
			v-if="removable"
			class="lucarne-video-card__remove"
			variant="tertiary"
			:aria-label="t('Remove')"
			@click="$emit('remove', video)">
			<template #icon>
				<DeleteIcon :size="20" />
			</template>
		</NcButton>
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcChip from '@nextcloud/vue/components/NcChip'
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import DeleteIcon from 'vue-material-design-icons/Delete.vue'
import VideoOutlineIcon from 'vue-material-design-icons/VideoOutline.vue'
import { apiUrl } from '../api.js'
import { formatDate, formatDuration } from '../format.js'
import { t } from '../i18n.js'

const props = defineProps({
	video: { type: Object, required: true },
	playlistId: { type: Number, default: null },
	removable: { type: Boolean, default: false },
	/** A video that is still waiting for the agent to collect its metadata. */
	pending: { type: Boolean, default: false },
})
defineEmits(['remove'])

const thumbnail = computed(() => (props.video.thumbnail_url ? apiUrl(props.video.thumbnail_url) : ''))
const unavailable = computed(() => props.video.availability && props.video.availability !== 'available')
const title = computed(() => props.video.title || t('Pending video'))
const channelName = computed(() => (props.pending ? '' : props.video.channel_name || t('Standalone video')))
const date = computed(() => formatDate(props.video.published_at || props.video.created_at))
const progress = computed(() => {
	const duration = Number(props.video.history_duration || 0)
	return duration > 0 ? Math.min(100, (Number(props.video.history_position || 0) / duration) * 100) : 0
})
</script>

<style scoped>
.lucarne-video-card {
	position: relative;
	min-width: 0;
	overflow: hidden;
	border-radius: var(--border-radius-container);
	background-color: var(--color-main-background);
	border: 1px solid var(--color-border);
}

.lucarne-video-card:hover,
.lucarne-video-card:focus-within {
	background-color: var(--color-background-hover);
}

.lucarne-video-card__link {
	display: flex;
	flex-direction: column;
	height: 100%;
	color: var(--color-main-text);
	text-decoration: none;
}

.lucarne-video-card__media {
	position: relative;
	display: flex;
	align-items: center;
	justify-content: center;
	aspect-ratio: 16 / 9;
	overflow: hidden;
	color: var(--color-text-maxcontrast);
	background-color: var(--color-background-dark);
}

.lucarne-video-card__media img {
	width: 100%;
	height: 100%;
	object-fit: cover;
}

.lucarne-video-card__duration {
	position: absolute;
	inset-inline-end: calc(var(--default-grid-baseline) * 2);
	inset-block-end: calc(var(--default-grid-baseline) * 2);
	padding: 0 calc(var(--default-grid-baseline) * 1.5);
	border-radius: var(--border-radius-small, 4px);
	/* Overlay on top of a video thumbnail: independent from the theme, like the picture itself. */
	color: #fff;
	background-color: rgba(0, 0, 0, 0.75);
	font-size: var(--font-size-small, 13px);
}

.lucarne-video-card__unavailable {
	position: absolute;
	inset-inline-start: calc(var(--default-grid-baseline) * 2);
	inset-block-start: calc(var(--default-grid-baseline) * 2);
}

.lucarne-video-card__progress {
	position: absolute;
	inset-inline-start: 0;
	inset-block-end: 0;
	height: calc(var(--default-grid-baseline));
	background-color: var(--color-primary-element);
}

.lucarne-video-card__body {
	display: flex;
	flex: 1;
	flex-direction: column;
	gap: var(--default-grid-baseline);
	min-height: calc(var(--default-grid-baseline) * 20);
	padding: calc(var(--default-grid-baseline) * 3);
}

.lucarne-video-card__title {
	display: -webkit-box;
	/* Room for two lines even when the title fits on one, so all tiles have the same height. */
	min-height: calc(2em * var(--default-line-height, 1.5));
	overflow: hidden;
	font-weight: bold;
	-webkit-box-orient: vertical;
	-webkit-line-clamp: 2;
}

.lucarne-video-card__meta {
	display: flex;
	gap: var(--default-grid-baseline);
	margin-block-start: auto;
	white-space: nowrap;
	color: var(--color-text-maxcontrast);
}

.lucarne-video-card__channel {
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
}

.lucarne-video-card__date {
	flex: none;
}

.lucarne-video-card__remove {
	position: absolute;
	inset-inline-end: var(--default-grid-baseline);
	inset-block-end: var(--default-grid-baseline);
}
</style>
