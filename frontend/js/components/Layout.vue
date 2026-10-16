<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { Link, usePage, router } from '@inertiajs/vue3';
import IntegracarLogo from './IntegracarLogo.vue';
import { Conversa, Usuario } from '@/types/index';

const page = usePage<{
    urls: Record<string, string>,
    user: Usuario,
    conversas: Conversa[],
}>();

const pathname = computed(() => page.url.replace(/\/+$/, '') || '/');

const isActive = (href: string): boolean => {
    try {
        const url = new URL(href, window.location.origin);
        const hrefPath = url.pathname.replace(/\/+$/, '') || '/';
        return pathname.value === hrefPath;
    } catch (e) {
        return pathname.value === (href.replace(/\/+$/, '') || '/');
    }
};

const buscaConversa = ref('');
const nomesConversas = ref<Record<number, string>>({});
function nomeConversa(conversa: Conversa) {
    return nomesConversas.value[conversa.id] ?? conversa.nome;
}
function normalizar(texto: string) {
    return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
}
const conversasFiltradas = computed(() => (page.props.conversas ?? []).filter(
    conversa => normalizar(nomeConversa(conversa)).includes(normalizar(buscaConversa.value.trim()))
));
const renameModal = ref<HTMLDialogElement | null>(null);
const renameInput = ref<HTMLInputElement | null>(null);
const conversaParaRenomear = ref<Conversa | null>(null);
const novoNome = ref('');
const erroRenomear = ref('');
const salvandoNome = ref(false);

function abrirRenomear(conversa: Conversa) {
    conversaParaRenomear.value = conversa;
    novoNome.value = nomeConversa(conversa);
    erroRenomear.value = '';
    renameModal.value?.showModal();
    setTimeout(() => renameInput.value?.select(), 0);
}

