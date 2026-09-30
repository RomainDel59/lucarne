<template>
	<div ref="pageElement" class="lucarne-page">
		<PageHeader :title="t('Playlists')">
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
			<EntityGrid v-if="playlists.length" :items="playlists" type="playlist" :page="page" :page-size="pageSize" @change="goTo" />
			<NcEmptyContent v-else :name="t('No playlists')" :description="t('Create a personal playlist or import one from YouTube.')">
				<template #icon>
					<PlaylistPlayIcon />
				</template>
			</NcEmptyContent>
		</template>
		<AddPlaylistDialog v-if="adding" @added="reload" @close="adding = false" />
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import PlaylistPlayIcon from 'vue-material-design-icons/PlaylistPlay.vue'
import PlusIcon from 'vue-material-design-icons/Plus.vue'
import SortAlphabeticalAscendingIcon from 'vue-material-design-icons/SortAlphabeticalAscending.vue'
import SortClockDescendingIcon from 'vue-material-design-icons/SortClockDescending.vue'
import SortIcon from 'vue-material-design-icons/Sort.vue'
import { request } from '../api.js'
import AddPlaylistDialog from '../components/AddPlaylistDialog.vue'
import EntityGrid from '../components/EntityGrid.vue'
import PageHeader from '../components/PageHeader.vue'
import ToolbarMenu from '../components/ToolbarMenu.vue'
import { useAsync } from '../composables/useAsync.js'
import { usePagedGrid } from '../composables/usePagedGrid.js'
import { t } from '../i18n.js'

const route = useRoute()
const router = useRouter()
const adding = ref(false)
const pageElement = ref(null)
// Compact tiles: six rows take about the height of two rows of video tiles.
const { pageSize, page, goTo, settle } = usePagedGrid(pageElement, 6)

const sort = computed({
	get: () => String(route.query.sort || 'alpha'),
	set: (value) => router.replace({ query: { ...route.query, page: undefined, sort: value === 'alpha' ? undefined : value } }),
})
const sortOptions = [
	{ id: 'alpha', label: t('Alphabetical order'), icon: SortAlphabeticalAscendingIcon },
	{ id: 'recent', label: t('Latest video'), icon: SortClockDescendingIcon },
]

const { data, loading, error, reload } = useAsync(
	() => (route.name === 'playlists' ? request('api/playlists') : Promise.resolve(null)),
	() => route.name,
)

const playlists = computed(() => {
	const list = [...(data.value || [])]
	if (sort.value === 'recent') {
		list.sort((a, b) => Number(b.latest_published_at || 0) - Number(a.latest_published_at || 0))
	}
	return list
})
watch(() => [pageSize.value, playlists.value.length], () => settle(playlists.value.length))
</script>

