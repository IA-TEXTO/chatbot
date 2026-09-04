import "vite/modulepreload-polyfill";
import axios from "axios";

import { createInertiaApp } from "@inertiajs/vue3";
import { createApp, h } from "vue";
import Layout from "@/components/Layout.vue";


import "../css/main.css";


const pages = import.meta.glob("./pages/**/*.vue");

document.addEventListener("DOMContentLoaded", () => {
	axios.defaults.xsrfCookieName = "csrftoken";
	axios.defaults.xsrfHeaderName = "X-CSRFToken";

	// inertia-django 1.x serializa a página no atributo data-page do #app,
	// enquanto versões mais novas podem usar um script JSON separado.
	// Aceitar ambos mantém desenvolvimento e produção compatíveis.
	const appElement = document.getElementById("app");
	const pageScript = document.querySelector('script[data-page="app"]');
	const serializedPage = pageScript?.textContent || appElement?.dataset.page;

	if (!serializedPage) {
		throw new Error("Dados iniciais do Inertia não encontrados no HTML.");
	}
	const initialPage = JSON.parse(serializedPage);

	createInertiaApp({
		page: initialPage,
		resolve: async (name) => {
			const path = `./pages/${name}.vue`;
			const resolver = pages[path];

			if (!resolver) {
				throw new Error(
					`Página Inertia não encontrada: ${name}. ` +
					`Páginas disponíveis: ${Object.keys(pages).join(", ")}`,
				);
			}

			const module = typeof resolver === "function"
				? await resolver()
				: resolver;
			const page = module.default;
			// page.layout = page.layout || Layout;
			return page;
		},
		setup({ el, App, props, plugin }) {
			createApp({ render: () => h(App, props) })
				.use(plugin)
				.mount(el);
		},
	});

});
