import { showError, showSuccess } from '@nextcloud/dialogs'

export function notify(message) {
	showSuccess(message)
}

export function notifyError(error) {
	showError(error instanceof Error ? error.message : String(error))
}
