<script setup lang="ts">
import { usePage, router } from '@inertiajs/vue3';

import Layout from '@/components/Layout.vue';
import type { DjangoFormData } from "@/types/djangoForm";
import type { Documento } from '@/types/index';
import { ref, watch } from 'vue';

const documentoParaExcluir = ref<Documento | null>(null);
const modalExclusao = ref<HTMLDialogElement | null>(null);
const modalImportacao = ref<HTMLDialogElement | null>(null);
const inputDocumentos = ref<HTMLInputElement | null>(null);

function abrirModalExclusao(documento: Documento) {
    documentoParaExcluir.value = documento;
    modalExclusao.value?.showModal();
}

function confirmarExclusao() {
    if (documentoParaExcluir.value) {
        const url = page.props['urls']['excluir_documento'].replace('%(id_documento)s', documentoParaExcluir.value.id.toString());
        router.post(url);
    }
    modalExclusao.value?.close();
    documentoParaExcluir.value = null;
}

function cancelarExclusao() {
    modalExclusao.value?.close();
    documentoParaExcluir.value = null;
}

function abrirModalImportacao() {
    modalImportacao.value?.showModal();
}

function fecharModalImportacao() {
    modalImportacao.value?.close();
    documentosParaImportar.value = [];
    if (inputDocumentos.value) inputDocumentos.value.value = '';
}


const page = usePage<{
    urls: Record<string, string>,
}>();
const props = defineProps<{
    importar_documentos_form: DjangoFormData,
    documentos: Documento[];
    documentos_processados: number;
    documentos_pendentes: number;
}>();

const documentos = ref([...props.documentos]);
const qtdDocumentosProcessados = ref(props.documentos_processados);
const qtdDocumentosPendentes = ref(props.documentos_pendentes);

watch(
    () => ({
        docs: props.documentos,
        proc: props.documentos_processados,
        pend: props.documentos_pendentes
    }),
    (v) => {
        documentos.value = [...v.docs];
        qtdDocumentosProcessados.value = v.proc;
        qtdDocumentosPendentes.value = v.pend;
        atualizarStatusDocumentosPendentes();
    }
);

let verificando = false;
async function atualizarStatusDocumentosPendentes() {
    if (verificando) return;
    verificando = true;

    while (true) {
        const pendentes = documentos.value.filter(
            d => d.status === "pendente" || d.status === "processando"
        );
        if (pendentes.length === 0) break;

        await new Promise(r => setTimeout(r, 5000));

        await Promise.all(
            pendentes.map(async doc => {
                try {
                    const res = await fetch(`/api/documentos/${doc.id}/status`);
                    if (!res.ok) return;
                    const data = await res.json();
                    doc.status = data.status;
                } catch (e) {
                    console.error(e);
                }
            })
        );

        qtdDocumentosProcessados.value = documentos.value.filter(d => d.status === 'processado').length;
        qtdDocumentosPendentes.value = documentos.value.filter(d => d.status === 'pendente').length;
    }

    verificando = false;
}

atualizarStatusDocumentosPendentes();

type DocumentoParaImportar = {
    arquivo: File;
    tipo: 'manual' | 'legislacao';
};

const documentosParaImportar = ref<DocumentoParaImportar[]>([]);

function removerDocumento(index: number) {
    documentosParaImportar.value.splice(index, 1);
}

function selecionarDocumentos(event: Event) {
    const target = event.target as HTMLInputElement;
    for (const arquivo of Array.from(target.files ?? [])) {
        documentosParaImportar.value.push({ arquivo, tipo: 'manual' });
    }
    target.value = '';
}

function submit() {
    if (!documentosParaImportar.value.length) return;
    const formData = new FormData();

    documentosParaImportar.value.forEach((doc, index) => {
        formData.append(`documentos[${index}]`, doc.arquivo);
        formData.append(`tipos[${index}]`, doc.tipo);
    });

    router.post(page.props['urls']['documentos'], formData, {
        onSuccess: () => {
            fecharModalImportacao();
        }
    });
}

async function atualizarTipoDocumento(documento: Documento, novoTipo: string) {
    try {
        const res = await fetch(`/api/documentos/${documento.id}/tipo`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ tipo: novoTipo })
        });

        if (!res.ok) {
            console.error('Erro ao atualizar tipo de documento');
        }
    } catch (e) {
        console.error(e);
    }
}

</script>

