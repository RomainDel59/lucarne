<template>
	<NcContent app-name="lucarne">
		<NcAppNavigation aria-label="Lucarne">
			<template v-if="ready && isVideoList" #search>
				<NcAppNavigationSearch v-model="search" :label="t('Search videos')" />
			</template>
			<template v-if="ready" #list>
				<NcAppNavigationItem
					v-model:open="catalogsOpen"
					:name="t('Home')"
					:to="{ name: 'home' }"
					allow-collapse
					exact>
					<template #icon>
						<HomeIcon :size="20" />
					</template>
					<NcAppNavigationItem
						v-for="catalog in catalogs"
						:key="catalog.id"
						:class="{ 'lucarne-drop-target': dropTarget === `catalog-${catalog.id}` }"
						:name="catalog.name"
						:to="{ name: 'catalog', params: { id: catalog.id } }"
						@dragover="allowDrop($event, CHANNEL_DRAG_TYPE)"
						@dragenter="dropTarget = `catalog-${catalog.id}`"
						@dragleave="leaveDrop(`catalog-${catalog.id}`, $event)"
						@drop.prevent="dropChannel(catalog, $event)">
						<template #icon>
							<FolderOutlineIcon :size="20" />
						</template>
					</NcAppNavigationItem>
					<NcAppNavigationItem :name="t('Uncatalogued')" :to="{ name: 'uncategorized' }">
						<template #icon>
							<FolderOffOutlineIcon :size="20" />
						</template>
					</NcAppNavigationItem>
				</NcAppNavigationItem>
				<NcAppNavigationItem :name="t('Subscriptions')" :to="{ name: 'subscriptions' }">
					<template #icon>
						<YoutubeSubscriptionIcon :size="20" />
					</template>
				</NcAppNavigationItem>
				<NcAppNavigationItem
					v-model:open="playlistsOpen"
					:name="t('Playlists')"
					:to="{ name: 'playlists' }"
					allow-collapse>
					<template #icon>
						<PlaylistPlayIcon :size="20" />
					</template>
					<NcAppNavigationItem
						v-for="playlist in playlists"
						:key="playlist.id"
						:class="{ 'lucarne-drop-target': dropTarget === `playlist-${playlist.id}` }"
						:name="entityTitle(playlist, 'playlist')"
						:to="{ name: 'playlist', params: { id: playlist.id } }"
						v-on="playlist.kind === 'personal' ? playlistDropEvents(playlist) : {}">
						<template #icon>
							<PlaylistPlayIcon v-if="playlist.kind === 'personal'" :size="20" />
							<YoutubeIcon v-else :size="20" />
						</template>
					</NcAppNavigationItem>
				</NcAppNavigationItem>
				<NcAppNavigationItem :name="t('History')" :to="{ name: 'history' }">
					<template #icon>
						<HistoryIcon :size="20" />
					</template>
				</NcAppNavigationItem>
			</template>
			<template v-if="ready" #footer>
				<NcAppNavigationList class="app-navigation-entry__settings">
					<NcAppNavigationItem :name="t('Catalogues')" :to="{ name: 'catalogues' }">
						<template #icon>
							<FolderMultipleOutlineIcon :size="20" />
						</template>
					</NcAppNavigationItem>
					<NcAppNavigationItem :name="t('Settings')" :to="{ name: 'settings' }">
						<template #icon>
							<CogIcon :size="20" />
						</template>
					</NcAppNavigationItem>
					<template v-if="isAdmin">
						<NcAppNavigationItem :name="t('Administration')" :to="{ name: 'admin' }">
							<template #icon>
								<ShieldAccountIcon :size="20" />
							</template>
						</NcAppNavigationItem>
						<NcAppNavigationItem :name="t('Supervision')" :to="{ name: 'supervision' }">
							<template #icon>
								<ChartTimelineVariantIcon :size="20" />
							</template>
						</NcAppNavigationItem>
					</template>
				</NcAppNavigationList>
			</template>
		</NcAppNavigation>
		<NcAppContent page-heading="Lucarne">
			<NcEmptyContent v-if="failure" :name="t('Unable to start Lucarne')" :description="failure">
				<template #icon>
					<AlertCircleIcon />
				</template>
			</NcEmptyContent>
			<NcLoadingIcon v-else-if="!ready" class="lucarne-loading" :size="44" />
			<router-view v-else />
		</NcAppContent>
	</NcContent>
</template>

<script setup>
import NcAppContent from '@nextcloud/vue/components/NcAppContent'
import NcAppNavigation from '@nextcloud/vue/components/NcAppNavigation'
import NcAppNavigationItem from '@nextcloud/vue/components/NcAppNavigationItem'
import NcAppNavigationList from '@nextcloud/vue/components/NcAppNavigationList'
import NcAppNavigationSearch from '@nextcloud/vue/components/NcAppNavigationSearch'
import NcContent from '@nextcloud/vue/components/NcContent'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import ChartTimelineVariantIcon from 'vue-material-design-icons/ChartTimelineVariant.vue'
import CogIcon from 'vue-material-design-icons/Cog.vue'
import FolderMultipleOutlineIcon from 'vue-material-design-icons/FolderMultipleOutline.vue'
import FolderOffOutlineIcon from 'vue-material-design-icons/FolderOffOutline.vue'
import FolderOutlineIcon from 'vue-material-design-icons/FolderOutline.vue'
import HistoryIcon from 'vue-material-design-icons/History.vue'
import HomeIcon from 'vue-material-design-icons/Home.vue'
import PlaylistPlayIcon from 'vue-material-design-icons/PlaylistPlay.vue'
import ShieldAccountIcon from 'vue-material-design-icons/ShieldAccount.vue'
import YoutubeIcon from 'vue-material-design-icons/Youtube.vue'
import YoutubeSubscriptionIcon from 'vue-material-design-icons/YoutubeSubscription.vue'
import { send } from './api.js'
import { CHANNEL_DRAG_TYPE, VIDEO_DRAG_TYPE } from './drag.js'
import { entityTitle } from './format.js'
import { t } from './i18n.js'
import { notify, notifyError } from './notify.js'
import { catalogMembershipsChanged, ensureBootstrap, loadPlaylists, playlistContentChanged, state } from './store.js'

