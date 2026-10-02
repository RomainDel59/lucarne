<template>
	<div class="lucarne-page-frame">
		<div ref="pageElement" class="lucarne-page">
			<PageHeader :title="t('Subscriptions')">
				<ToolbarMenu v-model="catalog" :options="catalogOptions" :label="t('Catalogue')" :icon="FilterVariantIcon" />
					<ToolbarMenu v-model="sort" :options="sortOptions" :label="t('Sort')" :icon="SortIcon" />
				<NcButton variant="primary" @click="adding = true">
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
				<EntityGrid v-if="channels.length" :items="channels" type="channel" :page="page" :page-size="pageSize" @change="goTo" />
				<NcEmptyContent v-else :name="t('No subscriptions')" :description="t('Add a YouTube channel to follow its videos.')">
					<template #icon>
						<YoutubeSubscriptionIcon />
					</template>
				</NcEmptyContent>
			</template>
			<UrlDialog
				v-if="adding"
				:title="t('Add a subscription')"
				:label="t('YouTube channel URL')"
				:submit-label="t('Add')"
				@submit="addChannel"
				@close="adding = false" />
		</div>
		<RemoveDropZone
			v-if="filteredCatalog"
			:type="CHANNEL_DRAG_TYPE"
			:label="removeLabel"
			@drop="removeChannel" />
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import FilterVariantIcon from 'vue-material-design-icons/FilterVariant.vue'
import FolderMultipleOutlineIcon from 'vue-material-design-icons/FolderMultipleOutline.vue'
import FolderOffOutlineIcon from 'vue-material-design-icons/FolderOffOutline.vue'
import FolderOutlineIcon from 'vue-material-design-icons/FolderOutline.vue'
import PlusIcon from 'vue-material-design-icons/Plus.vue'
import SortAlphabeticalAscendingIcon from 'vue-material-design-icons/SortAlphabeticalAscending.vue'
import SortClockDescendingIcon from 'vue-material-design-icons/SortClockDescending.vue'
import SortIcon from 'vue-material-design-icons/Sort.vue'
import YoutubeSubscriptionIcon from 'vue-material-design-icons/YoutubeSubscription.vue'
import { request, send } from '../api.js'
import EntityGrid from '../components/EntityGrid.vue'
import PageHeader from '../components/PageHeader.vue'
import RemoveDropZone from '../components/RemoveDropZone.vue'
import ToolbarMenu from '../components/ToolbarMenu.vue'
import UrlDialog from '../components/UrlDialog.vue'
import { CHANNEL_DRAG_TYPE } from '../drag.js'
import { useAsync } from '../composables/useAsync.js'
import { usePagedGrid } from '../composables/usePagedGrid.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'
import { catalogMembershipsChanged, state } from '../store.js'

const route = useRoute()
const router = useRouter()
const adding = ref(false)
const pageElement = ref(null)
// Compact tiles: six rows take about the height of two rows of video tiles.
const { pageSize, page, goTo, settle } = usePagedGrid(pageElement, 6)

const catalog = computed({
	get: () => String(route.query.catalog || 'all'),
	set: (value) => router.replace({ query: { ...route.query, page: undefined, catalog: value === 'all' ? undefined : value } }),
})
const sort = computed({
	get: () => String(route.query.sort || 'alpha'),
	set: (value) => router.replace({ query: { ...route.query, page: undefined, sort: value === 'alpha' ? undefined : value } }),
})

const catalogOptions = computed(() => [
	{ id: 'all', label: t('All catalogues'), icon: FolderMultipleOutlineIcon },
	...state.bootstrap.catalogs.map((item) => ({ id: String(item.id), label: item.name, icon: FolderOutlineIcon })),
	{ id: 'uncategorized', label: t('Uncatalogued'), icon: FolderOffOutlineIcon },
])
// The zone to drop a subscription on only exists when the list is filtered on one catalogue.
const filteredCatalog = computed(() => state.bootstrap.catalogs.find((item) => String(item.id) === catalog.value) || null)
const removeLabel = computed(() => t('Remove from "{catalog}"', { catalog: filteredCatalog.value?.name || '' }))
const sortOptions = [
	{ id: 'alpha', label: t('Alphabetical order'), icon: SortAlphabeticalAscendingIcon },
	{ id: 'recent', label: t('Latest video'), icon: SortClockDescendingIcon },
]

const { data, loading, error, reload } = useAsync(() => {
	if (route.name !== 'subscriptions') {
		return Promise.resolve(null)
	}
	const filter = catalog.value === 'uncategorized' ? '?uncategorized=true' : catalog.value !== 'all' ? `?catalog_id=${catalog.value}` : ''
	return request(`api/channels${filter}`)
}, () => [route.name, route.query.catalog, state.catalogRevision])

const channels = computed(() => {
	const list = [...(data.value || [])]
	if (sort.value === 'recent') {
		list.sort((a, b) => Number(b.latest_published_at || 0) - Number(a.latest_published_at || 0))
	}
	return list
})

watch(() => [pageSize.value, channels.value.length], () => settle(channels.value.length))

async function removeChannel(channel) {
	const target = filteredCatalog.value
	try {
		await send('DELETE', `api/catalogs/${target.id}/channels/${channel.id}`)
		catalogMembershipsChanged()
		notify(t('"{channel}" removed from the catalogue "{catalog}"', { channel: channel.title, catalog: target.name }))
	} catch (error) {
		notifyError(error)
	}
}

async function addChannel(url) {
	try {
		await send('POST', 'api/channels', { url })
		notify(t('Subscription queued'))
		reload()
	} catch (failure) {
		notifyError(failure)
	}
}
</script>
