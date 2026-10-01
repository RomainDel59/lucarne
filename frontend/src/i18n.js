import { getLanguage } from '@nextcloud/l10n'
import { reactive } from 'vue'

export const i18n = reactive({ translations: {}, language: 'en' })

/**
 * The language of the user's Nextcloud profile, as an HTTP language tag.
 */
export function nextcloudLanguage() {
	return getLanguage().replaceAll('_', '-')
}

export function t(key, variables = {}) {
	let value = i18n.translations[key] || key
	for (const [name, replacement] of Object.entries(variables)) {
		value = value.replaceAll(`{${name}}`, String(replacement))
	}
	return value
}