const route = useRoute()
const router = useRouter()

const ready = ref(false)
const failure = ref('')
const catalogsOpen = ref(true)
const playlistsOpen = ref(false)
const search = ref('')
const dropTarget = ref('')

const catalogs = computed(() => state.bootstrap?.catalogs || [])
const playlists = computed(() => state.playlists)
const isAdmin = computed(() => Boolean(state.bootstrap?.is_admin))
const isVideoList = computed(() => ['home', 'catalog', 'uncategorized'].includes(String(route.name)))

// Dropping an item on an entry of the navigation adds it there, without leaving its other places.
function allowDrop(event, type) {
	if (event.dataTransfer?.types.includes(type)) {
		event.preventDefault()
		event.dataTransfer.dropEffect = 'copy'
	}
}

function leaveDrop(key, event) {
	if (!event.currentTarget.contains(event.relatedTarget)) {
		dropTarget.value = dropTarget.value === key ? '' : dropTarget.value
	}
}

async function dropChannel(catalog, event) {
	dropTarget.value = ''
	const payload = event.dataTransfer?.getData(CHANNEL_DRAG_TYPE)
	if (!payload) {
		return
	}
	const channel = JSON.parse(payload)
	try {
		const result = await send('PUT', `api/catalogs/${catalog.id}/channels/${channel.id}`)
		const names = { channel: channel.title, catalog: catalog.name }
		if (result.added) {
			catalogMembershipsChanged()
			notify(t('"{channel}" added to the catalogue "{catalog}"', names))
		} else {
			notifyError(t('"{channel}" is already in the catalogue "{catalog}"', names))
		}
	} catch (error) {
		notifyError(error)
	}
}

async function dropVideo(playlist, event) {
	dropTarget.value = ''
	const payload = event.dataTransfer?.getData(VIDEO_DRAG_TYPE)
	if (!payload) {
		return
	}
	const video = JSON.parse(payload)
	try {
		const result = await send('POST', `api/playlists/${playlist.id}/videos`, { video_id: video.id })
		const names = { video: video.title, playlist: entityTitle(playlist, 'playlist') }
		if (result.added) {
			playlistContentChanged()
			notify(t('"{video}" added to the playlist "{playlist}"', names))
		} else {
			notifyError(t('"{video}" is already in the playlist "{playlist}"', names))
		}
	} catch (error) {
		notifyError(error)
	}
}

// Only the playlists of the user accept videos: those imported from YouTube are filled by the agent.
function playlistDropEvents(playlist) {
	const key = `playlist-${playlist.id}`
	return {
		dragover: (event) => allowDrop(event, VIDEO_DRAG_TYPE),
		dragenter: () => { dropTarget.value = key },
		dragleave: (event) => leaveDrop(key, event),
		drop: (event) => {
			event.preventDefault()
			dropVideo(playlist, event)
		},
	}
}

onMounted(async () => {
	try {
		await ensureBootstrap()
		await loadPlaylists()
		await router.isReady()
		ready.value = true
	} catch (error) {
		failure.value = error.message
	}
})

// The playlists of the navigation follow the pages: they are created, renamed and imported in the background.
watch(() => route.fullPath, () => { loadPlaylists().catch(() => {}) })

// Keep the navigation search field in sync with the address, and the other way round.
watch(() => route.query.search, (value) => { search.value = String(value || '') }, { immediate: true })

let searchTimer = null
watch(search, (value) => {
	if (value === String(route.query.search || '')) {
		return
	}
	clearTimeout(searchTimer)
	searchTimer = setTimeout(() => {
		const target = isVideoList.value ? { name: route.name, params: route.params } : { name: 'home' }
		router.push({ ...target, query: value ? { search: value } : {} })
	}, 300)
})
onBeforeUnmount(() => clearTimeout(searchTimer))
</script>

<style>
/* Page with a footer drawn over its bottom edge, like the zone to drop an item on to remove it. */
.lucarne-page-frame {
	position: relative;
	height: 100%;
}

/* Catalogue of the navigation under a dragged subscription. */
.lucarne-drop-target {
	border-radius: var(--border-radius-element);
	outline: 2px dashed var(--color-primary-element);
	outline-offset: -2px;
	background-color: var(--color-background-hover);
}

/* Footer of the navigation: same rules as the Files app, so that it is never squeezed. */
.app-navigation-entry__settings {
	flex: 0 0 auto;
	padding-top: 0 !important;
}

/* Shared page frame: only the spacing needed around the Nextcloud components. */
.lucarne-page {
	box-sizing: border-box;
	height: 100%;
	overflow-y: auto;
	padding: calc(var(--default-grid-baseline) * 2) calc(var(--default-grid-baseline) * 4) calc(var(--default-grid-baseline) * 8);
	padding-inline-start: calc(var(--default-clickable-area) + var(--default-grid-baseline) * 4);
}

.lucarne-loading {
	margin-block-start: 20vh;
}
</style>
