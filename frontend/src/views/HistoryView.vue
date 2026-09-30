<template>
	<div ref="pageElement" class="lucarne-page">
		<PageHeader :title="t('History')">
			<NcButton v-if="data && data.items.length" variant="error" @click="clear">
				<template #icon>
					<DeleteIcon :size="20" />
				</template>
				{{ t('Clear') }}
			</NcButton>
		</PageHeader>
		<NcLoadingIcon v-if="loading && !data" :size="44" />
		<NcEmptyContent v-else-if="error" :name="t('Something went wrong')" :description="error.message">
			<template #icon>
				<AlertCircleIcon />
			</template>
		</NcEmptyContent>
		<template v-else-if="data">
			<NcEmptyContent v-if="!data.items.length" :name="t('No history')" :description="t('Videos you watch will appear here.')">
				<template #icon>
					<HistoryIcon />
				</template>
			</NcEmptyContent>
			<template v-else>
				<VideoGrid :videos="data.items" :page-size="pageSize" :total="data.total" />
				<Pagination :page="page" :total="data.total" :per-page="pageSize" @change="goTo" />
			</template>
		</template>
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import DeleteIcon from 'vue-material-design-icons/Delete.vue'
import HistoryIcon from 'vue-material-design-icons/History.vue'
import { request, send } from '../api.js'
import PageHeader from '../components/PageHeader.vue'
import Pagination from '../components/Pagination.vue'
import VideoGrid from '../components/VideoGrid.vue'
import { useAsync } from '../composables/useAsync.js'
import { usePagedGrid } from '../composables/usePagedGrid.js'
import { confirm } from '../dialogs.js'
import { t } from '../i18n.js'
import { notifyError } from '../notify.js'

const route = useRoute()
const pageElement = ref(null)
const { pageSize, page, goTo, settle } = usePagedGrid(pageElement)

const { data, loading, error, reload } = useAsync(
	() => {
		if (route.name !== 'history' || !pageSize.value) {
			return Promise.resolve(null)
		}
		return request(`api/history?page=${page.value}&page_size=${pageSize.value}`).then((result) => {
			settle(result.total)
			return result
		})
	},
	() => [route.name, route.query.page, pageSize.value],
)

async function clear() {
	const answer = await confirm({
		title: t('Clear history'),
		message: t('All playback positions will be removed.'),
		submit: t('Clear'),
		danger: true,
	})
	if (!answer.confirmed) {
		return
	}
	try {
		await send('DELETE', 'api/history')
		reload()
	} catch (failure) {
		notifyError(failure)
	}
}
</script>
