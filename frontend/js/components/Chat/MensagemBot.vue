<script setup lang="ts">
import type { TMensagem } from './ChatComponente.vue';
import { usePage } from '@inertiajs/vue3';
import markdownit from 'markdown-it';
import { computed, nextTick, ref, watch } from 'vue';


const md = markdownit();


const props = defineProps<{
    mensagem: TMensagem,
    indexMensagemSelecionada: number;
    maxMensagemSelecionada: number;
    setIndexMensagemSelecionada: (index: number) => void;
}>();

const curtido = ref<boolean | null>(props.mensagem.curtido);
const copiado = ref(false);
const fontesAbertas = ref(false);
const usuarioAutenticado = Boolean(usePage().props.user);

const fontes = computed(() => props.mensagem.fontes ?? []);
const numerosDisponiveis = computed(() => new Set(fontes.value.map(fonte => fonte.numero)));

const respostaHtml = computed(() => {
    const texto = props.mensagem.conteudo.replace(
        /\[Fonte\s+(\d+)\]/gi,
        (citacao, numero) => numerosDisponiveis.value.has(Number(numero))
            ? `[Fonte ${numero}](#fonte-${props.mensagem.id}-${numero})`
            : citacao,
    ).replace(
        /\(fontes?\s+\d+(?:\s*,\s*\d+)*\)/gi,
        (citacao) => {
            const numeros = [...citacao.matchAll(/\d+/g)].map(match => Number(match[0]));
            if (!numeros.every(numero => numerosDisponiveis.value.has(numero))) return citacao;
            return `(${numeros.map(numero =>
                `[Fonte ${numero}](#fonte-${props.mensagem.id}-${numero})`
            ).join(', ')})`;
        },
    );
    return md.render(texto);
});

function aoAlternarFontes(event: Event) {
    fontesAbertas.value = (event.target as HTMLDetailsElement).open;
}

async function abrirFonte(event: MouseEvent) {
    const alvo = event.target as HTMLElement;
    const link = alvo.closest('a[href^="#fonte-"]') as HTMLAnchorElement | null;
    if (!link) return;
    event.preventDefault();
    fontesAbertas.value = true;
    await nextTick();
    document.getElementById(link.hash.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}


watch(() => props.mensagem.curtido, (novoCurtido) => {
    curtido.value = novoCurtido;
});

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

async function curtirMensagem(valor: boolean) {
    const novoValor = curtido.value === valor ? null : valor;

    try {
        const response = await fetch(`/api/mensagens/${props.mensagem.id}/curtir`, {
            method: 'PATCH',
            body: JSON.stringify({ curtido: novoValor }),
        });

        if (response.ok) {
            curtido.value = novoValor;
            props.mensagem.curtido = novoValor;
        }
    } catch (error) {
        console.error('Erro ao curtir mensagem:', error);
    }
}
</script>

<template>
    <article class="mt-4 flex flex-col items-start gap-2" aria-label="Mensagem do assistente">

        <div v-if="mensagem.conteudo"
            class="markdown w-full rounded-2xl bg-base-100"
            v-html="respostaHtml" @click="abrirFonte"></div>
        <div v-else class="inline-grid *:[grid-area:1/1] pl-1" aria-label="Assistente digitando resposta">
            <div class="status status-neutral animate-ping status-lg"></div>
            <div class="status status-neutral status-lg"></div>
        </div>

        <details v-if="fontes.length" :open="fontesAbertas" @toggle="aoAlternarFontes"
            class="w-full rounded-xl border border-base-content/15 bg-base-200/50 px-3 py-2">
            <summary class="cursor-pointer text-sm font-semibold">
                Fontes consultadas ({{ fontes.length }})
            </summary>
            <ol class="mt-3 space-y-3">
                <li v-for="fonte in fontes" :id="`fonte-${mensagem.id}-${fonte.numero}`"
                    :key="fonte.numero" class="rounded-lg bg-base-100 p-3 text-sm scroll-mt-4">
                    <div class="font-semibold">Fonte {{ fonte.numero }} · {{ fonte.nome }}</div>
                    <div class="mt-0.5 text-xs opacity-70">
                        {{ fonte.tipo === 'legislacao' ? 'Legislação' : 'Manual' }}
                    </div>
                    <p class="mt-2 whitespace-pre-wrap wrap-break-word">{{ fonte.trecho }}</p>
                    <a v-if="usuarioAutenticado" class="link link-primary mt-2 inline-block"
                        :href="`/api/mensagens/${mensagem.id}/documentos/${fonte.documento_id}/arquivo`"
                        target="_blank" rel="noopener noreferrer">
                        Abrir PDF <span class="sr-only">de {{ fonte.nome }} em nova aba</span>
                    </a>
                </li>
            </ol>
        </details>

        <div class="flex flex-wrap items-center gap-1">
            <div class="flex items-center gap-0.5" v-if="maxMensagemSelecionada > 0" aria-label="Navegação entre respostas">
                <button class="btn btn-ghost btn-xs btn-square" :disabled="indexMensagemSelecionada <= 0"
                    aria-label="Resposta anterior" title="Resposta anterior"
                    @click="setIndexMensagemSelecionada(indexMensagemSelecionada - 1)">
                    <i class="bi bi-caret-left text-base"></i>
                </button>
                <span class="text-xs h-fit px-1">{{ indexMensagemSelecionada + 1 }}/{{ maxMensagemSelecionada + 1 }}</span>
                <button class="btn btn-ghost btn-xs btn-square"
                    aria-label="Próxima resposta" title="Próxima resposta"
                    @click="setIndexMensagemSelecionada(indexMensagemSelecionada + 1)"
                    :disabled="indexMensagemSelecionada >= maxMensagemSelecionada">
                    <i class="bi bi-caret-right text-base"></i>
                </button>
            </div>
            <button class="btn btn-ghost btn-xs btn-square" @click="copiarMensagem" aria-label="Copiar mensagem"
                :title="copiado ? 'Copiado' : 'Copiar mensagem'">
                <i class="text-base" :class="copiado ? 'bi bi-check-lg' : 'bi bi-copy'"></i>
            </button>
            <button v-if="curtido !== false" class="btn btn-ghost btn-xs btn-square" @click="curtirMensagem(true)"
                aria-label="Curtir resposta" title="Curtir resposta"
                :class="{ 'text-success': curtido === true }">
                <i class="text-base"
                    :class="curtido === true ? 'bi bi-hand-thumbs-up-fill' : 'bi bi-hand-thumbs-up'"></i>
            </button>
            <button v-if="curtido !== true" class="btn btn-ghost btn-xs btn-square" @click="curtirMensagem(false)"
                aria-label="Não curtir resposta" title="Não curtir resposta"
                :class="{ 'text-error': curtido === false }">
                <i class="text-base"
                    :class="curtido === false ? 'bi bi-hand-thumbs-down-fill' : 'bi bi-hand-thumbs-down'"></i>
            </button>
        </div>
    </article>
</template>
