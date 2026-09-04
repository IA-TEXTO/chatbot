import { resolve } from "node:path";

import vue from "@vitejs/plugin-vue";

import { defineConfig, loadEnv } from "vite";

import tailwindcss from '@tailwindcss/vite';


export default defineConfig((mode) => {
	const env = loadEnv(mode, process.cwd(), "");

	const INPUT_DIR = "./frontend";
	const OUTPUT_DIR = "./frontend/dist";

	return {
		plugins: [
			tailwindcss(),
			vue()

		],
		resolve: {
			alias: {
				"@": resolve(INPUT_DIR, "js"),
				"@/types": resolve(INPUT_DIR, "js/types"),
				vue: "vue/dist/vue.esm-bundler.js",
			},
		},
		root: resolve(INPUT_DIR),
		base: "/static/",
		server: {
			host: "0.0.0.0",
			port: env.DJANGO_VITE_DEV_SERVER_PORT || 5173,
			watch: {
				usePolling: true,
			},
		},
		optimizeDeps: {
			entries: ["js/main.js"],
		},
		build: {
			manifest: "manifest.json",
			emptyOutDir: true,
			outDir: resolve(OUTPUT_DIR),
			rollupOptions: {
				input: {
					main: resolve(INPUT_DIR, "js/main.js"),
					css: resolve(INPUT_DIR, "css/main.css"),
				},
			},
		},
	};
});
