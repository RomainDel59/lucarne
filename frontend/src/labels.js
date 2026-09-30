import { t } from './i18n.js'

const labels = {
	'phase.discover': () => t('Checking sources'),
	'phase.metadata': () => t('Metadata and thumbnails'),
	'phase.history': () => t('Retrieving history'),
	'phase.history_required': () => t('First historical batch'),
	'job.discover': () => t('Check sources'),
	'job.metadata': () => t('Retrieve metadata and thumbnails'),
	'job.history': () => t('Retrieve history'),
	'job.initialize_channel': () => t('Add a subscription'),
	'job.initialize_playlist': () => t('Import a playlist'),
	'job.inspect_video': () => t('Add a video'),
	'job.sync_source': () => t('Reactivate a subscription'),
	'job.delete_channel': () => t('Delete a subscription'),
	'job.delete_playlist': () => t('Delete a playlist'),
	'job.delete_video': () => t('Delete a video'),
	'status.queued': () => t('Queued'),
	'status.running': () => t('Running'),
	'status.error': () => t('Error'),
}

export function technicalLabel(key) {
	return labels[key]?.() ?? key
}

export function presentationText(value, variables = {}) {
	if (!value) {
		return ''
	}
	if (value.startsWith('Channel · ')) {
		return `${t('Channel')} · ${value.slice(10)}`
	}
	if (value.startsWith('Playlist · ')) {
		return `${t('Playlist')} · ${value.slice(11)}`
	}
	const known = value.match(/^(\d+) known videos · (unlimited|limit (\d+))$/)
	if (known) {
		return t(known[2] === 'unlimited' ? '{count} known videos · unlimited' : '{count} known videos · limit {limit}', { count: known[1], limit: known[3] })
	}
	return t(value, variables)
}
