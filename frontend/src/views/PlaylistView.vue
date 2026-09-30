<template>
	<div class="lucarne-page">
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
					:removable="!imported"
					@remove="removeVideo" />
				<Pagination :page="page" :total="data.videos.total" @change="goTo" />
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
import UrlDialog from '../components/UrlDialog.vue'
import VideoGrid from '../components/VideoGrid.vue'
import { useAsync } from '../composables/useAsync.js'
import { confirm } from '../dialogs.js'
import { entityTitle } from '../format.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'

const route = useRoute()
const router = useRouter()
const editing = ref(false)
const adding = ref(false)
const page = computed(() => Number(route.query.page || 1))

const { data, loading, error, reload } = useAsync(async () => {
	if (route.name !== 'playlist') {
		return null
	}
	const playlist = await request(`api/playlists/${route.params.id}`)
	const videos = await request(`api/catalog?playlist_id=${playlist.id}&page=${page.value}`)
	let message = ''
	if (!videos.items.length && playlist.kind === 'youtube') {
		const schedule = await request('api/schedule')
		const delay = Math.max(0, Number(schedule.next_lot_at) - Number(schedule.server_time))
		message = t('Videos will appear after the next batch, in about {minutes} min.', { minutes: Math.max(1, Math.ceil(delay / 60)) })
	}
	return { playlist, videos, message }
}, () => [route.name, route.params.id, route.query.page])

const title = computed(() => (data.value ? entityTitle(data.value.playlist, 'playlist') : ''))
const imported = computed(() => data.value?.playlist.kind === 'youtube')
const pending = computed(() => data.value?.videos.pending_jobs || [])

function goTo(value) {
	router.push({ query: { ...route.query, page: value } })
}

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
	const answer = await confirm({
		title: t('Remove video'),
		message: t('Remove this video from the playlist?'),
		submit: t('Remove'),
		danger: true,
	})
	if (!answer.confirmed) {
		return
	}
	try {
		await send('DELETE', `api/playlists/${data.value.playlist.id}/videos/${video.id}`)
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
