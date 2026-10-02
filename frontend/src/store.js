import { reactive } from 'vue'
import { request } from './api.js'
import { i18n } from './i18n.js'

export const state = reactive({ bootstrap: null, playlists: [], catalogRevision: 0, playlistRevision: 0 })

export async function loadBootstrap() {
	const data = await request('api/bootstrap')
	i18n.translations = data.translations || {}
	i18n.language = data.language || 'en'
	state.bootstrap = data
}

export function setCatalogs(catalogs) {
	state.bootstrap.catalogs = catalogs
}

/** Tell the lists that depend on catalogue memberships that they changed. */
export function catalogMembershipsChanged() {
	state.catalogRevision++
}

/** Playlists of the navigation: all of them, personal ones and those imported from YouTube. */
export async function loadPlaylists() {
	state.playlists = await request('api/playlists')
}

/** Tell the pages that show the content of playlists that it changed. */
export function playlistContentChanged() {
	state.playlistRevision++
}

let pending = null

/**
 * Load the bootstrap data once; later callers wait for the same request.
 */
export function ensureBootstrap() {
	pending ??= loadBootstrap()
	return pending
}
