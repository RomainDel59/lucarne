import { generateUrl } from '@nextcloud/router'
import { t } from './i18n.js'

const PROXY_ROOT = '/apps/app_api/proxy/lucarne/'

export function apiUrl(path) {
	return generateUrl(PROXY_ROOT + path.replace(/^\//, ''))
}

export async function request(path, options = {}) {
	const { headers, ...rest } = options
	const response = await fetch(apiUrl(path), {
		credentials: 'same-origin',
		headers: { 'Content-Type': 'application/json', ...(headers || {}) },
		...rest,
	})
	const body = response.status === 204 ? null : await response.json().catch(() => ({}))
	if (!response.ok) {
		throw new Error(body?.error || body?.detail || `${t('Request failed')} (${response.status})`)
	}
	return body
}

export function send(method, path, payload) {
	return request(path, { method, body: payload === undefined ? undefined : JSON.stringify(payload) })
}
