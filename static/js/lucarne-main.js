(function() {
	'use strict'

	const APP_ID = 'lucarne'
	const PROXY_ROOT = `/apps/app_api/proxy/${APP_ID}/`
	const ROUTER_ROOT = `/apps/app_api/embedded/${APP_ID}/main`
	const state = { bootstrap: null, view: 'home', params: {}, timer: null, player: null, lastProgressSave: 0 }
	const paths = {
		home: 'M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z',
		subscriptions: 'M4 6h16v2H4V6zm2 4h12v2H6v-2zm3 4h6v2H9v-2z',
		playlists: 'M4 6h12v2H4V6zm0 5h12v2H4v-2zm0 5h8v2H4v-2zm14-5v7l5-3.5z',
		history: 'M13 3a9 9 0 1 0 8.95 10h-2.02A7 7 0 1 1 18 7.05V10h-6V4l2.45 2.45A8.9 8.9 0 0 0 13 3zm-1 5h2v5.17l3.24 1.87-1 1.73L12 14.32z',
		settings: 'M19.43 12.98c.04-.32.07-.65.07-.98s-.03-.66-.08-.98l2.11-1.65-2-3.46-2.49 1a7.2 7.2 0 0 0-1.69-.98L15 3.27h-4l-.4 2.66c-.61.25-1.17.59-1.69.98l-2.49-1-2 3.46 2.11 1.65c-.04.32-.08.66-.08.98s.03.66.08.98l-2.11 1.65 2 3.46 2.49-1c.52.4 1.08.73 1.69.98l.4 2.66h4l.4-2.66c.61-.25 1.17-.59 1.69-.98l2.49 1 2-3.46zM13 15.5A3.5 3.5 0 1 1 13 8a3.5 3.5 0 0 1 0 7.5z',
		catalogues: 'M4 4h7v7H4V4zm9 0h7v7h-7V4zM4 13h7v7H4v-7zm9 0h7v7h-7v-7z',
		admin: 'M12 2 3 6v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V6l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V13H5V7.3l7-3.11v8.8z',
		supervision: 'M3 3h18v18H3V3zm2 2v14h14V5H5zm2 10h2v2H7v-2zm4-4h2v6h-2v-6zm4-3h2v9h-2V8z',
		video: 'M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-8 12.5v-9l6 4.5-6 4.5z',
		add: 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6z',
		delete: 'M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zm3.46-7.12 1.41-1.41L12 11.59l1.12-1.12 1.41 1.41L13.41 13l1.12 1.12-1.41 1.41L12 14.41l-1.12 1.12-1.41-1.41L10.59 13zM15.5 4l-1-1h-5l-1 1H5v2h14V4z',
		back: 'M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20z',
		up: 'm7 14 5-5 5 5z',
		down: 'm7 10 5 5 5-5z',
		right: 'm9 18 6-6-6-6z',
		left: 'm15 18-6-6 6-6z',
		refresh: 'M17.65 6.35A7.95 7.95 0 0 0 12 4V1L8 5l4 4V6a6 6 0 1 1-5.65 4H4.26A8 8 0 1 0 17.65 6.35z',
		search: 'M9.5 3a6.5 6.5 0 1 0 3.98 11.64L19.85 21 21 19.85l-6.36-6.37A6.5 6.5 0 0 0 9.5 3zm0 2a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9z',
		close: 'M18.3 5.71 12 12l6.3 6.29-1.42 1.42L10.59 13.4 4.29 19.7l-1.41-1.42L9.17 12l-6.3-6.29L4.3 4.29l6.29 6.3 6.3-6.3z',
		menu: 'M3 6h18v2H3V6zm0 5h18v2H3v-2zm0 5h18v2H3v-2z',
	}

	function apiUrl(path) { return OC.generateUrl(PROXY_ROOT + path.replace(/^\//, '')) }
	function t(key, variables = {}) {
		let value = state.bootstrap?.translations?.[key] || key
		Object.entries(variables).forEach(([name, replacement]) => { value = value.replace(`{${name}}`, replacement) })
		return value
	}
	function icon(name, size = 22) {
		const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
		svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('width', size); svg.setAttribute('height', size); svg.classList.add('lucarne-icon')
		const path = document.createElementNS('http://www.w3.org/2000/svg', 'path'); path.setAttribute('d', paths[name] || paths.video); svg.append(path)
		return svg
	}
	function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node }
	function button(label, iconName, style = 'tonal', action = null) {
		const node = el('button', `lucarne-button lucarne-button--${style}`); node.type = 'button'; if (iconName) node.append(icon(iconName)); if (label) node.append(el('span', '', label)); if (action) node.addEventListener('click', action); return node
	}
	function iconButton(name, label, action) { const node = el('button', 'lucarne-icon-button'); node.type = 'button'; node.title = label; node.setAttribute('aria-label', label); node.append(icon(name)); node.addEventListener('click', action); return node }
	async function request(path, options = {}) {
		const response = await fetch(apiUrl(path), { credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options })
		const body = response.status === 204 ? null : await response.json().catch(() => ({}))
		if (!response.ok) throw new Error(body?.error || body?.detail || `${t('Request failed')} (${response.status})`)
		return body
	}
	function notify(message, error = false) { document.querySelector('.lucarne-snackbar')?.remove(); const node = el('div', `lucarne-snackbar${error ? ' lucarne-snackbar--error' : ''}`, message); document.body.append(node); setTimeout(() => node.remove(), 4500) }
	function formatDate(timestamp) { if (!timestamp) return t('Unknown date'); return new Intl.DateTimeFormat(state.bootstrap?.language || 'en', { dateStyle: 'medium' }).format(new Date(timestamp * 1000)) }
	function duration(seconds) { seconds = Math.max(0, Math.floor(Number(seconds || 0))); const hours = Math.floor(seconds / 3600); const pad = value => String(value).padStart(2, '0'); const minutes = Math.floor((seconds % 3600) / 60); return hours ? `${hours}:${pad(minutes)}:${pad(seconds % 60)}` : `${minutes}:${pad(seconds % 60)}` }
	function presentationText(value, variables = {}) { if (!value) return ''; if (value.startsWith('Channel · ')) return `${t('Channel')} · ${value.slice(10)}`; if (value.startsWith('Playlist · ')) return `${t('Playlist')} · ${value.slice(11)}`; const known = value.match(/^(\d+) known videos · (unlimited|limit (\d+))$/); if (known) return t(known[2] === 'unlimited' ? '{count} known videos · unlimited' : '{count} known videos · limit {limit}', { count: known[1], limit: known[3] }); return t(value, variables) }
	function entityTitle(item, type) { return type === 'playlist' && String(item.external_id || '').startsWith('pending_') ? t('Pending playlist') : item.title }
	const technicalLabels = {
		'phase.discover': () => t('Checking sources'), 'phase.metadata': () => t('Metadata and thumbnails'), 'phase.history': () => t('Retrieving history'), 'phase.history_required': () => t('First historical batch'),
		'job.discover': () => t('Check sources'), 'job.metadata': () => t('Retrieve metadata and thumbnails'), 'job.history': () => t('Retrieve history'), 'job.initialize_channel': () => t('Add a subscription'), 'job.initialize_playlist': () => t('Import a playlist'), 'job.inspect_video': () => t('Add a video'), 'job.sync_source': () => t('Reactivate a subscription'), 'job.delete_channel': () => t('Delete a subscription'), 'job.delete_playlist': () => t('Delete a playlist'), 'job.delete_video': () => t('Delete a video'),
		'status.queued': () => t('Queued'), 'status.running': () => t('Running'), 'status.error': () => t('Error'),
	}
	function technicalLabel(key) { return technicalLabels[key]?.() ?? key }

	function modal({ title, body, submit = t('Save'), cancel = t('Cancel'), danger = false }) {
		return new Promise(resolve => {
			const dialog = el('dialog', 'lucarne-dialog'); const form = el('form'); form.method = 'dialog'
			const header = el('header'); header.append(el('h2', '', title), iconButton('close', t('Close'), () => dialog.close('cancel')))
			const content = el('div', 'lucarne-dialog__body'); if (typeof body === 'string') content.append(el('p', '', body)); else content.append(body)
			const cancelButton = button(cancel, null, 'text', () => dialog.close('cancel'))
			const submitButton = button(submit, null, danger ? 'danger' : 'filled')
			submitButton.type = 'submit'
			const footer = el('footer'); footer.append(cancelButton, submitButton)
			form.append(header, content, footer); dialog.append(form); document.body.append(dialog)
			form.addEventListener('submit', event => { event.preventDefault(); if (form.reportValidity()) dialog.close('submit') })
			dialog.addEventListener('close', () => { const accepted = dialog.returnValue === 'submit'; dialog.remove(); resolve(accepted) }); dialog.showModal()
		})
	}
	function field(label, type = 'text', value = '') { const wrapper = el('div', 'lucarne-field'); const input = el(type === 'select' ? 'select' : 'input', type === 'select' ? 'lucarne-select' : 'lucarne-input'); if (type !== 'select') { input.type = type; input.required = true } input.value = value ?? ''; wrapper.append(el('label', '', label), input); return { wrapper, input } }
	function selectField(label, choices, value = '') { const result = field(label, 'select'); choices.forEach(([id, name]) => { const option = el('option', '', name); option.value = id; option.selected = String(id) === String(value ?? ''); result.input.append(option) }); return result }

	function settingsForm(values, includeName = false, includeHistory = false) {
		const body = el('div', 'lucarne-form-grid'); const fields = {}
		if (includeName) { fields.title = field(t('Name'), 'text', values.title); body.append(fields.title.wrapper) }
		fields.mode = selectField(t('Playback mode'), [['', t('Inherit ({value})', { value: values.inheritedMode || t('Video') })], ['video', t('Video')], ['audio', t('Audio only')]], values.mode || '')
		fields.quality = selectField(t('Video quality'), [['', t('Inherit ({value})', { value: values.inheritedQuality || '720p' })], ['360', '360p'], ['480', '480p'], ['720', '720p'], ['1080', '1080p'], ['best', t('Best available')]], values.quality || '')
		fields.audio_quality = selectField(t('Audio quality'), [['', t('Inherit ({value})', { value: `${values.inheritedAudio || 128} kbps` })], ['96', '96 kbps'], ['128', '128 kbps'], ['192', '192 kbps'], ['256', '256 kbps']], values.audio_quality || '')
		body.append(fields.mode.wrapper, fields.quality.wrapper, fields.audio_quality.wrapper)
		if (includeHistory) fields.history_limit = selectField(t('History limit'), [['', t('Inherit ({value})', { value: values.inheritedHistoryLabel || t('Unlimited') })], ['0', t('Unlimited')], ['10', '10'], ['25', '25'], ['50', '50'], ['100', '100'], ['250', '250']], values.history_limit ?? '')
		if (includeHistory) body.append(fields.history_limit.wrapper)
		const adapt = () => { fields.quality.wrapper.hidden = fields.mode.input.value === 'audio' }
		fields.mode.input.addEventListener('change', adapt); adapt()
		return { body, fields, values: () => { const result = Object.fromEntries(Object.entries(fields).map(([key, item]) => [key, item.input.value === '' ? null : item.input.value])); if (result.mode === 'audio') result.quality = null; return result } }
	}

	function pageHeader(title, actions = []) { const header = el('header', 'lucarne-page-header'); const menu = iconButton('menu', t('Open navigation'), () => { document.querySelector('.lucarne-navigation')?.classList.add('lucarne-navigation--open'); const scrim = document.querySelector('.lucarne-scrim'); if (scrim) scrim.hidden = false }); menu.classList.add('lucarne-menu-button'); const heading = el('h1', '', title); heading.title = title; const controls = el('div', 'lucarne-page-actions'); actions.forEach(action => controls.append(action)); header.append(menu, heading, controls); return header }
	function empty(title, message, action = null) { const root = el('div', 'lucarne-empty'); const inner = el('div'); inner.append(icon('video', 64), el('h2', '', title), el('p', '', message)); if (action) inner.append(action); root.append(inner); return root }
	function loading() { const root = el('div', 'lucarne-loading'); root.append(el('div', 'lucarne-spinner')); return root }

	function videoCard(video, options = {}) {
		const card = el('article', 'lucarne-video-card'); card.tabIndex = 0
		const media = el('div', 'lucarne-video-card__media'); if (video.thumbnail_url) { const image = new Image(); image.src = apiUrl(video.thumbnail_url); image.alt = ''; media.append(image) } else media.append(icon('video', 54))
		if (video.duration) media.append(el('span', 'lucarne-video-card__duration', duration(video.duration)))
		if (video.availability && video.availability !== 'available') media.append(el('span', 'lucarne-video-card__unavailable', t('Unavailable')))
		if (Number(video.history_duration || 0) > 0) { const progress = el('span', 'lucarne-video-card__progress'); progress.style.width = `${Math.min(100, Number(video.history_position || 0) / Number(video.history_duration) * 100)}%`; media.append(progress) }
		const body = el('div', 'lucarne-video-card__body'); const title = el('div', 'lucarne-video-card__title', video.title || t('Pending video')); title.title = video.title || t('Pending video')
		const meta = el('div', 'lucarne-video-card__meta'); const channel = el('span', '', video.channel_name || t('Standalone video')); channel.title = channel.textContent; meta.append(channel, el('span', '', '·'), el('span', '', formatDate(video.published_at || video.created_at)))
		body.append(title, meta); card.append(media, body)
		const open = () => navigate('video', { id: video.id, playlistId: options.playlistId }); card.addEventListener('click', open); card.addEventListener('keydown', event => { if (event.key === 'Enter') open() })
		if (options.remove) { const remove = iconButton('delete', t('Remove'), event => { event.stopPropagation(); options.remove(video) }); remove.classList.add('lucarne-card-remove'); card.append(remove) }
		return card
	}
	function videoGrid(items, options = {}) { const grid = el('div', 'lucarne-grid'); items.forEach(item => grid.append(videoCard(item, options))); return grid }
	function pendingVideoCard(job) { const card = el('article', 'lucarne-video-card'); const media = el('div', 'lucarne-video-card__media'); media.append(icon('video', 54)); const body = el('div', 'lucarne-video-card__body'); body.append(el('div', 'lucarne-video-card__title', t('Pending video')), el('div', 'lucarne-video-card__meta', formatDate(job.created_at))); card.append(media, body); return card }
	function entityCard(item, type, open) { const card = el('button', `lucarne-entity-card${type === 'playlist' ? ' lucarne-entity-card--playlist' : ''}`); card.type = 'button'; const picture = el('span', 'lucarne-entity-card__image'); if (item.image_url) { const image = new Image(); image.src = apiUrl(item.image_url); image.alt = ''; picture.append(image) } else picture.append(icon(type === 'playlist' ? 'playlists' : 'subscriptions', 34)); const copy = el('span', 'lucarne-entity-card__copy'); const displayTitle = entityTitle(item, type); const title = el('span', 'lucarne-entity-card__title', displayTitle); title.title = displayTitle; const count = Number(item.video_count || 0); copy.append(title, el('span', 'lucarne-entity-card__subtitle', count ? t('{count} videos · {date}', { count, date: formatDate(item.latest_published_at) }) : t('No videos'))); if (['pending', 'initializing', 'syncing'].includes(item.sync_status)) copy.append(el('span', 'lucarne-status', t('Initialization pending'))); if (item.sync_status === 'error') copy.append(el('span', 'lucarne-status lucarne-status--error', type === 'playlist' ? t('Import needs retry') : t('Synchronization needs retry'))); card.append(picture, copy); card.addEventListener('click', open); return card }

	function pagination(data, reload) { if (data.total <= 10) return null; const root = el('div', 'lucarne-pagination'); const previous = button(t('Previous page'), 'back', 'text', () => reload(data.page - 1)); previous.disabled = data.page <= 1; const next = button(t('Next page'), 'right', 'text', () => reload(data.page + 1)); next.disabled = data.page * 10 >= data.total; root.append(previous, el('span', '', t('Page {page}', { page: data.page })), next); return root }
	async function nextBatchMessage() { const schedule = await request('api/schedule'); const delay = Math.max(0, Number(schedule.next_lot_at) - Number(schedule.server_time)); return t('Videos will appear after the next batch, in about {minutes} min.', { minutes: Math.max(1, Math.ceil(delay / 60)) }) }

	function mount(content) { const main = document.querySelector('.lucarne-main'); main.replaceChildren(); const page = el('section', 'lucarne-page'); page.append(content); main.append(page); main.scrollTop = 0 }
	function closeNavigation() { document.querySelector('.lucarne-navigation')?.classList.remove('lucarne-navigation--open'); const scrim = document.querySelector('.lucarne-scrim'); if (scrim) scrim.hidden = true }
	async function navigate(view, params = {}, push = true) { closeNavigation(); cleanupPlayer(); state.view = view; state.params = params; if (push) history.pushState({ view, params }, '', routeUrl(view, params)); drawNavigation(); mount(loading()); try { await render() } catch (error) { mount(empty(t('Something went wrong'), error.message)); notify(error.message, true) } }
	function routeUrl(view, params) {
		const suffix = view === 'home' ? '' : `/${view}${params.id ? `/${params.id}` : ''}`
		const query = new URLSearchParams()
		Object.entries(params).forEach(([key, value]) => { if (key !== 'id' && value !== undefined && value !== null && value !== '') query.set(key, value) })
		return OC.generateUrl(ROUTER_ROOT + suffix) + (query.size ? `?${query}` : '')
	}
	function decodeRoute() {
		const path = location.pathname.split('/main')[1] || ''
		const parts = path.split('/').filter(Boolean)
		const params = Object.fromEntries(new URLSearchParams(location.search))
		for (const key of ['page', 'playlistId']) if (params[key]) params[key] = Number(params[key])
		if (parts[1]) params.id = Number(parts[1])
		return { view: parts[0] || 'home', params }
	}

	function drawNavigation() {
		const nav = document.querySelector('.lucarne-navigation'); nav.replaceChildren(); const brand = el('div', 'lucarne-navigation__brand'); brand.append(icon('video', 28), el('span', '', 'Lucarne')); nav.append(brand)
		const list = el('div', 'lucarne-nav-list'); const entries = [['home', 'Home', 'home'], ['subscriptions', 'Subscriptions', 'subscriptions'], ['playlists', 'Playlists', 'playlists'], ['history', 'History', 'history']]
		entries.forEach(([view, label, iconName]) => { const item = el('button', 'lucarne-nav-item'); item.type = 'button'; if (state.view === view) item.setAttribute('aria-current', 'page'); item.append(icon(iconName), el('span', '', t(label))); item.addEventListener('click', () => navigate(view)); list.append(item); if (view === 'home') { (state.bootstrap?.catalogs || []).forEach(catalog => { const child = el('button', 'lucarne-nav-item lucarne-nav-item--catalog'); child.type = 'button'; child.title = catalog.name; if (state.view === 'catalog' && Number(state.params.id) === Number(catalog.id)) child.setAttribute('aria-current', 'page'); child.append(icon('right', 16), el('span', '', catalog.name)); child.addEventListener('click', () => navigate('catalog', { id: catalog.id })); list.append(child) }); const uncategorized = el('button', 'lucarne-nav-item lucarne-nav-item--catalog'); uncategorized.type = 'button'; uncategorized.title = t('Uncatalogued'); if (state.view === 'uncategorized') uncategorized.setAttribute('aria-current', 'page'); uncategorized.append(icon('subscriptions', 16), el('span', '', t('Uncatalogued'))); uncategorized.addEventListener('click', () => navigate('uncategorized')); list.append(uncategorized) } })
		const separator = () => { const item = el('div', 'lucarne-nav-separator'); item.setAttribute('role', 'separator'); list.append(item) }
		const appendItem = (view, label, iconName) => { const item = el('button', 'lucarne-nav-item'); item.type = 'button'; if (state.view === view) item.setAttribute('aria-current', 'page'); item.append(icon(iconName), el('span', '', t(label))); item.addEventListener('click', () => navigate(view)); list.append(item) }
		separator()
		appendItem('settings', 'Settings', 'settings')
		appendItem('catalogues', 'Catalogues', 'catalogues')
		if (state.bootstrap?.is_admin) {
			separator()
			appendItem('admin', 'Administration', 'admin')
			appendItem('supervision', 'Supervision', 'supervision')
		}
		nav.append(list)
	}

	async function renderHome(filter = {}) {
		let page = Number(state.params.page || 1); const root = document.createDocumentFragment(); const search = el('input', 'lucarne-input lucarne-search'); search.type = 'search'; search.placeholder = t('Search videos'); search.value = state.params.search || ''; let searchTimer; search.addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => navigate(state.view, { ...state.params, page: 1, search: search.value }), 300) }); const actions = [search]; if (!filter.query) actions.push(button(t('Add'), 'add', 'filled', addVideoDialog)); root.append(pageHeader(filter.title || t('Home'), actions)); const query = new URLSearchParams({ page, search: state.params.search || '', ...filter.query }); const data = await request(`api/catalog?${query}`); const pending = data.pending_jobs || []; if (!data.items.length && !pending.length) { const searched = Boolean(state.params.search); if (filter.query?.uncategorized) root.append(empty(t('No videos'), searched ? t('No results for this search.') : t('All your channels and videos are already in a catalogue.'))); else if (filter.query?.catalog_id) root.append(empty(t('No videos'), searched ? t('No results for this search.') : t('This catalogue does not contain videos from its subscriptions yet.'))); else root.append(empty(t('No videos yet'), searched ? t('No results for this search.') : t('Add a channel, playlist or video to start your library.'), searched ? null : button(t('Add'), 'add', 'filled', addVideoDialog))) } else { const grid = videoGrid(data.items); pending.forEach(job => grid.prepend(pendingVideoCard(job))); root.append(grid); const pager = pagination(data, value => navigate(state.view, { ...state.params, page: value })); if (pager) root.append(pager) } mount(root)
	}

	async function renderSubscriptions() {
		const root = document.createDocumentFragment(); const catalogs = [['', t('All catalogues')], ...(state.bootstrap.catalogs || []).map(item => [String(item.id), item.name]), ['uncategorized', t('- Uncatalogued -')]]; const filter = selectField('', catalogs, state.params.catalog || ''); filter.wrapper.replaceWith(filter.input); filter.input.addEventListener('change', () => navigate('subscriptions', { ...state.params, catalog: filter.input.value })); const sort = selectField('', [['alpha', t('Alphabetical order')], ['recent', t('Latest video')]], state.params.sort || 'alpha'); sort.wrapper.replaceWith(sort.input); sort.input.addEventListener('change', () => navigate('subscriptions', { ...state.params, sort: sort.input.value })); root.append(pageHeader(t('Subscriptions'), [filter.input, sort.input, button(t('Add'), 'add', 'filled', addChannelDialog)])); const query = state.params.catalog === 'uncategorized' ? '?uncategorized=true' : state.params.catalog ? `?catalog_id=${state.params.catalog}` : ''; let channels = await request(`api/channels${query}`); if (state.params.sort === 'recent') channels.sort((a, b) => Number(b.latest_published_at || 0) - Number(a.latest_published_at || 0)); const grid = el('div', 'lucarne-entity-grid'); channels.forEach(item => grid.append(entityCard(item, 'channel', () => navigate('channel', { id: item.id })))); root.append(channels.length ? grid : empty(t('No subscriptions'), t('Add a YouTube channel to follow its videos.'))); mount(root)
	}

	async function renderPlaylists() {
		const root = document.createDocumentFragment(); const sort = selectField('', [['alpha', t('Alphabetical order')], ['recent', t('Latest video')]], state.params.sort || 'alpha'); sort.wrapper.replaceWith(sort.input); sort.input.addEventListener('change', () => navigate('playlists', { sort: sort.input.value })); root.append(pageHeader(t('Playlists'), [sort.input, button(t('Add'), 'add', 'filled', addPlaylistDialog)])); let playlists = await request('api/playlists'); if (state.params.sort === 'recent') playlists.sort((a, b) => Number(b.latest_published_at || 0) - Number(a.latest_published_at || 0)); const grid = el('div', 'lucarne-entity-grid'); playlists.forEach(item => grid.append(entityCard(item, 'playlist', () => navigate('playlist', { id: item.id })))); root.append(playlists.length ? grid : empty(t('No playlists'), t('Create a personal playlist or import one from YouTube.'))); mount(root)
	}

	async function renderChannel() {
		const channel = await request(`api/channels/${state.params.id}`); const root = document.createDocumentFragment()
		const actions = channel.subscribed
			? [button(t('Settings'), 'settings', 'tonal', () => playbackDialog(channel, 'channel')), button(t('Unsubscribe'), 'delete', 'danger', () => deleteEntity('channel', channel))]
			: [button(t('Subscribe'), 'add', 'filled', () => subscribeChannel(channel))]
		root.append(pageHeader(entityTitle(channel, 'channel'), actions)); const data = await request(`api/catalog?channel_id=${channel.id}&page=${state.params.page || 1}`)
		if (data.items.length) root.append(videoGrid(data.items))
		else if (channel.sync_status === 'error') root.append(empty(t('Synchronization stopped'), channel.sync_error || t('The agent will retry this source in a future batch.')))
		else root.append(empty(t('No videos'), await nextBatchMessage()))
		const pager = pagination(data, page => navigate('channel', { id: channel.id, page })); if (pager) root.append(pager); mount(root)
	}

	async function renderPlaylist() {
		const playlist = await request(`api/playlists/${state.params.id}`); const root = document.createDocumentFragment(); const imported = playlist.kind === 'youtube'
		const actions = [button(t('Settings'), 'settings', 'tonal', () => playbackDialog(playlist, 'playlist'))]
		if (!imported) actions.push(button(t('Add'), 'add', 'tonal', () => addPlaylistVideoDialog(playlist)))
		actions.push(button(t('Delete'), 'delete', 'danger', () => deleteEntity('playlist', playlist))); root.append(pageHeader(entityTitle(playlist, 'playlist'), actions))
		const data = await request(`api/catalog?playlist_id=${playlist.id}&page=${state.params.page || 1}`)
		const pending = data.pending_jobs || []
		if (data.items.length || pending.length) { const grid = videoGrid(data.items, { playlistId: playlist.id, remove: imported ? null : video => removePlaylistVideo(playlist, video) }); pending.forEach(job => grid.prepend(pendingVideoCard(job))); root.append(grid) }
		else root.append(empty(t('No videos'), imported ? await nextBatchMessage() : t('Add a video to this playlist.')))
		const pager = pagination(data, page => navigate('playlist', { id: playlist.id, page })); if (pager) root.append(pager); mount(root)
	}

	async function renderHistory() { const root = document.createDocumentFragment(); const data = await request(`api/history?page=${state.params.page || 1}`); root.append(pageHeader(t('History'), data.items.length ? [button(t('Clear'), 'delete', 'danger', clearHistory)] : [])); root.append(data.items.length ? videoGrid(data.items) : empty(t('No history'), t('Videos you watch will appear here.'))); const pager = pagination(data, page => navigate('history', { page })); if (pager) root.append(pager); mount(root) }

	async function renderVideo() {
		const video = await request(`api/videos/${state.params.id}${state.params.playlistId ? `?playlist_id=${state.params.playlistId}` : ''}`); const playlists = (await request('api/playlists')).filter(item => item.kind === 'personal'); const root = document.createDocumentFragment(); root.append(pageHeader(video.title, [button(t('Back'), 'back', 'text', () => history.length > 1 ? history.back() : navigate('home')), button(t('Settings'), 'settings', 'tonal', () => playbackDialog(video, 'video')), button(t('Delete'), 'delete', 'danger', () => deleteVideo(video))])); const playerShell = el('div', 'lucarne-player-shell'); if (video.thumbnail_url) { const poster = new Image(); poster.src = apiUrl(video.thumbnail_url); poster.alt = ''; playerShell.append(poster) } else playerShell.append(icon('video', 72)); const unavailable = video.availability !== 'available' && !video.media_available; const playerStatus = el('div', `lucarne-player-status${unavailable ? ' lucarne-player-status--error' : ''}`); const spinner = el('span', 'lucarne-spinner'); spinner.hidden = true; const statusMessage = unavailable ? (video.unavailable_reason || t('This video is no longer available on YouTube.')) : video.media_retained ? t('This media is retained in your library.') : video.media_available ? t('This media is available in the temporary cache.') : t('The media will be downloaded completely before playback.'); const statusText = el('p', '', statusMessage); const play = button(video.media_available ? t('Play') : t('Download and play'), 'video', 'filled', () => downloadAndPlay(video, playerShell, { play, spinner, statusText, playerStatus })); play.disabled = unavailable; playerStatus.append(spinner, statusText, play); playerShell.append(playerStatus); const toolbar = el('div', 'lucarne-video-toolbar'); const meta = el('div', 'lucarne-video-meta'); const channel = button(video.channel_name || t('Standalone video'), null, 'tonal', () => { if (video.channel_id) navigate('channel', { id: video.channel_id }) }); if (!video.channel_id) channel.disabled = true; meta.append(channel, el('span', '', `${formatDate(video.published_at)}${video.duration ? ` · ${duration(video.duration)}` : ''}`)); const keep = el('label', 'lucarne-switch'); const checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.checked = Boolean(video.retained); checkbox.addEventListener('change', async () => { try { await request(`api/videos/${video.id}/retention`, { method: 'PUT', body: JSON.stringify({ retained: checkbox.checked }) }); video.retained = checkbox.checked; notify(checkbox.checked ? t('The next download will be retained.') : t('The retained media was deleted.')) } catch (error) { checkbox.checked = !checkbox.checked; notify(error.message, true) } }); keep.append(checkbox, el('span', '', t('Keep offline'))); meta.append(keep); const select = el('select', 'lucarne-select'); const none = el('option', '', t('Add to a playlist')); none.value = ''; select.append(none); playlists.forEach(item => { const option = el('option', '', `${(video.playlist_ids || []).includes(item.id) ? '✓ ' : ''}${item.title}`); option.value = item.id; option.disabled = (video.playlist_ids || []).includes(item.id); select.append(option) }); select.addEventListener('change', async () => { if (!select.value) return; try { await request(`api/playlists/${select.value}/videos`, { method: 'POST', body: JSON.stringify({ video_id: video.id }) }); const option = select.selectedOptions[0]; option.textContent = `✓ ${option.textContent}`; option.disabled = true; notify(t('Video added to playlist')); select.value = '' } catch (error) { notify(error.message, true) } }); toolbar.append(meta, select); root.append(playerShell, toolbar, el('div', 'lucarne-description', video.description || t('No description.'))); mount(root)
	}

	async function downloadAndPlay(video, shell, controls) { controls.play.disabled = true; controls.spinner.hidden = false; controls.playerStatus.classList.remove('lucarne-player-status--error'); controls.statusText.textContent = t('Preparing playback…'); try { const job = await request(`api/videos/${video.id}/downloads${state.params.playlistId ? `?playlist_id=${state.params.playlistId}` : ''}`, { method: 'POST', body: '{}' }); for (let attempt = 0; attempt < 720; attempt++) { const status = await request(`api/downloads/${job.id}`); if (status.status === 'ready') { const player = el(status.mode === 'audio' ? 'audio' : 'video', `lucarne-player${status.mode === 'audio' ? ' lucarne-player--audio' : ''}`); player.controls = true; player.playsInline = true; shell.classList.toggle('lucarne-player-shell--audio', status.mode === 'audio'); if (status.mode !== 'audio' && video.thumbnail_url) player.poster = apiUrl(video.thumbnail_url); player.src = apiUrl(`media/downloads/${job.id}`); shell.replaceChildren(player); state.player = player; state.lastProgressSave = Number(video.history_position || 0); if (state.lastProgressSave > 0) player.addEventListener('loadedmetadata', () => { if (!video.history_completed && state.lastProgressSave < player.duration - 5) player.currentTime = state.lastProgressSave }, { once: true }); player.addEventListener('timeupdate', scheduleProgress); player.addEventListener('pause', () => saveProgress(true)); player.addEventListener('ended', () => saveProgress(true)); await player.play(); return } if (status.status === 'error') throw new Error(status.error || t('Download failed')); controls.statusText.textContent = status.status === 'queued' ? t('Download queued…') : t('Downloading the complete media…'); await new Promise(resolve => setTimeout(resolve, 2000)) } throw new Error(t('The download took too long.')) } catch (error) { controls.spinner.hidden = true; controls.statusText.textContent = error.message; controls.playerStatus.classList.add('lucarne-player-status--error'); controls.play.disabled = false; notify(error.message, true) } }
	function scheduleProgress() { if (!state.player) return; if (state.player.currentTime < state.lastProgressSave || state.player.currentTime - state.lastProgressSave >= 10) saveProgress(false) }
	async function saveProgress(force) { if (!state.player || !state.params.id || (!force && state.player.paused) || !Number.isFinite(state.player.currentTime)) return; const position = state.player.currentTime; state.lastProgressSave = position; try { await request(`api/history/${state.params.id}`, { method: 'PUT', keepalive: Boolean(force), body: JSON.stringify({ position, duration: Number.isFinite(state.player.duration) ? state.player.duration : null }) }) } catch (_) {} }
	function cleanupPlayer() { if (state.player) { saveProgress(true); state.player.pause(); state.player.removeAttribute('src'); state.player.load(); state.player = null; state.lastProgressSave = 0 } }

	async function renderSettings() {
		const values = await request('api/settings/personal'); const root = document.createDocumentFragment(); root.append(pageHeader(t('Settings'))); const panel = el('section', 'lucarne-panel'); panel.append(el('h2', '', t('Playback and collection')), el('p', '', t('Defaults inherited by channels, playlists and videos.'))); const form = settingsForm({ mode: values.default_mode, quality: values.default_quality, audio_quality: values.default_audio_quality }, false, false); form.fields.mode.input.querySelector('option[value=""]')?.remove(); form.fields.quality.input.querySelector('option[value=""]')?.remove(); form.fields.audio_quality.input.querySelector('option[value=""]')?.remove(); const historyLimit = field(t('History limit'), 'number', values.history_limit); historyLimit.input.min = 0; historyLimit.input.max = 100000; historyLimit.input.required = true; historyLimit.wrapper.append(el('small', 'lucarne-settings-help', t('Use 0 for no limit. Channel and playlist settings take priority.'))); panel.append(form.body, historyLimit.wrapper, button(t('Save'), null, 'filled', async () => { try { await request('api/settings/personal', { method: 'PUT', body: JSON.stringify({ default_mode: form.fields.mode.input.value, default_quality: form.fields.quality.input.value, default_audio_quality: form.fields.audio_quality.input.value, history_limit: Number(historyLimit.input.value) }) }); state.bootstrap.personal_settings = await request('api/settings/personal'); notify(t('Settings saved')) } catch (error) { notify(error.message, true) } })); root.append(panel); mount(root)
	}

	async function renderCatalogues() {
		const root = document.createDocumentFragment(); root.append(pageHeader(t('Catalogues')), await catalogManager()); mount(root)
	}

	async function catalogManager() {
		const panel = el('section', 'lucarne-panel')
		panel.append(el('h2', '', t('Channel catalogues')), el('p', '', t('Group subscriptions and browse their videos from the navigation.')))
		let catalogs = await request('api/catalogs')
		let activeId = ''
		let original = []
		const toolbar = el('div', 'lucarne-page-actions'); toolbar.style.justifyContent = 'stretch'
		const select = el('select', 'lucarne-select'); select.style.flex = '1'
		const transfer = el('div', 'lucarne-transfer')
		const available = el('select', 'lucarne-select'); available.multiple = true
		const assigned = el('select', 'lucarne-select'); assigned.multiple = true
		const availableField = el('div', 'lucarne-field'); availableField.append(el('label', '', t('Available channels')), available)
		const assignedField = el('div', 'lucarne-field'); assignedField.append(el('label', '', t('Catalogue channels')), assigned)
		const controls = el('div', 'lucarne-transfer__buttons')
		controls.append(iconButton('right', t('Add'), () => moveSelected(available, assigned)), iconButton('left', t('Remove'), () => moveSelected(assigned, available)))
		transfer.append(availableField, controls, assignedField)
		const actions = el('div', 'lucarne-page-actions'); actions.style.marginTop = '16px'

		function fill(preferred = activeId) {
			select.replaceChildren()
			catalogs.forEach(item => { const option = el('option', '', item.name); option.value = item.id; select.append(option) })
			select.value = catalogs.some(item => String(item.id) === String(preferred)) ? String(preferred) : String(catalogs[0]?.id || '')
			activeId = select.value
		}
		function updateVisibility() { transfer.hidden = actions.hidden = catalogs.length === 0 }
		function selectedIds() { return [...assigned.options].map(option => Number(option.value)).sort((a, b) => a - b) }
		function isDirty() { return JSON.stringify(selectedIds()) !== JSON.stringify([...original].sort((a, b) => a - b)) }
		async function confirmDiscard() {
			return !isDirty() || modal({ title: t('Discard changes'), body: t('Discard the unsaved catalogue changes?'), submit: t('Yes'), cancel: t('No'), danger: true })
		}
		async function loadLists(catalogId = select.value) {
			const current = catalogs.find(item => String(item.id) === String(catalogId))
			if (!current) { original = []; available.replaceChildren(); assigned.replaceChildren(); updateVisibility(); return }
			select.value = String(current.id); activeId = select.value
			const [channels, details] = await Promise.all([request('api/channels'), request(`api/catalogs/${current.id}`)])
			original = (details.channel_ids || []).map(Number)
			available.replaceChildren(); assigned.replaceChildren()
			channels.forEach(channel => { const option = el('option', '', channel.title); option.value = channel.id; (original.includes(channel.id) ? assigned : available).append(option) })
			updateVisibility()
		}

		const add = button(t('Add'), 'add', 'tonal', async () => {
			if (!await confirmDiscard()) return
			const name = field(t('Name'))
			if (!await modal({ title: t('Add a catalogue'), body: name.wrapper, submit: t('Create') })) return
			try {
				const item = await request('api/catalogs', { method: 'POST', body: JSON.stringify({ name: name.input.value }) })
				catalogs.push(item); catalogs.sort((a, b) => a.name.localeCompare(b.name)); fill(item.id)
				state.bootstrap.catalogs = catalogs; drawNavigation(); await loadLists(item.id)
			} catch (error) { notify(error.message, true) }
		})
		const edit = button(t('Edit'), 'settings', 'tonal', async () => {
			const current = catalogs.find(item => String(item.id) === select.value); if (!current) return
			const name = field(t('Name'), 'text', current.name)
			if (!await modal({ title: t('Edit catalogue'), body: name.wrapper })) return
			try {
				const item = await request(`api/catalogs/${current.id}`, { method: 'PUT', body: JSON.stringify({ name: name.input.value }) })
				Object.assign(current, item); catalogs.sort((a, b) => a.name.localeCompare(b.name)); fill(item.id)
				state.bootstrap.catalogs = catalogs; drawNavigation()
			} catch (error) { notify(error.message, true) }
		})
		const remove = button(t('Delete'), 'delete', 'danger', async () => {
			const current = catalogs.find(item => String(item.id) === select.value)
			if (!current || !await modal({ title: t('Delete catalogue'), body: t('The catalogue will be deleted. Channels and videos will remain.'), submit: t('Yes'), cancel: t('No'), danger: true })) return
			try {
				await request(`api/catalogs/${current.id}`, { method: 'DELETE' }); catalogs = catalogs.filter(item => item.id !== current.id); fill()
				state.bootstrap.catalogs = catalogs; drawNavigation(); await loadLists()
			} catch (error) { notify(error.message, true) }
		})
		toolbar.append(select, add, edit, remove); panel.append(toolbar, transfer)
		select.addEventListener('change', async () => {
			const requested = select.value; select.value = activeId
			if (await confirmDiscard()) await loadLists(requested)
		})
		actions.append(button(t('Cancel'), null, 'text', () => loadLists(activeId)), button(t('Save'), null, 'filled', async () => {
			const current = catalogs.find(item => String(item.id) === activeId); if (!current) return
			try {
				await request(`api/catalogs/${current.id}/channels`, { method: 'PUT', body: JSON.stringify({ channel_ids: selectedIds() }) })
				notify(t('Catalogue saved')); await loadLists(activeId)
			} catch (error) { notify(error.message, true) }
		}))
		panel.append(actions); fill(); updateVisibility(); if (catalogs.length) await loadLists()
		return panel
	}
	function moveSelected(from, to) { [...from.selectedOptions].forEach(option => to.append(option)); [...to.options].sort((a, b) => a.text.localeCompare(b.text)).forEach(option => to.append(option)) }

	async function renderAdmin() {
		const root = document.createDocumentFragment(); root.append(pageHeader(t('Administration'))); const settingsValues = await request('api/admin/settings'); const panel = el('section', 'lucarne-panel'); panel.append(el('h2', '', t('Collection agent')), el('p', '', t('Control the pace of automatic YouTube requests and temporary media retention.'))); const fields = { batch_size: field(t('Videos per batch'), 'number', settingsValues.batch_size), lot_wait_seconds: selectField(t('Delay between batches'), [['60', t('1 minute')], ['120', t('2 minutes')], ['300', t('5 minutes')], ['600', t('10 minutes')], ['900', t('15 minutes')], ['1800', t('30 minutes')], ['3600', t('1 hour')]], settingsValues.lot_wait_seconds), campaign_duration_seconds: selectField(t('Maximum campaign time'), [['1800', t('30 minutes')], ['3600', t('1 hour')], ['7200', t('2 hours')], ['14400', t('4 hours')], ['28800', t('8 hours')], ['43200', t('12 hours')]], settingsValues.campaign_duration_seconds), temporary_retention_days: field(t('Temporary media retention (days)'), 'number', settingsValues.temporary_retention_days) }; fields.batch_size.input.min = 5; fields.batch_size.input.max = 50; fields.batch_size.input.required = true; fields.batch_size.wrapper.append(el('small', 'lucarne-settings-help', t('Large batches increase the risk of temporary YouTube rate limits.'))); fields.temporary_retention_days.input.min = 1; fields.temporary_retention_days.input.max = 365; fields.temporary_retention_days.input.required = true; fields.temporary_retention_days.wrapper.append(el('small', 'lucarne-settings-help', t('The duration restarts after each playback. Quality variants remain separate.'))); const grid = el('div', 'lucarne-form-grid'); Object.values(fields).forEach(item => grid.append(item.wrapper)); panel.append(grid, button(t('Save'), null, 'filled', async () => { try { await request('api/admin/settings', { method: 'PUT', body: JSON.stringify(Object.fromEntries(Object.entries(fields).map(([key, item]) => [key, Number(item.input.value)]))) }); notify(t('Settings saved')) } catch (error) { notify(error.message, true) } })); root.append(panel); mount(root)
	}

	async function renderSupervision() {
		const root = document.createDocumentFragment(); root.append(pageHeader(t('Supervision'))); const agentPanel = el('section', 'lucarne-panel'); agentPanel.dataset.agent = 'true'; root.append(agentPanel); mount(root); await refreshAgent(); clearInterval(state.timer); state.timer = setInterval(refreshAgent, 1000)
	}

	async function refreshAgent() {
		const panel = document.querySelector('[data-agent]'); if (!panel) return
		try {
			const data = await request('api/agent'); const seconds = Math.max(0, Number(data.campaign.next_lot_at) - Number(data.server_time)); const running = data.jobs.find(job => job.status === 'running'); const queued = data.jobs.filter(job => job.status === 'queued'); const next = queued[0]
			panel.replaceChildren(el('h2', '', t('Agent')), el('p', '', t('Real-time campaign and batch supervision.')))
			const summary = el('div', 'lucarne-agent-summary'); const timer = el('div', 'lucarne-stat'); timer.append(el('span', '', running ? t('Current batch') : t('Next batch in')), el('strong', '', running ? t('In progress') : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`)); const phase = el('div', 'lucarne-stat'); const nextPresentation = (running || next)?.presentation; phase.append(el('span', '', running ? t('Current operation') : t('Next operation')), el('strong', '', nextPresentation ? presentationText(nextPresentation.title, nextPresentation.variables) : technicalLabel(`phase.${data.campaign.phase || 'discover'}`))); summary.append(timer, phase); panel.append(summary)
			if (!data.jobs.length) panel.append(el('p', '', t('No queued batches.')))
			data.jobs.forEach(job => {
				const row = el('div', 'lucarne-job'); const copy = el('div', 'lucarne-job__copy'); const presentation = job.presentation || {}; copy.append(el('strong', '', presentation.title ? presentationText(presentation.title, presentation.variables) : technicalLabel(`job.${job.type}`)), el('span', '', `${technicalLabel(`status.${job.status}`)} · ${job.manual ? t('User request') : t('Automatic')}`)); if (presentation.summary) copy.append(el('small', 'lucarne-job__summary', presentationText(presentation.summary))); if (presentation.details?.length) { const details = el('details', 'lucarne-job__details'); details.append(el('summary', '', t('Show details ({count})', { count: presentation.details.length }))); const list = el('ul'); presentation.details.forEach(value => list.append(el('li', '', presentationText(value)))); details.append(list); copy.append(details) } if (job.error) copy.append(el('small', 'lucarne-job__error', job.error)); row.append(copy)
				if (job.status === 'queued') { const queuedIndex = queued.findIndex(item => item.id === job.id); const up = iconButton('up', t('Move up'), () => alterJob(job.id, 'move', { direction: 'up' })); const down = iconButton('down', t('Move down'), () => alterJob(job.id, 'move', { direction: 'down' })); up.disabled = queuedIndex === 0; down.disabled = queuedIndex === queued.length - 1; row.append(up, down) }
				if (job.status === 'error') row.append(button(t('Retry'), 'refresh', 'text', () => alterJob(job.id, 'retry'))); if (job.status !== 'running') row.append(iconButton('delete', t('Delete'), () => alterJob(job.id, 'delete'))); panel.append(row)
			})
			;(data.future_steps || []).forEach(step => { const row = el('div', 'lucarne-job lucarne-job--future'); const copy = el('div', 'lucarne-job__copy'); copy.append(el('strong', '', t(step.title)), el('span', '', t('Future step')), el('small', 'lucarne-job__summary', t(step.summary))); row.append(copy); panel.append(row) })
		} catch (error) { panel.replaceChildren(el('p', '', error.message)) }
	}
	async function alterJob(id, action, body = null) { try { if (action === 'delete') await request(`api/agent/jobs/${id}`, { method: 'DELETE' }); else await request(`api/agent/jobs/${id}/${action}`, { method: 'POST', body: JSON.stringify(body || {}) }); await refreshAgent() } catch (error) { notify(error.message, true) } }

	async function addChannelDialog() { const url = field(t('YouTube channel URL'), 'url'); if (await modal({ title: t('Add a subscription'), body: url.wrapper, submit: t('Add') })) { try { await request('api/channels', { method: 'POST', body: JSON.stringify({ url: url.input.value }) }); notify(t('Subscription queued')); await navigate('subscriptions') } catch (error) { notify(error.message, true) } } }
	async function addVideoDialog() { const url = field(t('YouTube video URL'), 'url'); if (await modal({ title: t('Add a video'), body: url.wrapper, submit: t('Add') })) { try { await request('api/videos', { method: 'POST', body: JSON.stringify({ url: url.input.value }) }); notify(t('Video queued')); await navigate('home') } catch (error) { notify(error.message, true) } } }
	async function addPlaylistDialog() { const box = el('div'); const mode = selectField(t('Type'), [['personal', t('Personal playlist')], ['youtube', t('YouTube playlist')]], 'personal'); const value = field(t('Name'), 'text'); const help = el('p', 'lucarne-settings-help', t('Playlist history is collected progressively and follows your personal history limit.')); help.hidden = true; box.append(mode.wrapper, value.wrapper, help); mode.input.addEventListener('change', () => { const imported = mode.input.value === 'youtube'; value.wrapper.querySelector('label').textContent = imported ? t('YouTube playlist URL') : t('Name'); value.input.type = imported ? 'url' : 'text'; help.hidden = !imported }); if (await modal({ title: t('Add a playlist'), body: box, submit: t('Add') })) { try { if (mode.input.value === 'youtube') await request('api/playlists/import', { method: 'POST', body: JSON.stringify({ url: value.input.value }) }); else await request('api/playlists', { method: 'POST', body: JSON.stringify({ title: value.input.value }) }); notify(t('Playlist added')); await navigate('playlists') } catch (error) { notify(error.message, true) } } }
	async function addPlaylistVideoDialog(playlist) { const url = field(t('YouTube video URL'), 'url'); if (await modal({ title: t('Add a video'), body: url.wrapper, submit: t('Add') })) { try { await request(`api/playlists/${playlist.id}/videos`, { method: 'POST', body: JSON.stringify({ url: url.input.value }) }); notify(t('Video queued')); await renderPlaylist() } catch (error) { notify(error.message, true) } } }
	async function playbackDialog(item, type) { const personal = state.bootstrap.personal_settings; const inherited = item.inherited || { mode: personal.default_mode, quality: personal.default_quality, audio_quality: personal.default_audio_quality }; const includeHistory = type === 'channel' || (type === 'playlist' && item.kind === 'youtube'); const form = settingsForm({ ...item, inheritedMode: inherited.mode === 'audio' ? t('Audio only') : t('Video'), inheritedQuality: inherited.quality === 'best' ? t('Best available') : `${inherited.quality}p`, inheritedAudio: inherited.audio_quality, inheritedHistoryLabel: personal.history_limit ? String(personal.history_limit) : t('Unlimited') }, type === 'playlist' && item.kind !== 'youtube', includeHistory); if (!await modal({ title: t('Settings'), body: form.body })) return; try { const values = form.values(); const path = type === 'channel' ? `api/channels/${item.id}` : type === 'playlist' ? `api/playlists/${item.id}` : `api/videos/${item.id}`; await request(path, { method: 'PUT', body: JSON.stringify(values) }); notify(t('Settings saved')); await render() } catch (error) { notify(error.message, true) } }
	async function subscribeChannel(channel) { if (!await modal({ title: t('Subscribe to {name}?', { name: channel.title }), body: t('The subscription will be added to the next batch.'), submit: t('Subscribe') })) return; try { await request('api/channels', { method: 'POST', body: JSON.stringify({ url: channel.source_url }) }); notify(t('Subscription queued')); await navigate('subscriptions') } catch (error) { notify(error.message, true) } }
	async function deleteEntity(type, item) { const box = el('div'); const check = el('input'); check.type = 'checkbox'; const label = el('label', 'lucarne-switch'); label.append(check, el('span', '', t('Also delete associated videos'))); box.append(el('p', '', type === 'channel' ? t('The subscription will be removed.') : t('The playlist will be removed.')), label); if (!await modal({ title: type === 'channel' ? t('Unsubscribe') : t('Delete playlist'), body: box, submit: t('Delete'), danger: true })) return; try { await request(`api/${type === 'channel' ? 'channels' : 'playlists'}/${item.id}`, { method: 'DELETE', body: JSON.stringify({ delete_videos: check.checked }) }); notify(t('Deletion queued')); await navigate(type === 'channel' ? 'subscriptions' : 'playlists') } catch (error) { notify(error.message, true) } }
	async function deleteVideo(video) { if (!await modal({ title: t('Delete video'), body: t('The video and its local media will be deleted.'), submit: t('Delete'), danger: true })) return; try { await request(`api/videos/${video.id}`, { method: 'DELETE' }); notify(t('Deletion queued')); await navigate('home') } catch (error) { notify(error.message, true) } }
	async function removePlaylistVideo(playlist, video) { if (!await modal({ title: t('Remove video'), body: t('Remove this video from the playlist?'), submit: t('Remove'), danger: true })) return; try { await request(`api/playlists/${playlist.id}/videos/${video.id}`, { method: 'DELETE' }); await renderPlaylist() } catch (error) { notify(error.message, true) } }
	async function clearHistory() { if (!await modal({ title: t('Clear history'), body: t('All playback positions will be removed.'), submit: t('Clear'), danger: true })) return; try { await request('api/history', { method: 'DELETE' }); await renderHistory() } catch (error) { notify(error.message, true) } }

	async function render() { clearInterval(state.timer); state.timer = null; switch (state.view) { case 'home': return renderHome(); case 'catalog': { const catalog = state.bootstrap.catalogs.find(item => Number(item.id) === Number(state.params.id)); return renderHome({ title: catalog?.name || t('Catalogue'), query: { catalog_id: state.params.id } }) } case 'uncategorized': return renderHome({ title: t('Uncatalogued'), query: { uncategorized: true } }); case 'subscriptions': return renderSubscriptions(); case 'playlists': return renderPlaylists(); case 'channel': return renderChannel(); case 'playlist': return renderPlaylist(); case 'video': return renderVideo(); case 'history': return renderHistory(); case 'settings': return renderSettings(); case 'catalogues': return renderCatalogues(); case 'admin': return state.bootstrap?.is_admin ? renderAdmin() : renderHome(); case 'supervision': return state.bootstrap?.is_admin ? renderSupervision() : renderHome(); default: return renderHome() } }

	async function initialise() {
		const content = document.getElementById('content'); if (!content) return
		content.replaceChildren(); const app = el('div', 'lucarne-app'); const scrim = el('button', 'lucarne-scrim'); scrim.type = 'button'; scrim.hidden = true; scrim.setAttribute('aria-label', t('Close navigation')); scrim.addEventListener('click', closeNavigation); app.append(el('nav', 'lucarne-navigation'), scrim, el('main', 'lucarne-main')); content.append(app); document.querySelector('.lucarne-main').append(loading())
		try { state.bootstrap = await request('api/bootstrap'); scrim.setAttribute('aria-label', t('Close navigation')); const route = decodeRoute(); state.view = route.view; state.params = route.params; drawNavigation(); await render() } catch (error) { mount(empty(t('Unable to start Lucarne'), error.message)) }
		window.addEventListener('popstate', event => { const route = event.state || decodeRoute(); navigate(route.view || 'home', route.params || {}, false) })
		window.addEventListener('beforeunload', () => saveProgress(true))
	}

	initialise()
})()
