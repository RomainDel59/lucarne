import { createRouter, createWebHistory } from 'vue-router'
import { ensureBootstrap, state } from './store.js'
import AdminView from './views/AdminView.vue'
import CataloguesView from './views/CataloguesView.vue'
import ChannelView from './views/ChannelView.vue'
import HistoryView from './views/HistoryView.vue'
import HomeView from './views/HomeView.vue'
import PlaylistsView from './views/PlaylistsView.vue'
import PlaylistView from './views/PlaylistView.vue'
import SettingsView from './views/SettingsView.vue'
import SubscriptionsView from './views/SubscriptionsView.vue'
import SupervisionView from './views/SupervisionView.vue'
import VideoView from './views/VideoView.vue'

const routes = [
	{ path: '/', name: 'home', component: HomeView },
	{ path: '/catalog/:id(\\d+)', name: 'catalog', component: HomeView },
	{ path: '/uncategorized', name: 'uncategorized', component: HomeView },
	{ path: '/subscriptions', name: 'subscriptions', component: SubscriptionsView },
	{ path: '/playlists', name: 'playlists', component: PlaylistsView },
	{ path: '/history', name: 'history', component: HistoryView },
	{ path: '/channel/:id(\\d+)', name: 'channel', component: ChannelView },
	{ path: '/playlist/:id(\\d+)', name: 'playlist', component: PlaylistView },
	{ path: '/video/:id(\\d+)', name: 'video', component: VideoView },
	{ path: '/settings', name: 'settings', component: SettingsView },
	{ path: '/catalogues', name: 'catalogues', component: CataloguesView },
	{ path: '/admin', name: 'admin', component: AdminView, meta: { admin: true } },
	{ path: '/supervision', name: 'supervision', component: SupervisionView, meta: { admin: true } },
	{ path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
]

// The page may be served with or without `index.php`, so the base is taken from the address.
const PAGE_PATH = '/apps/app_api/embedded/lucarne/main'
const base = location.pathname.slice(0, location.pathname.indexOf(PAGE_PATH) + PAGE_PATH.length)

export const router = createRouter({
	history: createWebHistory(base),
	routes,
})

router.beforeEach(async (to) => {
	if (!to.meta.admin) {
		return true
	}
	await ensureBootstrap().catch(() => {})
	if (!state.bootstrap?.is_admin) {
		return { name: 'home' }
	}
	return true
})
