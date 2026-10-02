<template>
	<div class="lucarne-page">
		<PageHeader :title="data ? data.video.title : ''">
			<NcButton variant="tertiary" @click="goBack">
				<template #icon>
					<ArrowLeftIcon :size="20" />
				</template>
				{{ t('Back') }}
			</NcButton>
			<template v-if="data">
				<NcButton variant="secondary" @click="editing = true">
					<template #icon>
						<CogIcon :size="20" />
					</template>
					{{ t('Settings') }}
				</NcButton>
				<NcButton variant="error" @click="deleteVideo">
					<template #icon>
						<DeleteIcon :size="20" />
					</template>
					{{ t('Delete') }}
				</NcButton>
				<YoutubeLink :url="data.video.webpage_url" />
			</template>
		</PageHeader>
		<NcLoadingIcon v-if="loading && !data" :size="44" />
		<NcEmptyContent v-else-if="error" :name="t('Something went wrong')" :description="error.message">
			<template #icon>
				<AlertCircleIcon />
			</template>
		</NcEmptyContent>
		<template v-else-if="data">
			<div class="lucarne-player-shell" :class="{ 'lucarne-player-shell--audio': phase === 'playing' && mediaMode === 'audio' }">
				<template v-if="phase === 'playing'">
					<audio
						v-if="mediaMode === 'audio'"
						ref="player"
						class="lucarne-player"
						:src="mediaSrc"
						controls
						playsinline
						@loadedmetadata="resume"
						@timeupdate="scheduleProgress"
						@pause="saveProgress(true)"
						@ended="saveProgress(true)" />
					<video
						v-else
						ref="player"
						class="lucarne-player"
						:src="mediaSrc"
						:poster="thumbnail"
						controls
						disablepictureinpicture
						playsinline
						@loadedmetadata="resume"
						@timeupdate="scheduleProgress"
						@pause="saveProgress(true)"
						@ended="saveProgress(true)" />
				</template>
				<template v-else>
					<img v-if="thumbnail" class="lucarne-player-shell__poster" :src="thumbnail" alt="">
					<VideoOutlineIcon v-else :size="72" />
					<div class="lucarne-player-shell__status">
						<NcLoadingIcon v-if="phase === 'working'" :size="32" />
						<p>{{ statusText }}</p>
						<NcNoteCard v-if="errorText" type="error" :text="errorText" />
						<NcButton
							variant="primary"
							:disabled="unavailable || phase === 'working'"
							@click="downloadAndPlay">
							<template #icon>
								<PlayIcon :size="20" />
							</template>
							{{ data.video.media_available ? t('Play') : t('Download and play') }}
						</NcButton>
					</div>
				</template>
			</div>
			<div class="lucarne-video-toolbar">
				<div class="lucarne-video-toolbar__meta">
					<NcButton
						variant="secondary"
						:disabled="!data.video.channel_id"
						:to="data.video.channel_id ? { name: 'channel', params: { id: data.video.channel_id } } : undefined">
						{{ data.video.channel_name || t('Standalone video') }}
					</NcButton>
					<span>{{ `${formatDate(data.video.published_at)}${data.video.duration ? ` · ${formatDuration(data.video.duration)}` : ''}` }}</span>
					<NcCheckboxRadioSwitch type="switch" :model-value="retained" @update:model-value="setRetention">
						{{ t('Keep offline') }}
					</NcCheckboxRadioSwitch>
				</div>
				<SelectField
					v-model="playlistChoice"
					compact
					:options="playlistOptions"
					:selectable="(option) => !option.disabled"
					:label="t('Add to a playlist')"
					@update:model-value="addToPlaylist" />
			</div>
			<div class="lucarne-description">
				{{ data.video.description || t('No description.') }}
			</div>
		</template>
		<PlaybackDialog
			v-if="editing && data"
			:item="data.video"
			type="video"
			@saved="reload"
			@close="editing = false" />
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcCheckboxRadioSwitch from '@nextcloud/vue/components/NcCheckboxRadioSwitch'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import NcNoteCard from '@nextcloud/vue/components/NcNoteCard'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import ArrowLeftIcon from 'vue-material-design-icons/ArrowLeft.vue'
import CogIcon from 'vue-material-design-icons/Cog.vue'
import DeleteIcon from 'vue-material-design-icons/Delete.vue'
import PlayIcon from 'vue-material-design-icons/Play.vue'
import VideoOutlineIcon from 'vue-material-design-icons/VideoOutline.vue'
import { apiUrl, request, send } from '../api.js'
import PageHeader from '../components/PageHeader.vue'
import PlaybackDialog from '../components/PlaybackDialog.vue'
import SelectField from '../components/SelectField.vue'
import YoutubeLink from '../components/YoutubeLink.vue'
import { useAsync } from '../composables/useAsync.js'
import { confirm } from '../dialogs.js'
import { formatDate, formatDuration } from '../format.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'