async function salvarNome() {
    if (!conversaParaRenomear.value || !novoNome.value.trim() || salvandoNome.value) return;
    salvandoNome.value = true;
    erroRenomear.value = '';
    try {
        const response = await fetch(`/api/conversas/${conversaParaRenomear.value.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nome: novoNome.value.trim() }),
        });
        if (!response.ok) throw new Error('Falha ao salvar');
        const conversa = await response.json();
        nomesConversas.value[conversa.id] = conversa.nome;
        renameModal.value?.close();
    } catch {
        erroRenomear.value = 'Não foi possível salvar o nome. Tente novamente.';
    } finally {
        salvandoNome.value = false;
    }
}

const deleteModal = ref<HTMLDialogElement | null>(null);
const conversaParaExcluir = ref<Conversa | null>(null);
const sidebarToggle = ref<HTMLInputElement | null>(null);
const deleteConfirmButton = ref<HTMLButtonElement | null>(null);
let mediaQuery: MediaQueryList | null = null;
let mediaQueryHandler: ((event: MediaQueryListEvent) => void) | null = null;

onMounted(() => {
    mediaQuery = window.matchMedia('(min-width: 1024px)');

    const syncSidebarState = (isLargeScreen: boolean) => {
        if (sidebarToggle.value) {
            sidebarToggle.value.checked = isLargeScreen;
        }
    };

    syncSidebarState(mediaQuery.matches);
    mediaQueryHandler = (event: MediaQueryListEvent) => syncSidebarState(event.matches);
    mediaQuery.addEventListener('change', mediaQueryHandler);
});

onUnmounted(() => {
    if (mediaQuery && mediaQueryHandler) {
        mediaQuery.removeEventListener('change', mediaQueryHandler);
    }
});

const abrirModalExcluir = (conversa: Conversa, event: Event) => {
    event.preventDefault();
    event.stopPropagation();
    conversaParaExcluir.value = { ...conversa, nome: nomeConversa(conversa) };
    deleteModal.value?.showModal();
    setTimeout(() => deleteConfirmButton.value?.focus(), 0);
};

const confirmarExclusao = () => {
    if (conversaParaExcluir.value) {
        const url = page.props.urls['excluir_conversa'].replace('%(id_conversa)s', conversaParaExcluir.value.id.toString());
        router.post(url, undefined, { 'preserveState': false, 'replace': true });
        if (isActive('/')) {
            router.visit(page.props.urls['index']);
        }
    }
    deleteModal.value?.close();
    conversaParaExcluir.value = null;
};

const cancelarExclusao = () => {
    deleteModal.value?.close();
    conversaParaExcluir.value = null;
};

function fecharSidebarEmTelaPequena() {
    if (!sidebarToggle.value) return;
    if (window.innerWidth < 1024) {
        sidebarToggle.value.checked = false;
    }
}
</script>

<template>
    <div class="drawer lg:drawer-open">
        <input id="sidebar" ref="sidebarToggle" type="checkbox" class="drawer-toggle" />
        <div class="drawer-content flex h-dvh flex-col overflow-hidden">
            <!-- Navbar -->
            <nav
                class="navbar sticky top-0 z-20 w-full border-b border-base-content/10 bg-linear-to-r/shorter from-neutral to-base-300 text-secondary-content">
                <label for="sidebar" aria-label="Abrir barra lateral" class="btn btn-square btn-ghost">
                    <i class="bi bi-layout-sidebar text-xl"></i>
                </label>
                <div class="px-4">
                    <Link :href="page.props.urls['index']" class="flex items-center gap-2">
                        <IntegracarLogo />
                        Chatbot IntegraCAR
                    </Link>
                </div>
            </nav>

            <!-- Page content here -->
            <div class="grow min-h-0 flex flex-col overflow-y-auto overflow-x-hidden">

                <slot></slot>
            </div>
        </div>

        <div class="drawer-side is-drawer-close:overflow-visible z-50">
            <label for="sidebar" aria-label="Fechar barra lateral" class="drawer-overlay"></label>
            <div
                class="flex h-full min-h-full flex-col overflow-visible border-r border-base-content/20 bg-neutral text-neutral-content is-drawer-close:w-14 is-drawer-open:w-72">
                <ul class="menu w-full shrink-0 gap-1 px-2 pt-2">
                    <div class="h-2"></div>
                    <li>
                        <Link :href="page.props.urls['index']"
                            class="is-drawer-close:tooltip is-drawer-close:tooltip-right rounded-xl border border-transparent px-2 text-nowrap"
                            :class="{ 'bg-accent': isActive(page.props.urls['index']) }" data-tip="Nova Conversa"
                            @click="fecharSidebarEmTelaPequena">
                            <i class="bi bi-pencil-square"></i>
                            <span class="is-drawer-close:hidden">Nova Conversa</span>
                        </Link>
                    </li>
                    <li v-if="page.props.user.is_staff">
                        <Link :href="page.props.urls['documentos']"
                            class="is-drawer-close:tooltip is-drawer-close:tooltip-right rounded-xl border border-transparent px-2 text-nowrap"
                            :class="{ 'bg-accent': isActive(page.props.urls['documentos']) }" data-tip="Documentos"
                            @click="fecharSidebarEmTelaPequena">
                            <i class="bi bi-file-earmark-text"></i>
                            <span class="is-drawer-close:hidden">Documentos</span>
                        </Link>
                    </li>
                    <li v-if="page.props.user.is_staff">
                        <Link :href="page.props.urls['curadoria']"
                            class="is-drawer-close:tooltip is-drawer-close:tooltip-right rounded-xl border border-transparent px-2 text-nowrap"
                            :class="{ 'bg-accent': isActive(page.props.urls['curadoria']) }" data-tip="Curadoria"
                            @click="fecharSidebarEmTelaPequena">
                            <i class="bi bi-robot"></i>
                            <span class="is-drawer-close:hidden">Curadoria</span>
                        </Link>
                    </li>
                </ul>

                <hr class="my-2">
                <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain is-drawer-close:hidden">
                    <div class="px-3 py-2">
                        <label for="buscar-conversas" class="mb-2 block text-xs font-semibold">Histórico de consultas</label>
                        <input id="buscar-conversas" v-model="buscaConversa" type="search"
                            placeholder="Buscar pelo nome…" class="input input-sm w-full bg-neutral text-neutral-content"
                            @keydown.esc="buscaConversa = ''" />
                        <p v-if="buscaConversa" class="mt-2 text-xs" role="status">
                            {{ conversasFiltradas.length }} conversa(s) encontrada(s)
                        </p>
                        <p v-if="!page.props.conversas?.length" class="mt-2 text-xs opacity-70">Suas consultas aparecerão aqui.</p>
                    </div>
                    <ul class="menu w-full gap-1 px-2">
                        <li class="is-drawer-close:hidden" v-for="conversa in conversasFiltradas" :key="conversa.id">
                            <div class="group flex items-center gap-1 p-0">
                            <Link :href="page.props.urls['conversa'].replace('%(id_conversa)s', conversa.id.toString())"
                                class="min-w-0 flex-1 flex items-center justify-between gap-2 rounded-xl border border-transparent px-2 py-1.5 text-nowrap hover:bg-secondary/80 focus-visible:border-base-100/70"
                                :class="{ 'bg-accent': isActive(page.props.urls['conversa'].replace('%(id_conversa)s', conversa.id.toString())) }"
                                @click="fecharSidebarEmTelaPequena">
                                <span class="truncate is-drawer-close:hidden">{{ nomeConversa(conversa) }}</span>
                                <i class="bi bi-chat-left-text is-drawer-open:hidden"></i>
                            </Link>
                            <button type="button" class="btn btn-ghost btn-xs btn-square"
                                :aria-label="`Renomear conversa ${nomeConversa(conversa)}`" title="Renomear conversa"
                                @click="abrirRenomear(conversa)">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button type="button" class="btn btn-ghost btn-xs btn-square"
                                :aria-label="`Excluir conversa ${nomeConversa(conversa)}`" title="Excluir conversa"
                                @click="abrirModalExcluir(conversa, $event)">
                                <i class="bi bi-trash"></i>
                            </button>
                            </div>
                        </li>
                    </ul>
                </div>

                <ul class="menu mt-auto w-full shrink-0">
                    <li>
                        <div class="dropdown dropdown-top p-0 is-drawer-close:tooltip is-drawer-close:tooltip-right"
                            role="button">
                            <div tabindex="0" role="button" class="btn btn-accent text-nowrap rounded-lg p-1 w-full">
                                <i class="bi bi-person-circle"></i>
                                <span class="is-drawer-close:hidden">{{ page.props.user.name }}</span>
                            </div>
                            <ul tabindex="-1"
                                class="dropdown-content menu bg-base-300 text-base-content rounded-box w-60 p-2 shadow-sm ">
                                <li>
                                    <Link :href="page.props.urls['sair']" method="post" @click="fecharSidebarEmTelaPequena">
                                        <i class="bi bi-box-arrow-right text-error"> </i>
                                        Sair
                                    </Link>
                                </li>
                            </ul>
                        </div>
                    </li>
                </ul>

            </div>
        </div>
    </div>

    <dialog ref="renameModal" class="modal" aria-labelledby="renomear-titulo" @cancel="salvandoNome && $event.preventDefault()">
        <form class="modal-box" @submit.prevent="salvarNome">
            <h3 id="renomear-titulo" class="text-lg font-bold">Renomear conversa</h3>
            <label for="nome-conversa" class="mt-4 mb-2 block">Nome da consulta</label>
            <input id="nome-conversa" ref="renameInput" v-model="novoNome" maxlength="50" required
                :disabled="salvandoNome" class="input w-full" />
            <p class="mt-1 text-xs opacity-70">{{ novoNome.length }}/50 caracteres</p>
            <p v-if="erroRenomear" role="alert" class="mt-2 text-error">{{ erroRenomear }}</p>
            <div class="modal-action">
                <button type="button" class="btn" :disabled="salvandoNome" @click="renameModal?.close()">Cancelar</button>
                <button type="submit" class="btn btn-primary" :disabled="!novoNome.trim() || salvandoNome">
                    {{ salvandoNome ? 'Salvando…' : 'Salvar nome' }}
                </button>
            </div>
        </form>
    </dialog>

    <!-- Modal de confirmação de exclusão -->
    <dialog ref="deleteModal" class="modal">
        <div class="modal-box">
            <h3 class="text-lg font-bold">Excluir conversa</h3>
            <p class="py-4">Tem certeza que deseja excluir a conversa "{{ conversaParaExcluir?.nome }}"?</p>
            <div class="modal-action">
                <button class="btn" @click="cancelarExclusao">Cancelar</button>
                <button ref="deleteConfirmButton" class="btn btn-error" @click="confirmarExclusao">Excluir</button>
            </div>
        </div>
        <form method="dialog" class="modal-backdrop">
            <button @click="cancelarExclusao">close</button>
        </form>
    </dialog>
</template>
