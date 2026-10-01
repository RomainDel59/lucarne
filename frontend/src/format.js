import { getCanonicalLocale } from '@nextcloud/l10n'
import { t } from './i18n.js'

export function formatDate(timestamp) {
	if (!timestamp) {
		return t('Unknown date')
	}
	return new Intl.DateTimeFormat(getCanonicalLocale(), { dateStyle: 'medium' }).format(new Date(timestamp * 1000))
}

export function formatDuration(value) {
	const seconds = Math.max(0, Math.floor(Number(value || 0)))
	const hours = Math.floor(seconds / 3600)
	const pad = (number) => String(number).padStart(2, '0')
	const minutes = Math.floor((seconds % 3600) / 60)
	return hours ? `${hours}:${pad(minutes)}:${pad(seconds % 60)}` : `${minutes}:${pad(seconds % 60)}`
}

export function entityTitle(item, type) {
	return type === 'playlist' && String(item.external_id || '').startsWith('pending_') ? t('Pending playlist') : item.title
}

export function countdown(seconds) {
	return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}
