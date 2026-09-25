<script setup lang="ts">
import type { TFonte, TMensagem } from './ChatComponente.vue';
import markdownit from 'markdown-it';
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';


const md = markdownit();


const props = defineProps<{
    mensagem: TMensagem,
    indexMensagemSelecionada: number;
    maxMensagemSelecionada: number;
    setIndexMensagemSelecionada: (index: number) => void;
}>();

const curtido = ref<boolean | null>(props.mensagem.curtido);
const copiado = ref(false);
const fonteAtiva = ref<TFonte | null>(null);
const citacaoAtiva = ref<HTMLAnchorElement | null>(null);
const tooltipRef = ref<HTMLElement | null>(null);
const tooltipPosicionado = ref(false);
const tooltipStyle = ref({ left: '0px', top: '0px' });
const tooltipId = computed(() => `fonte-tooltip-${props.mensagem.id}`);
let tooltipFixado = false;
let temporizadorOcultar: ReturnType<typeof setTimeout> | null = null;

const fontes = computed(() => props.mensagem.fontes ?? []);
const numerosDisponiveis = computed(() => new Set(fontes.value.map(fonte => fonte.numero)));

const renderLinkOpen = md.renderer.rules.link_open;
md.renderer.rules.link_open = (tokens, index, options, env, self) => {
    const token = tokens[index];
    if (token.attrGet('href')?.startsWith(`#fonte-${props.mensagem.id}-`)) {
        token.attrJoin('class', 'citacao-fonte');
        token.attrSet('aria-describedby', tooltipId.value);
        const numero = Number(token.attrGet('href')?.match(/-(\d+)$/)?.[1]);
        const nome = fontes.value.find(fonte => fonte.numero === numero)?.nome;
        if (nome) token.attrSet('aria-label', `Fonte ${numero}: ${nome}`);
    }
    return renderLinkOpen
        ? renderLinkOpen(tokens, index, options, env, self)
        : self.renderToken(tokens, index, options);
};

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

function encontrarCitacao(target: EventTarget | null): HTMLAnchorElement | null {
    if (!(target instanceof Element)) return null;
    const link = target.closest('a.citacao-fonte');
    return link instanceof HTMLAnchorElement ? link : null;
}

function cancelarOcultacao() {
    if (temporizadorOcultar !== null) clearTimeout(temporizadorOcultar);
    temporizadorOcultar = null;
}

function agendarOcultacao() {
    cancelarOcultacao();
    temporizadorOcultar = setTimeout(() => {
        if (!tooltipFixado) esconderFonte();
    }, 180);
}

async function mostrarFonte(link: HTMLAnchorElement) {
    cancelarOcultacao();
    const numero = Number(link.hash.match(/-(\d+)$/)?.[1]);
    const fonte = fontes.value.find(item => item.numero === numero);
    if (!fonte) return;

    citacaoAtiva.value = link;
    fonteAtiva.value = fonte;
    tooltipPosicionado.value = false;
    await nextTick();
    if (citacaoAtiva.value !== link) return;

    const rect = link.getBoundingClientRect();
    const largura = Math.min(448, window.innerWidth - 24);
    const altura = tooltipRef.value?.getBoundingClientRect().height ?? 0;
    const esquerda = Math.max(12, Math.min(rect.left, window.innerWidth - largura - 12));
    const abaixo = rect.bottom + 8;
    const acima = rect.top - altura - 8;
    const topo = abaixo + altura <= window.innerHeight - 12
        ? abaixo
        : acima >= 12 ? acima : Math.max(12, window.innerHeight - altura - 12);
    tooltipStyle.value = { left: `${esquerda}px`, top: `${topo}px` };
    tooltipPosicionado.value = true;
}

function esconderFonte() {
    cancelarOcultacao();
    fonteAtiva.value = null;
    citacaoAtiva.value = null;
    tooltipPosicionado.value = false;
    tooltipFixado = false;
}

function aoPassarMouse(event: MouseEvent) {
    const link = encontrarCitacao(event.target);
    if (link && citacaoAtiva.value !== link) {
        tooltipFixado = false;
        void mostrarFonte(link);
    }
}

