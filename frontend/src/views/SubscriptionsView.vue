<template>
	<div ref="pageElement" class="lucarne-page">
		<PageHeader :title="t('Subscriptions')">
			<SelectField
				v-model="catalog"
				compact
				:options="catalogOptions"
				:label="t('Catalogue')" />
			<SelectField
				v-model="sort"
				compact
				:options="sortOptions"
				:label="t('Alphabetical order')" />
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
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import PlusIcon from 'vue-material-design-icons/Plus.vue'
import YoutubeSubscriptionIcon from 'vue-material-design-icons/YoutubeSubscription.vue'
import { request, send } from '../api.js'
import EntityGrid from '../components/EntityGrid.vue'
import PageHeader from '../components/PageHeader.vue'
import SelectField from '../components/SelectField.vue'
import UrlDialog from '../components/UrlDialog.vue'
import { useAsync } from '../composables/useAsync.js'
import { usePagedGrid } from '../composables/usePagedGrid.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'
import { state } from '../store.js'

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
	{ id: 'all', label: t('All catalogues') },
	...state.bootstrap.catalogs.map((item) => ({ id: String(item.id), label: item.name })),
	{ id: 'uncategorized', label: t('- Uncatalogued -') },
])
const sortOptions = [
	{ id: 'alpha', label: t('Alphabetical order') },
	{ id: 'recent', label: t('Latest video') },
]

const { data, loading, error, reload } = useAsync(() => {
	if (route.name !== 'subscriptions') {
		return Promise.resolve(null)
	}
	const filter = catalog.value === 'uncategorized' ? '?uncategorized=true' : catalog.value !== 'all' ? `?catalog_id=${catalog.value}` : ''
	return request(`api/channels${filter}`)
}, () => [route.name, route.query.catalog])

const channels = computed(() => {
	const list = [...(data.value || [])]
	if (sort.value === 'recent') {
		list.sort((a, b) => Number(b.latest_published_at || 0) - Number(a.latest_published_at || 0))
	}
	return list
})

watch(() => [pageSize.value, channels.value.length], () => settle(channels.value.length))

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