const route = useRoute()
const router = useRouter()
const editing = ref(false)
const player = ref(null)

const phase = ref('idle')
const statusText = ref('')
const errorText = ref('')
const mediaSrc = ref('')
const mediaMode = ref('video')
const retained = ref(false)
const playlistChoice = ref('none')
const includedPlaylists = ref([])

const playlistId = computed(() => (route.query.playlistId ? Number(route.query.playlistId) : null))

const { data, loading, error, reload } = useAsync(async () => {
	if (route.name !== 'video') {
		return null
	}
	const suffix = playlistId.value ? `?playlist_id=${playlistId.value}` : ''
	const video = await request(`api/videos/${route.params.id}${suffix}`)
	const playlists = (await request('api/playlists')).filter((item) => item.kind === 'personal')
	retained.value = Boolean(video.retained)
	includedPlaylists.value = video.playlist_ids || []
	return { video, playlists }
}, () => [route.name, route.params.id])

const thumbnail = computed(() => (data.value?.video.thumbnail_url ? apiUrl(data.value.video.thumbnail_url) : ''))
const unavailable = computed(() => Boolean(data.value) && data.value.video.availability !== 'available' && !data.value.video.media_available)

watch(data, (value) => {
	if (!value) {
		return
	}
	const video = value.video
	errorText.value = ''
	statusText.value = unavailable.value
		? (video.unavailable_reason || t('This video is no longer available on YouTube.'))
		: video.media_retained
			? t('This media is retained in your library.')
			: video.media_available
				? t('This media is available in the temporary cache.')
				: t('The media will be downloaded completely before playback.')
})

const playlistOptions = computed(() => [
	{ id: 'none', label: t('Add to a playlist') },
	...(data.value?.playlists || []).map((item) => {
		const included = includedPlaylists.value.includes(item.id)
		return { id: String(item.id), label: `${included ? '✓ ' : ''}${item.title}`, disabled: included }
	}),
])

function goBack() {
	if (history.length > 1) {
		history.back()
	} else {
		router.push({ name: 'home' })
	}
}

// Download then play -------------------------------------------------------

let cancelled = false
let lastProgressSave = 0

async function downloadAndPlay() {
	phase.value = 'working'
	errorText.value = ''
	statusText.value = t('Preparing playback…')
	try {
		const suffix = playlistId.value ? `?playlist_id=${playlistId.value}` : ''
		const job = await send('POST', `api/videos/${data.value.video.id}/downloads${suffix}`, {})
		for (let attempt = 0; attempt < 720 && !cancelled; attempt++) {
			const status = await request(`api/downloads/${job.id}`)
			if (status.status === 'ready') {
				mediaMode.value = status.mode === 'audio' ? 'audio' : 'video'
				mediaSrc.value = apiUrl(`media/downloads/${job.id}`)
				lastProgressSave = Number(data.value.video.history_position || 0)
				phase.value = 'playing'
				await nextTick()
				await player.value?.play()
				return
			}
			if (status.status === 'error') {
				throw new Error(status.error || t('Download failed'))
			}
			statusText.value = status.status === 'queued' ? t('Download queued…') : t('Downloading the complete media…')
			await new Promise((resolve) => setTimeout(resolve, 2000))
		}
		if (!cancelled) {
			throw new Error(t('The download took too long.'))
		}
	} catch (failure) {
		phase.value = 'idle'
		errorText.value = failure.message
		notifyError(failure)
	}
}

// Playback position --------------------------------------------------------

function resume() {
	const element = player.value
	if (element && lastProgressSave > 0 && !data.value.video.history_completed && lastProgressSave < element.duration - 5) {
		element.currentTime = lastProgressSave
	}
}

