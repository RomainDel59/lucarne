<template>
	<div class="lucarne-page-frame">
		<div ref="pageElement" class="lucarne-page">
			<PageHeader :title="title">
				<template v-if="data">
					<NcButton variant="secondary" @click="editing = true">
						<template #icon>
							<CogIcon :size="20" />
						</template>
						{{ t('Settings') }}
					</NcButton>
					<NcButton v-if="!imported" variant="secondary" @click="adding = true">
						<template #icon>
							<PlusIcon :size="20" />
						</template>
						{{ t('Add') }}
					</NcButton>
					<NcButton variant="error" @click="deletePlaylist">
						<template #icon>
							<DeleteIcon :size="20" />
						</template>
						{{ t('Delete') }}
					</NcButton>
					<YoutubeLink v-if="imported" :url="data.playlist.source_url" />
				</template>
			</PageHeader>
			<NcLoadingIcon v-if="loading && !data" :size="44" />
			<NcEmptyContent v-else-if="error" :name="t('Something went wrong')" :description="error.message">
				<template #icon>
					<AlertCircleIcon />
				</template>
			</NcEmptyContent>
			<template v-else-if="data">
				<template v-if="data.videos.items.length || pending.length">
					<VideoGrid
						:videos="data.videos.items"
						:pending="pending"
						:playlist-id="data.playlist.id"
						:reorderable="!imported"
						:page-size="pageSize"
						:total="data.videos.total"
						@reorder="moveVideo" />
					<Pagination :page="page" :total="data.videos.total" :per-page="pageSize" @change="goTo" />
				</template>
				<NcEmptyContent v-else :name="t('No videos')" :description="imported ? data.message : t('Add a video to this playlist.')">
					<template #icon>
						<VideoOutlineIcon />
					</template>
				</NcEmptyContent>
			</template>
			<PlaybackDialog
				v-if="editing && data"
				:item="data.playlist"
				type="playlist"
				@saved="reload"
				@close="editing = false" />
			<UrlDialog
				v-if="adding"
				:title="t('Add a video')"
				:label="t('YouTube video URL')"
				:submit-label="t('Add')"
				@submit="addVideo"
				@close="adding = false" />
		</div>
		<RemoveDropZone
			v-if="data && !imported"
			:type="VIDEO_DRAG_TYPE"
			:label="removeLabel"
			@drop="removeVideo" />
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import CogIcon from 'vue-material-design-icons/Cog.vue'
import DeleteIcon from 'vue-material-design-icons/Delete.vue'
import PlusIcon from 'vue-material-design-icons/Plus.vue'
import VideoOutlineIcon from 'vue-material-design-icons/VideoOutline.vue'
import { request, send } from '../api.js'
import PageHeader from '../components/PageHeader.vue'
import Pagination from '../components/Pagination.vue'
import PlaybackDialog from '../components/PlaybackDialog.vue'
import RemoveDropZone from '../components/RemoveDropZone.vue'
import UrlDialog from '../components/UrlDialog.vue'
import VideoGrid from '../components/VideoGrid.vue'
import YoutubeLink from '../components/YoutubeLink.vue'
import { useAsync } from '../composables/useAsync.js'
import { usePagedGrid } from '../composables/usePagedGrid.js'
import { confirm } from '../dialogs.js'
import { VIDEO_DRAG_TYPE } from '../drag.js'
import { entityTitle } from '../format.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'
import { playlistContentChanged, state } from '../store.js'

const route = useRoute()
const router = useRouter()
const editing = ref(false)
const adding = ref(false)
const pageElement = ref(null)
const { pageSize, page, goTo, settle } = usePagedGrid(pageElement)

const { data, loading, error, reload } = useAsync(async () => {
	if (route.name !== 'playlist' || !pageSize.value) {
		return null
	}
	const playlist = await request(`api/playlists/${route.params.id}`)
	const videos = await request(`api/catalog?playlist_id=${playlist.id}&page=${page.value}&page_size=${pageSize.value}`)
	settle(videos.total)
	let message = ''
	if (!videos.items.length && playlist.kind === 'youtube') {
		const schedule = await request('api/schedule')
		const delay = Math.max(0, Number(schedule.next_lot_at) - Number(schedule.server_time))
		message = t('Videos will appear after the next batch, in about {minutes} min.', { minutes: Math.max(1, Math.ceil(delay / 60)) })
	}
	return { playlist, videos, message }
}, () => [route.name, route.params.id, route.query.page, pageSize.value, state.playlistRevision])

const title = computed(() => (data.value ? entityTitle(data.value.playlist, 'playlist') : ''))
const removeLabel = computed(() => t('Remove from "{playlist}"', { playlist: title.value }))
const imported = computed(() => data.value?.playlist.kind === 'youtube')
const pending = computed(() => data.value?.videos.pending_jobs || [])

async function addVideo(url) {
	try {
		await send('POST', `api/playlists/${data.value.playlist.id}/videos`, { url })
		notify(t('Video queued'))
		reload()
	} catch (failure) {
		notifyError(failure)
	}
}

async function removeVideo(video) {
	const playlist = data.value.playlist
	try {
		await send('DELETE', `api/playlists/${playlist.id}/videos/${video.id}`)
		reload()
		notify(t('"{video}" removed from the playlist "{playlist}"', { video: video.title, playlist: title.value }))
	} catch (failure) {
		notifyError(failure)
	}
}

async function moveVideo({ id, target, after }) {
	if (id === target || !data.value.videos.items.some((item) => item.id === id)) {
		return
	}
	try {
		await send('PUT', `api/playlists/${data.value.playlist.id}/videos/${id}/position`, { target_video_id: target, after })
		reload()
	} catch (failure) {
		notifyError(failure)
	}
}

async function deletePlaylist() {
	const answer = await confirm({
		title: t('Delete playlist'),
		message: t('The playlist will be removed.'),
		checkboxLabel: t('Also delete associated videos'),
		submit: t('Delete'),
		danger: true,
	})
	if (!answer.confirmed) {
		return
	}
	try {
		await send('DELETE', `api/playlists/${data.value.playlist.id}`, { delete_videos: answer.checked })
		notify(t('Deletion queued'))
		router.push({ name: 'playlists' })
	} catch (failure) {
		notifyError(failure)
	}
}
</script>