<template>
    <Layout>
        <div class="mx-auto w-full max-w-5xl space-y-4 p-3 sm:p-4">
            <div class="grid grid-cols-1 gap-3 md:grid-cols-3 md:gap-4">
                <div class="rounded-2xl border border-base-content/10 bg-base-300 p-3 flex flex-col items-center justify-center">
                    <p class="label">Documentos processados</p>
                    <p class="font-bold text-2xl">{{ qtdDocumentosProcessados }}</p>
                </div>
                <div class="rounded-2xl border border-base-content/10 bg-base-300 p-3 flex flex-col items-center justify-center">
                    <p class="label">Documentos pendentes</p>
                    <p class="font-bold text-2xl">{{ qtdDocumentosPendentes }}</p>
                </div>
                <div class="rounded-2xl p-2 flex items-center justify-center">
                    <button @click="abrirModalImportacao" class="btn btn-primary btn-block md:btn-wide">
                        <i class="bi bi-plus-lg"></i>
                        Adicionar Documentos
                    </button>
                </div>
            </div>

            <div class="hidden overflow-x-auto rounded-2xl border border-base-content/10 bg-base-100 sm:block">
                <table class="table table-zebra table-auto">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Documento</th>
                            <th>Status</th>
                            <th>Tipo do Documento</th>
                            <th class="w-0 whitespace-nowrap">Ações</th>
                        </tr>
                    </thead>

                    <tbody>
                        <tr v-for="documento in documentos" :key="documento.id">
                            <td>{{ documento.id }}</td>
                            <td>{{ documento.nome }}</td>
                            <td>
                                <span v-if="documento.status === 'erro'" class="badge badge-error text-error-content">
                                    Erro
                                </span>
                                <span v-else-if="documento.status === 'processado'"
                                    class="badge badge-success text-success-content">
                                    Processado
                                </span>
                                <span v-else-if="documento.status === 'processando'"
                                    class="badge badge-warning text-warning-content">
                                    Processando
                                </span>
                                <span v-else class="badge badge-neutral">
                                    Pendente
                                </span>
                            </td>
                            <td>
                                <select v-model="documento.tipo"
                                    @change="atualizarTipoDocumento(documento, documento.tipo)"
                                    class="select select-bordered select-sm w-full max-w-xs">
                                    <option value="manual">Manual</option>
                                    <option value="legislacao">Legislação</option>
                                </select>
                            </td>
                            <td class="w-0 whitespace-nowrap">
                                <div class="flex gap-2 justify-center">
                                    <a :href="documento.arquivo.url" target="_blank">
                                        <i class="bi bi-eye-fill text-neutral"></i>
                                    </a>
                                    <button @click="abrirModalExclusao(documento)" class="cursor-pointer">
                                        <i class="bi bi-trash3-fill text-error"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="space-y-2 sm:hidden">
                <article v-for="documento in documentos" :key="documento.id"
                    class="rounded-2xl border border-base-content/10 bg-base-100 p-3 shadow-sm">
                    <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0">
                            <p class="text-xs opacity-70">ID {{ documento.id }}</p>
                            <p class="truncate font-medium">{{ documento.nome }}</p>
                        </div>
                        <div class="flex gap-2">
                            <a :href="documento.arquivo.url" target="_blank" aria-label="Visualizar documento">
                                <i class="bi bi-eye-fill text-neutral"></i>
                            </a>
                            <button @click="abrirModalExclusao(documento)" class="cursor-pointer"
                                aria-label="Excluir documento">
                                <i class="bi bi-trash3-fill text-error"></i>
                            </button>
                        </div>
                    </div>
                    <div class="mt-3 flex items-center justify-between gap-2">
                        <div>
                            <span v-if="documento.status === 'erro'" class="badge badge-error text-error-content">
                                Erro
                            </span>
                            <span v-else-if="documento.status === 'processado'" class="badge badge-success text-success-content">
                                Processado
                            </span>
                            <span v-else-if="documento.status === 'processando'" class="badge badge-warning text-warning-content">
                                Processando
                            </span>
                            <span v-else class="badge badge-neutral">
                                Pendente
                            </span>
                        </div>
                        <select v-model="documento.tipo" @change="atualizarTipoDocumento(documento, documento.tipo)"
                            class="select select-bordered select-xs w-36">
                            <option value="manual">Manual</option>
                            <option value="legislacao">Legislação</option>
                        </select>
                    </div>
                </article>
            </div>

            <!-- Modal de importação -->
            <dialog ref="modalImportacao" class="modal">
                <div class="modal-box max-w-2xl">
                    <h3 class="font-bold text-lg mb-4">Adicionar Documentos</h3>

                    <p class="mb-3 text-sm opacity-70">Selecione vários PDFs de uma vez. Você pode adicionar mais arquivos antes de enviar.</p>
                    <input ref="inputDocumentos" type="file" accept=".pdf" multiple @change="selecionarDocumentos"
                        aria-label="Selecionar documentos PDF"
                        class="file-input file-input-bordered file-input-sm w-full mb-4" />

                    <div v-if="documentosParaImportar.length" class="space-y-3 max-h-96 overflow-y-auto bg-base-200 rounded p-3">
                        <div v-for="(doc, index) in documentosParaImportar" :key="index"
                            class="flex gap-2 items-center">
                            <div class="min-w-0 flex-1">
                                <p class="break-words text-sm">{{ doc.arquivo.name }}</p>
                            </div>
                            <div class="w-40">
                                <select v-model="doc.tipo" :aria-label="`Tipo de ${doc.arquivo.name}`" class="select select-bordered select-sm w-full">
                                    <option value="manual">Manual</option>
                                    <option value="legislacao">Legislação</option>
                                </select>
                            </div>
                            <button @click="removerDocumento(index)" :aria-label="`Remover ${doc.arquivo.name}`"
                                class="btn btn-sm btn-ghost btn-circle">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>

                    <div class="modal-action">
                        <button class="btn" @click="fecharModalImportacao">Cancelar</button>
                        <button class="btn btn-primary" :disabled="!documentosParaImportar.length" @click="submit">Enviar</button>
                    </div>
                </div>
                <form method="dialog" class="modal-backdrop">
                    <button @click="fecharModalImportacao">close</button>
                </form>
            </dialog>

            <!-- Modal de confirmação de exclusão -->
            <dialog ref="modalExclusao" class="modal">
                <div class="modal-box">
                    <h3 class="font-bold text-lg">Confirmar exclusão</h3>
                    <p class="py-4">
                        Tem certeza que deseja excluir o documento
                        <strong>{{ documentoParaExcluir?.nome }}</strong>?
                    </p>
                    <div class="modal-action">
                        <button class="btn" @click="cancelarExclusao">Cancelar</button>
                        <button class="btn btn-error" @click="confirmarExclusao">Excluir</button>
                    </div>
                </div>
                <form method="dialog" class="modal-backdrop">
                    <button @click="cancelarExclusao">close</button>
                </form>
            </dialog>
        </div>
    </Layout>
</template>
