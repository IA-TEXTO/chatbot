<script setup lang="ts">
import { usePage, router } from '@inertiajs/vue3';
import { computed, onUnmounted, ref, watch } from 'vue';

import Layout from '@/components/Layout.vue';
import type { Skill } from '@/types/index';

const page = usePage<{
    urls: Record<string, string>,
}>();
const props = defineProps<{
    skills: Skill[];
    erro_importacao: string;
}>();

const skills = ref<Skill[]>([...props.skills]);
const qtdAtivas = computed(() => skills.value.filter(s => s.status === 'ativa').length);
const qtdRascunhos = computed(() => skills.value.filter(s => s.status === 'rascunho').length);

const statusSkill = {
    gerando: { texto: 'Gerando', classe: 'badge-warning text-warning-content' },
    rascunho: { texto: 'Rascunho', classe: 'badge-neutral' },
    ativa: { texto: 'Ativa', classe: 'badge-success text-success-content' },
    erro: { texto: 'Erro', classe: 'badge-error text-error-content' },
};

function atualizarSkill(atualizada: Skill) {
    const indice = skills.value.findIndex(s => s.id === atualizada.id);
    if (indice !== -1) skills.value[indice] = atualizada;
}

async function requisitar(url: string, method = 'GET', body?: object): Promise<Skill> {
    const res = await fetch(url, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
    });
    const dados = await res.json();
    if (!res.ok) throw new Error(dados.detail ?? 'Não foi possível concluir a ação.');
    return dados;
}

// Acompanha a geração em segundo plano até o rascunho ficar pronto.
let temporizador: ReturnType<typeof setTimeout> | null = null;
function acompanharGeracao() {
    if (temporizador) clearTimeout(temporizador);
    const gerando = skills.value.filter(s => s.status === 'gerando');
    if (gerando.length === 0) return;
    temporizador = setTimeout(async () => {
        await Promise.all(gerando.map(async skill => {
            try {
                atualizarSkill(await requisitar(`/api/skills/${skill.id}`));
            } catch (e) {
                console.error(e);
            }
        }));
        acompanharGeracao();
    }, 5000);
}
acompanharGeracao();
onUnmounted(() => temporizador && clearTimeout(temporizador));

watch(() => props.skills, (novas) => {
    skills.value = [...novas];
    acompanharGeracao();
});

// Importação de PDF
const modalImportacao = ref<HTMLDialogElement | null>(null);
const arquivoPdf = ref<File | null>(null);
const enviando = ref(false);

function abrirModalImportacao() {
    arquivoPdf.value = null;
    modalImportacao.value?.showModal();
}

function selecionarPdf(event: Event) {
    arquivoPdf.value = (event.target as HTMLInputElement).files?.[0] ?? null;
}

function enviarPdf() {
    if (!arquivoPdf.value) return;
    const formData = new FormData();
    formData.append('arquivo', arquivoPdf.value);
    enviando.value = true;
    router.post(page.props.urls['skills'], formData, {
        onSuccess: () => modalImportacao.value?.close(),
        onFinish: () => { enviando.value = false; },
    });
}

// Revisão e edição do .md
const modalEdicao = ref<HTMLDialogElement | null>(null);
const skillEmEdicao = ref<Skill | null>(null);
const conteudoEditado = ref('');
const erroEdicao = ref('');
const salvando = ref(false);
const pontosARevisar = computed(() =>
    (skillEmEdicao.value?.observacoes ?? '').split('\n').filter(Boolean)
);

function abrirEdicao(skill: Skill) {
    skillEmEdicao.value = skill;
    conteudoEditado.value = skill.conteudo;
    erroEdicao.value = '';
    modalEdicao.value?.showModal();
}

async function salvarEdicao(ativar: boolean) {
    const skill = skillEmEdicao.value;
    if (!skill) return;
    salvando.value = true;
    erroEdicao.value = '';
    try {
        let atualizada = await requisitar(`/api/skills/${skill.id}`, 'PUT', { conteudo: conteudoEditado.value });
        if (ativar) {
            atualizada = await requisitar(`/api/skills/${skill.id}/status`, 'PATCH', { ativa: true });
        }
        atualizarSkill(atualizada);
        modalEdicao.value?.close();
    } catch (e) {
        erroEdicao.value = (e as Error).message;
    } finally {
        salvando.value = false;
    }
}