function scheduleProgress() {
	const element = player.value
	if (!element) {
		return
	}
	if (element.currentTime < lastProgressSave || element.currentTime - lastProgressSave >= 10) {
		saveProgress(false)
	}
}

async function saveProgress(force) {
	const element = player.value
	if (!element || !data.value || (!force && element.paused) || !Number.isFinite(element.currentTime)) {
		return
	}
	const position = element.currentTime
	lastProgressSave = position
	try {
		await request(`api/history/${data.value.video.id}`, {
			method: 'PUT',
			keepalive: Boolean(force),
			body: JSON.stringify({ position, duration: Number.isFinite(element.duration) ? element.duration : null }),
		})
	} catch (failure) {
		// The position is saved again on the next update.
	}
}

function saveOnUnload() {
	saveProgress(true)
}

onMounted(() => window.addEventListener('beforeunload', saveOnUnload))
onBeforeUnmount(() => {
	cancelled = true
	window.removeEventListener('beforeunload', saveOnUnload)
	saveProgress(true)
	player.value?.pause()
})

// Actions ------------------------------------------------------------------

async function setRetention(value) {
	const previous = retained.value
	retained.value = value
	try {
		await send('PUT', `api/videos/${data.value.video.id}/retention`, { retained: value })
		notify(value ? t('The next download will be retained.') : t('The retained media was deleted.'))
	} catch (failure) {
		retained.value = previous
		notifyError(failure)
	}
}

async function addToPlaylist(choice) {
	if (choice === 'none') {
		return
	}
	try {
		await send('POST', `api/playlists/${choice}/videos`, { video_id: data.value.video.id })
		includedPlaylists.value = [...includedPlaylists.value, Number(choice)]
		notify(t('Video added to playlist'))
	} catch (failure) {
		notifyError(failure)
	} finally {
		playlistChoice.value = 'none'
	}
}

async function deleteVideo() {
	const answer = await confirm({
		title: t('Delete video'),
		message: t('The video and its local media will be deleted.'),
		submit: t('Delete'),
		danger: true,
	})
	if (!answer.confirmed) {
		return
	}
	try {
		await send('DELETE', `api/videos/${data.value.video.id}`)
		notify(t('Deletion queued'))
		router.push({ name: 'home' })
	} catch (failure) {
		notifyError(failure)
	}
}
</script>

<style scoped>
.lucarne-player-shell {
	/* Leave room below the player for the title, the actions and the start of the description. */
	--lucarne-player-max-height: max(240px, calc(100vh - 300px));
	position: relative;
	display: flex;
	align-items: center;
	justify-content: center;
	/* An explicit width keeps the frame full width when the height is capped. */
	width: 100%;
	aspect-ratio: 16 / 9;
	max-height: var(--lucarne-player-max-height);
	overflow: hidden;
	border-radius: var(--border-radius-container);
	/* The video frame itself stays dark, whatever the theme. */
	background-color: #000;
}

.lucarne-player-shell--audio {
	aspect-ratio: auto;
	min-height: calc(var(--default-grid-baseline) * 20);
}

.lucarne-player-shell__poster {
	position: absolute;
	inset: 0;
	width: 100%;
	height: 100%;
	object-fit: contain;
}

.lucarne-player-shell__status {
	position: relative;
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: calc(var(--default-grid-baseline) * 3);
	max-width: min(520px, 90%);
	padding: calc(var(--default-grid-baseline) * 6);
	border-radius: var(--border-radius-container-large, 16px);
	color: var(--color-main-text);
	background-color: var(--color-main-background-blur);
	-webkit-backdrop-filter: var(--filter-background-blur);
	backdrop-filter: var(--filter-background-blur);
	text-align: center;
}

.lucarne-player {
	width: 100%;
	max-height: var(--lucarne-player-max-height);
}

.lucarne-video-toolbar {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	justify-content: space-between;
	gap: calc(var(--default-grid-baseline) * 4);
	margin-block: calc(var(--default-grid-baseline) * 4);
}

.lucarne-video-toolbar__meta {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: calc(var(--default-grid-baseline) * 3);
	min-width: 0;
}

.lucarne-description {
	padding: calc(var(--default-grid-baseline) * 5);
	border-radius: var(--border-radius-container);
	background-color: var(--color-background-hover);
	white-space: pre-wrap;
}
</style>
