<template>
	<div ref="pageElement" class="lucarne-page">
		<PageHeader :title="title">
			<template v-if="data">
				<template v-if="data.channel.subscribed">
					<NcButton variant="secondary" @click="editing = true">
						<template #icon>
							<CogIcon :size="20" />
						</template>
						{{ t('Settings') }}
					</NcButton>
					<NcButton variant="error" @click="unsubscribe">
						<template #icon>
							<DeleteIcon :size="20" />
						</template>
						{{ t('Unsubscribe') }}
					</NcButton>
				</template>
				<NcButton v-else variant="primary" @click="subscribe">
					<template #icon>
						<PlusIcon :size="20" />
					</template>
					{{ t('Subscribe') }}
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
			<template v-if="data.videos.items.length">
				<VideoGrid :videos="data.videos.items" :page-size="pageSize" :total="data.videos.total" />
				<Pagination :page="page" :total="data.videos.total" :per-page="pageSize" @change="goTo" />
			</template>
			<NcEmptyContent
				v-else
				:name="data.channel.sync_status === 'error' ? t('Synchronization stopped') : t('No videos')"
				:description="emptyDescription">
				<template #icon>
					<VideoOutlineIcon />
				</template>
			</NcEmptyContent>
		</template>
		<PlaybackDialog
			v-if="editing && data"
			:item="data.channel"
			type="channel"
			@saved="reload"
			@close="editing = false" />
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
import VideoGrid from '../components/VideoGrid.vue'
import { useAsync } from '../composables/useAsync.js'
import { usePagedGrid } from '../composables/usePagedGrid.js'
import { confirm } from '../dialogs.js'
import { entityTitle } from '../format.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'

const route = useRoute()
const router = useRouter()
const editing = ref(false)
const pageElement = ref(null)
const { pageSize, page, goTo, settle } = usePagedGrid(pageElement)

const { data, loading, error, reload } = useAsync(async () => {
	if (route.name !== 'channel' || !pageSize.value) {
		return null
	}
	const channel = await request(`api/channels/${route.params.id}`)
	const videos = await request(`api/catalog?channel_id=${channel.id}&page=${page.value}&page_size=${pageSize.value}`)
	settle(videos.total)
	let message = ''
	if (!videos.items.length && channel.sync_status !== 'error') {
		const schedule = await request('api/schedule')
		const delay = Math.max(0, Number(schedule.next_lot_at) - Number(schedule.server_time))
		message = t('Videos will appear after the next batch, in about {minutes} min.', { minutes: Math.max(1, Math.ceil(delay / 60)) })
	}
	return { channel, videos, message }
}, () => [route.name, route.params.id, route.query.page, pageSize.value])

const title = computed(() => (data.value ? entityTitle(data.value.channel, 'channel') : ''))
const emptyDescription = computed(() => (
	data.value.channel.sync_status === 'error'
		? data.value.channel.sync_error || t('The agent will retry this source in a future batch.')
		: data.value.message
))

async function subscribe() {
	const channel = data.value.channel
	const answer = await confirm({
		title: t('Subscribe to {name}?', { name: channel.title }),
		message: t('The subscription will be added to the next batch.'),
		submit: t('Subscribe'),
	})
	if (!answer.confirmed) {
		return
	}
	try {
		await send('POST', 'api/channels', { url: channel.source_url })
		notify(t('Subscription queued'))
		router.push({ name: 'subscriptions' })
	} catch (failure) {
		notifyError(failure)
	}
}

async function unsubscribe() {
	const channel = data.value.channel
	const answer = await confirm({
		title: t('Unsubscribe'),
		message: t('The subscription will be removed.'),
		checkboxLabel: t('Also delete associated videos'),
		submit: t('Delete'),
		danger: true,
	})
	if (!answer.confirmed) {
		return
	}
	try {
		await send('DELETE', `api/channels/${channel.id}`, { delete_videos: answer.checked })
		notify(t('Deletion queued'))
		router.push({ name: 'subscriptions' })
	} catch (failure) {
		notifyError(failure)
	}
}
</script>
