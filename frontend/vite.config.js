import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// AppAPI loads the interface as a classic script, so the whole application is
// bundled into one file: `static/js/lucarne-main.js`, with its stylesheet in
// `static/css/lucarne.css`.
const staticDirectory = process.env.LUCARNE_STATIC_DIR
	? fileURLToPath(new URL(`file://${process.env.LUCARNE_STATIC_DIR}/`))
	: fileURLToPath(new URL('../static/', import.meta.url))

// `@nextcloud/dialogs` lazily loads its file, conflict and public-auth pickers.
// Lucarne only uses its toasts, and a classic script cannot load extra chunks.
const skipUnusedDialogs = {
	name: 'lucarne-skip-unused-dialogs',
	load(id) {
		if (/@nextcloud[\/]dialogs[\/]dist[\/]chunks[\/](ConflictPicker|FilePicker|PublicAuthPrompt)\.mjs/.test(id)) {
			return 'export default {}'
		}
		return null
	},
}

export default defineConfig({
	plugins: [skipUnusedDialogs, vue()],
	define: {
		'process.env.NODE_ENV': JSON.stringify('production'),
		// Globals expected by @nextcloud/vue (set by the Nextcloud webpack/vite configs).
		appName: JSON.stringify('lucarne'),
		appVersion: JSON.stringify(process.env.npm_package_version || '1.3.0'),
		__VUE_OPTIONS_API__: 'true',
		__VUE_PROD_DEVTOOLS__: 'false',
		__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
	},
	build: {
		outDir: staticDirectory,
		emptyOutDir: false,
		cssCodeSplit: false,
		sourcemap: false,
		rolldownOptions: {
			input: fileURLToPath(new URL(process.env.LUCARNE_ENTRY || './src/main.js', import.meta.url)),
			output: {
				format: 'iife',
				name: 'Lucarne',
				codeSplitting: false,
				entryFileNames: 'js/lucarne-main.js',
				assetFileNames: 'css/lucarne[extname]',
			},
		},
	},
})