function aoSairMouse(event: MouseEvent) {
    const link = encontrarCitacao(event.target);
    const destino = event.relatedTarget;
    if (link !== citacaoAtiva.value || tooltipFixado) return;
    if (destino instanceof Node &&
        (link?.contains(destino) || tooltipRef.value?.contains(destino))) return;
    agendarOcultacao();
}

function aoFocar(event: FocusEvent) {
    const link = encontrarCitacao(event.target);
    if (link) void mostrarFonte(link);
}

function aoDesfocar(event: FocusEvent) {
    const destino = event.relatedTarget;
    if (!tooltipFixado && !(destino instanceof Node && tooltipRef.value?.contains(destino))) {
        esconderFonte();
    }
}

function aoClicarCitacao(event: MouseEvent) {
    const link = encontrarCitacao(event.target);
    if (!link) return;
    event.preventDefault();
    if (tooltipFixado && citacaoAtiva.value === link) {
        esconderFonte();
    } else {
        tooltipFixado = true;
        void mostrarFonte(link);
    }
}

function aoClicarFora(event: PointerEvent) {
    const alvo = event.target;
    if (alvo instanceof Node &&
        (citacaoAtiva.value?.contains(alvo) || tooltipRef.value?.contains(alvo))) return;
    esconderFonte();
}

function aoRolar(event: Event) {
    if (!(event.target instanceof Node && tooltipRef.value?.contains(event.target))) {
        esconderFonte();
    }
}

function aoPressionarTecla(event: KeyboardEvent) {
    if (event.key === 'Escape') esconderFonte();
}

onMounted(() => {
    document.addEventListener('pointerdown', aoClicarFora);
    document.addEventListener('scroll', aoRolar, true);
    window.addEventListener('resize', esconderFonte);
    document.addEventListener('keydown', aoPressionarTecla);
});

onUnmounted(() => {
    cancelarOcultacao();
    document.removeEventListener('pointerdown', aoClicarFora);
    document.removeEventListener('scroll', aoRolar, true);
    window.removeEventListener('resize', esconderFonte);
    document.removeEventListener('keydown', aoPressionarTecla);
});

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
            v-html="respostaHtml" @mouseover="aoPassarMouse" @mouseout="aoSairMouse"
            @focusin="aoFocar" @focusout="aoDesfocar" @click="aoClicarCitacao"></div>
        <div v-else-if="!mensagem.progresso" class="inline-grid *:[grid-area:1/1] pl-1" aria-label="Assistente digitando resposta">
            <div class="status status-neutral animate-ping status-lg"></div>
            <div class="status status-neutral status-lg"></div>
        </div>

        <div v-if="mensagem.progresso" class="flex items-center gap-2 pl-1 text-sm opacity-70"
            role="status" aria-live="polite">
            <span class="loading loading-spinner loading-xs" aria-hidden="true"></span>
            <span>{{ mensagem.progresso }}</span>
        </div>

        <Teleport to="body">
            <div v-if="fonteAtiva" :id="tooltipId" ref="tooltipRef" role="tooltip"
                class="fonte-tooltip fixed z-50 w-[min(28rem,calc(100vw-1.5rem))] rounded-xl border border-base-content/15 bg-base-100 p-3 text-sm shadow-xl"
                :class="{ 'invisible': !tooltipPosicionado }" :style="tooltipStyle"
                @mouseenter="cancelarOcultacao" @mouseleave="!tooltipFixado && esconderFonte()">
                <div class="font-semibold">Fonte {{ fonteAtiva.numero }} · {{ fonteAtiva.nome }}</div>
                <div class="mt-0.5 text-xs opacity-70">
                    {{ fonteAtiva.tipo === 'legislacao' ? 'Legislação' : 'Manual' }}
                </div>
                <p class="mt-2 max-h-[45vh] overflow-y-auto whitespace-pre-wrap wrap-break-word">
                    {{ fonteAtiva.trecho }}
                </p>
            </div>
        </Teleport>

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