const erroAcao = ref('');
async function alternarAtivacao(skill: Skill) {
    erroAcao.value = '';
    try {
        atualizarSkill(await requisitar(`/api/skills/${skill.id}/status`, 'PATCH', { ativa: skill.status !== 'ativa' }));
    } catch (e) {
        erroAcao.value = `${skill.arquivo}: ${(e as Error).message}`;
    }
}

// Exclusão
const modalExclusao = ref<HTMLDialogElement | null>(null);
const skillParaExcluir = ref<Skill | null>(null);

function abrirModalExclusao(skill: Skill) {
    skillParaExcluir.value = skill;
    modalExclusao.value?.showModal();
}

function confirmarExclusao() {
    if (skillParaExcluir.value) {
        const url = page.props.urls['excluir_skill'].replace('%(id_skill)s', skillParaExcluir.value.id.toString());
        router.post(url);
    }
    modalExclusao.value?.close();
    skillParaExcluir.value = null;
}
</script>

<template>
    <Layout>
        <div class="mx-auto w-full max-w-5xl space-y-4 p-3 sm:p-4">
            <div class="grid grid-cols-1 gap-3 md:grid-cols-3 md:gap-4">
                <div class="rounded-2xl border border-base-content/10 bg-base-300 p-3 flex flex-col items-center justify-center">
                    <p class="label">Skills ativas</p>
                    <p class="font-bold text-2xl">{{ qtdAtivas }}</p>
                </div>
                <div class="rounded-2xl border border-base-content/10 bg-base-300 p-3 flex flex-col items-center justify-center">
                    <p class="label">Aguardando revisão</p>
                    <p class="font-bold text-2xl">{{ qtdRascunhos }}</p>
                </div>
                <div class="rounded-2xl p-2 flex items-center justify-center">
                    <button @click="abrirModalImportacao" class="btn btn-primary btn-block md:btn-wide">
                        <i class="bi bi-file-earmark-arrow-up"></i>
                        Criar skill a partir de PDF
                    </button>
                </div>
            </div>

            <div v-if="erro_importacao" role="alert" class="alert alert-error">{{ erro_importacao }}</div>
            <div v-if="erroAcao" role="alert" class="alert alert-error">{{ erroAcao }}</div>

            <p v-if="skills.length === 0" class="py-8 text-center opacity-70">
                Nenhuma skill cadastrada. Envie um PDF de fluxo ou procedimento para gerar a primeira.
            </p>

            <div class="space-y-2">
                <article v-for="skill in skills" :key="skill.id"
                    class="flex flex-col gap-3 rounded-2xl border border-base-content/10 bg-base-100 p-3 sm:flex-row sm:items-center">
                    <div class="min-w-0 flex-1">
                        <p class="truncate font-mono text-sm font-semibold">{{ skill.arquivo }}</p>
                        <p v-if="skill.titulo" class="truncate text-sm opacity-70">{{ skill.titulo }}</p>
                        <p v-else-if="skill.status === 'gerando'" class="text-sm opacity-70">
                            Lendo o PDF e escrevendo o roteiro...
                        </p>
                        <p v-if="skill.status === 'erro'" class="text-sm text-error">{{ skill.observacoes }}</p>
                    </div>

                    <div class="flex items-center gap-2">
                        <span class="badge" :class="statusSkill[skill.status].classe">
                            <span v-if="skill.status === 'gerando'" class="loading loading-spinner loading-xs"></span>
                            {{ statusSkill[skill.status].texto }}
                        </span>
                        <button v-if="skill.status === 'rascunho' || skill.status === 'ativa'"
                            class="btn btn-ghost btn-sm" @click="abrirEdicao(skill)">
                            <i class="bi bi-pencil-square"></i>
                            {{ skill.status === 'rascunho' ? 'Revisar' : 'Editar' }}
                        </button>
                        <button v-if="skill.status === 'rascunho' || skill.status === 'ativa'"
                            class="btn btn-sm" :class="skill.status === 'ativa' ? 'btn-ghost' : 'btn-success'"
                            @click="alternarAtivacao(skill)">
                            {{ skill.status === 'ativa' ? 'Desativar' : 'Ativar' }}
                        </button>
                        <a v-if="skill.arquivo_origem" :href="skill.arquivo_origem" target="_blank"
                            class="btn btn-ghost btn-sm btn-square" aria-label="Ver PDF de origem" title="Ver PDF de origem">
                            <i class="bi bi-file-earmark-pdf"></i>
                        </a>
                        <button class="btn btn-ghost btn-sm btn-square" @click="abrirModalExclusao(skill)"
                            aria-label="Excluir skill" title="Excluir skill">
                            <i class="bi bi-trash3-fill text-error"></i>
                        </button>
                    </div>
                </article>
            </div>

            <!-- Modal de importação -->
            <dialog ref="modalImportacao" class="modal">
                <div class="modal-box">
                    <h3 class="font-bold text-lg">Criar skill a partir de PDF</h3>
                    <p class="py-3 text-sm opacity-70">
                        O assistente lê o documento e escreve um rascunho de skill. Ele só passa a ser usado
                        depois que você revisar e ativar.
                    </p>
                    <input type="file" accept=".pdf" @change="selecionarPdf"
                        class="file-input file-input-bordered w-full" />
                    <div class="modal-action">
                        <button class="btn" @click="modalImportacao?.close()">Cancelar</button>
                        <button class="btn btn-primary" :disabled="!arquivoPdf || enviando" @click="enviarPdf">
                            <span v-if="enviando" class="loading loading-spinner loading-xs"></span>
                            Gerar skill
                        </button>
                    </div>
                </div>
                <form method="dialog" class="modal-backdrop">
                    <button>close</button>
                </form>
            </dialog>

            <!-- Modal de revisão/edição -->
            <dialog ref="modalEdicao" class="modal">
                <div class="modal-box flex max-h-[90vh] w-11/12 max-w-4xl flex-col">
                    <h3 class="font-bold text-lg font-mono">{{ skillEmEdicao?.arquivo }}</h3>

                    <div v-if="pontosARevisar.length" role="alert" class="alert alert-warning mt-3 items-start">
                        <i class="bi bi-exclamation-triangle"></i>
                        <div>
                            <p class="font-semibold">Confira antes de ativar</p>
                            <ul class="list-disc pl-4 text-sm">
                                <li v-for="ponto in pontosARevisar" :key="ponto">{{ ponto }}</li>
                            </ul>
                        </div>
                    </div>

                    <p class="mt-3 text-sm opacity-70">
                        Confira se a referência está fiel ao documento e se a <code>descricao</code> diz
                        claramente quando a skill deve ser usada.
                    </p>
                    <textarea v-model="conteudoEditado" spellcheck="false"
                        class="textarea textarea-bordered mt-2 min-h-[50vh] w-full flex-1 font-mono text-sm"></textarea>

                    <div v-if="erroEdicao" role="alert" class="alert alert-error mt-3">{{ erroEdicao }}</div>

                    <div class="modal-action">
                        <button class="btn" @click="modalEdicao?.close()">Cancelar</button>
                        <button class="btn" :disabled="salvando" @click="salvarEdicao(false)">Salvar</button>
                        <button v-if="skillEmEdicao?.status === 'rascunho'" class="btn btn-success"
                            :disabled="salvando" @click="salvarEdicao(true)">
                            Salvar e ativar
                        </button>
                    </div>
                </div>
                <form method="dialog" class="modal-backdrop">
                    <button>close</button>
                </form>
            </dialog>

            <!-- Modal de confirmação de exclusão -->
            <dialog ref="modalExclusao" class="modal">
                <div class="modal-box">
                    <h3 class="font-bold text-lg">Confirmar exclusão</h3>
                    <p class="py-4">
                        Tem certeza que deseja excluir a skill
                        <strong class="font-mono">{{ skillParaExcluir?.arquivo }}</strong>?
                    </p>
                    <div class="modal-action">
                        <button class="btn" @click="modalExclusao?.close()">Cancelar</button>
                        <button class="btn btn-error" @click="confirmarExclusao">Excluir</button>
                    </div>
                </div>
                <form method="dialog" class="modal-backdrop">
                    <button>close</button>
                </form>
            </dialog>
        </div>
    </Layout>
</template>
