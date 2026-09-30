<template>
	<div ref="pageElement" class="lucarne-page">
		<PageHeader :title="title">
			<NcButton v-if="route.name === 'home'" variant="primary" @click="adding = true">
				<template #icon>
					<PlusIcon :size="20" />
				</template>
				{{ t('Add') }}
			</NcButton>
		</PageHeader>
		<NcLoadingIcon v-if="loading && !data" :size="44" />
		<NcEmptyContent v-else-if="error" :name="t('Something went wrong')" :description="error.message">
			<template #icon>
				<AlertCircleIcon />
			</template>
		</NcEmptyContent>
		<template v-else-if="data">
			<NcEmptyContent v-if="isEmpty" :name="emptyTitle" :description="emptyDescription">
				<template #icon>
					<VideoOutlineIcon />
				</template>
				<template v-if="route.name === 'home' && !searched" #action>
					<NcButton variant="primary" @click="adding = true">
						<template #icon>
							<PlusIcon :size="20" />
						</template>
						{{ t('Add') }}
					</NcButton>
				</template>
			</NcEmptyContent>
			<template v-else>
				<VideoGrid :videos="data.items" :pending="data.pending_jobs || []" :page-size="pageSize" :total="data.total" />
				<Pagination :page="page" :total="data.total" :per-page="pageSize" @change="goTo" />
			</template>
		</template>
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
import { useRoute } from 'vue-router'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import PlusIcon from 'vue-material-design-icons/Plus.vue'
import VideoOutlineIcon from 'vue-material-design-icons/VideoOutline.vue'
import { request, send } from '../api.js'
import PageHeader from '../components/PageHeader.vue'
import Pagination from '../components/Pagination.vue'
import UrlDialog from '../components/UrlDialog.vue'
import VideoGrid from '../components/VideoGrid.vue'
import { useAsync } from '../composables/useAsync.js'
import { usePagedGrid } from '../composables/usePagedGrid.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'
import { state } from '../store.js'

const route = useRoute()
const adding = ref(false)

const pageElement = ref(null)
const { pageSize, page, goTo, settle } = usePagedGrid(pageElement)
const search = computed(() => String(route.query.search || ''))
const searched = computed(() => Boolean(search.value))

const title = computed(() => {
	if (route.name === 'catalog') {
		const catalog = state.bootstrap.catalogs.find((item) => item.id === Number(route.params.id))
		return catalog?.name || t('Catalogue')
	}
	return route.name === 'uncategorized' ? t('Uncatalogued') : t('Home')
})

const { data, loading, error, reload } = useAsync(() => {
	if (!['home', 'catalog', 'uncategorized'].includes(String(route.name)) || !pageSize.value) {
		return Promise.resolve(null)
	}
	const query = new URLSearchParams({ page: page.value, page_size: pageSize.value, search: search.value })
	if (route.name === 'catalog') {
		query.set('catalog_id', route.params.id)
	}
	if (route.name === 'uncategorized') {
		query.set('uncategorized', 'true')
	}
	return request(`api/catalog?${query}`).then((result) => {
		settle(result.total)
		return result
	})
}, () => [route.name, route.params.id, route.query.page, route.query.search, pageSize.value])

const isEmpty = computed(() => !data.value.items.length && !(data.value.pending_jobs || []).length)
const emptyTitle = computed(() => (route.name === 'home' && !searched.value ? t('No videos yet') : t('No videos')))
const emptyDescription = computed(() => {
	if (searched.value) {
		return t('No results for this search.')
	}
	if (route.name === 'uncategorized') {
		return t('All your channels and videos are already in a catalogue.')
	}
	if (route.name === 'catalog') {
		return t('This catalogue does not contain videos from its subscriptions yet.')
	}
	return t('Add a channel, playlist or video to start your library.')
})

async function addVideo(url) {
	try {
		await send('POST', 'api/videos', { url })
		notify(t('Video queued'))
		reload()
	} catch (failure) {
		notifyError(failure)
	}
}
</script>
