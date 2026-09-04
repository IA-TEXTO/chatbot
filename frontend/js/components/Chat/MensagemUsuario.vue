<script setup lang="ts">
import { TMensagem } from './ChatComponente.vue';
import { nextTick, ref } from 'vue';

const props = defineProps<{
    mensagem: TMensagem,
    indexMensagemSelecionada: number;
    maxMensagemSelecionada: number;
    setIndexMensagemSelecionada: (index: number) => void;
    edicaoDesabilitada: boolean;
}>();

const emit = defineEmits<{
    editarMensagem: [idMensagem: number, conteudo: string];
}>();

const copiado = ref(false);
const editando = ref(false);
const conteudoEdicao = ref('');
const editorEdicao = ref<HTMLTextAreaElement | null>(null);

function escapeHtml(str: string): string {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;")
        .replace(/\n/g, '<br>');
}

async function copiarMensagem() {
    try {
        await navigator.clipboard.writeText(props.mensagem.conteudo);
        copiado.value = true;
        setTimeout(() => {
            copiado.value = false;
        }, 2000);
    } catch (error) {
        console.error('Erro ao copiar mensagem:', error);
    }
}

function ajustarAlturaEdicao() {
    if (!editorEdicao.value) return;

    editorEdicao.value.style.height = 'auto';
    editorEdicao.value.style.height = `${Math.min(editorEdicao.value.scrollHeight, 176)}px`;
}

async function iniciarEdicao() {
    if (props.edicaoDesabilitada) return;

    conteudoEdicao.value = props.mensagem.conteudo;
    editando.value = true;
    await nextTick();
    ajustarAlturaEdicao();
    editorEdicao.value?.focus();
    editorEdicao.value?.setSelectionRange(
        conteudoEdicao.value.length,
        conteudoEdicao.value.length,
    );
}

function cancelarEdicao() {
    conteudoEdicao.value = '';
    editando.value = false;
}

function salvarEdicao() {
    const novoConteudo = conteudoEdicao.value.trim();
    if (
        !novoConteudo ||
        novoConteudo === props.mensagem.conteudo.trim() ||
        props.edicaoDesabilitada
    ) return;

    emit('editarMensagem', props.mensagem.id, novoConteudo);
    editando.value = false;
}

</script>

<template>
    <article class="mt-1 flex flex-col items-end gap-2" aria-label="Mensagem do usuário">
        <div v-if="!editando"
            class="max-w-[92%] sm:max-w-2xl rounded-2xl bg-neutral px-4 py-2.5 text-neutral-content whitespace-pre-wrap wrap-break-word shadow-sm">
            <p v-html="escapeHtml(mensagem.conteudo)"></p>
        </div>
        <div v-else
            class="w-full max-w-2xl overflow-hidden rounded-2xl border border-base-content/15 bg-base-100 shadow-md ring-1 ring-base-content/5">
            <textarea ref="editorEdicao" v-model="conteudoEdicao" rows="1"
                class="block min-h-16 max-h-44 w-full resize-none overflow-y-auto bg-transparent px-4 pb-3 pt-3.5 text-base leading-relaxed text-base-content outline-none"
                aria-label="Editar mensagem"
                @input="ajustarAlturaEdicao"
                @keydown.esc.prevent="cancelarEdicao"
                @keydown.enter.exact.prevent="salvarEdicao"></textarea>
            <div class="flex items-center justify-between gap-3 border-t border-base-content/10 bg-base-200/50 px-3 py-2">
                <span class="hidden text-xs text-base-content/50 sm:block">
                    Enter para enviar · Shift+Enter para nova linha
                </span>
                <div class="ml-auto flex items-center gap-1.5">
                <button type="button" class="btn btn-ghost btn-sm h-8 min-h-8 rounded-full px-3 font-normal"
                    @click="cancelarEdicao">
                    Cancelar
                </button>
                <button type="button" class="btn btn-neutral btn-sm h-8 min-h-8 rounded-full px-4"
                    :disabled="!conteudoEdicao.trim() || conteudoEdicao.trim() === mensagem.conteudo.trim() || edicaoDesabilitada"
                    @click="salvarEdicao">
                    <i class="bi bi-arrow-up-short text-lg"></i>
                    Enviar
                </button>
                </div>
            </div>
        </div>
        <div v-if="!editando" class="flex flex-wrap items-center gap-1 px-1 py-1">
            <button class="btn btn-ghost btn-xs btn-square" @click="copiarMensagem" aria-label="Copiar mensagem"
                :title="copiado ? 'Copiado' : 'Copiar mensagem'">
                <i class="text-base" :class="copiado ? 'bi bi-check-lg' : 'bi bi-copy'"></i>
            </button>
            <button type="button" class="btn btn-ghost btn-xs btn-square"
                :disabled="edicaoDesabilitada"
                :class="{ 'pointer-events-none opacity-40': edicaoDesabilitada }"
                @click="iniciarEdicao"
                aria-label="Editar mensagem" title="Editar mensagem">
                <i class="bi bi-pencil text-base"></i>
            </button>
            <div class="flex items-center gap-0.5" v-if="maxMensagemSelecionada > 0" aria-label="Navegação entre versões">
                <button class="btn btn-ghost btn-xs btn-square" :disabled="indexMensagemSelecionada <= 0"
                    aria-label="Versão anterior" title="Versão anterior"
                    @click="setIndexMensagemSelecionada(indexMensagemSelecionada - 1)">
                    <i class="bi bi-caret-left text-base"></i>
                </button>
                <span class="text-xs h-fit px-1">{{ indexMensagemSelecionada + 1 }}/{{ maxMensagemSelecionada + 1 }}</span>
                <button class="btn btn-ghost btn-xs btn-square"
                    aria-label="Próxima versão" title="Próxima versão"
                    @click="setIndexMensagemSelecionada(indexMensagemSelecionada + 1)"
                    :disabled="indexMensagemSelecionada >= maxMensagemSelecionada">
                    <i class="bi bi-caret-right text-base"></i>
                </button>
            </div>
        </div>
    </article>
</template>
