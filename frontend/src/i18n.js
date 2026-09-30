import { reactive } from 'vue'

export const i18n = reactive({ translations: {}, language: 'en' })

export function t(key, variables = {}) {
	let value = i18n.translations[key] || key
	for (const [name, replacement] of Object.entries(variables)) {
		value = value.replaceAll(`{${name}}`, String(replacement))
	}
	return value
}
