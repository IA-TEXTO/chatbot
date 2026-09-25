<script setup lang="ts">
import { ref, nextTick, computed, watch, onMounted, onUnmounted } from 'vue';
import { router, usePage } from '@inertiajs/vue3';
import Mensagem from './Mensagem.vue';
import { Usuario } from '@/types/index';

export type TFonte = {
    numero: number;
    documento_id: number;
    nome: string;
    tipo: string;
    trecho: string;
}

export type TMensagem = {
    id: number;
    tipo: 'USUARIO' | 'ASSISTENTE';
    conteudo: string;
    fontes: TFonte[];
    progresso?: string;
    mensagem_pai: number | null;
    mensagens_filhas: number[];
    curtido: boolean | null;
}

export type MapMensagens = {
    [key: number]: TMensagem;
}

type chatResponse = {
    id_conversa: number;
    id_mensagem_pergunta: number;
    id_mensagem_resposta: number;
}

const page = usePage<{
    map_mensagens: MapMensagens,
    id_conversa: number,
    user: Usuario | null,
}>();

const mapMensagens = ref<MapMensagens>(page.props.map_mensagens ?? {});
const idConversa = ref<number | null>(page.props.id_conversa ?? null);
const pergunta = ref('');
const enviandoMensagem = ref(false);
const erroEnvio = ref('');
const editable = ref<HTMLElement | null>(null);
const containerMensagens = ref<HTMLElement | null>(null);
const mensagemRef = ref<typeof Mensagem | null>(null);
let proximoIdTemporario = -1;

const perguntasSugeridas = [
    'Quais documentos eu preciso para iniciar o CAR?',
    'Como preencher área de APP no CAR?',
    'Qual a diferença entre Reserva Legal e APP?'
];

const temMensagens = computed(() => Object.keys(mapMensagens.value).length > 0);

function focarInputMensagem(cursorNoFinal = true) {
    if (!editable.value) return;

    editable.value.focus();
    if (!cursorNoFinal) return;

    const selection = window.getSelection();
    if (!selection) return;

    const range = document.createRange();
    range.selectNodeContents(editable.value);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
}

function ajustarAlturaEditable() {
    if (!editable.value) return;

    editable.value.style.height = 'auto';
    const maxHeight = 208;
    const novaAltura = Math.min(editable.value.scrollHeight, maxHeight);
    editable.value.style.height = `${Math.max(novaAltura, 24)}px`;
    editable.value.style.overflowY = editable.value.scrollHeight > maxHeight ? 'auto' : 'hidden';
}

function setPergunta(valor: string) {
    pergunta.value = valor;
    if (!editable.value) return;
    editable.value.textContent = valor;
    nextTick(() => {
        ajustarAlturaEditable();
        focarInputMensagem();
    });
}

const handleWindowFocus = () => {
    focarInputMensagem();
};

const mensagensRaiz = computed<number[]>(
    () =>
        Object.values(mapMensagens.value)
            .filter(mensagem => mensagem.mensagem_pai === null)
            .map(mensagem => mensagem.id)
);

watch(
    idConversa, (novoIdConversa, antigoIdConversa) => {
        if (novoIdConversa !== antigoIdConversa) {
            if (novoIdConversa == null) {
                router.visit('/', { replace: true, preserveState: true });
            } else if (page.props.user) {
                router.visit(`/c/${novoIdConversa}/`, { replace: true, preserveState: true });
            }
        }
    }
);

async function adicionarMensagem(mensagem: TMensagem) {
    mapMensagens.value[mensagem.id] = mensagem;
    await nextTick();
    scrollParaUltimaMensagem();
}

function limparInput() {
    pergunta.value = '';
    if (editable.value) {
        editable.value.textContent = '';
        ajustarAlturaEditable();
    }
}

function gerarIdTemporario() {
    return proximoIdTemporario--;
}

function substituirIdFilho(idPai: number, idAntigo: number, idNovo: number) {
    const filhos = mapMensagens.value[idPai]?.mensagens_filhas;
    if (!filhos) return;

    const index = filhos.indexOf(idAntigo);
    if (index !== -1) filhos[index] = idNovo;
}

function aplicarIdsPersistidos(
    dados: chatResponse,
    mensagemUsuario: TMensagem,
    botMessage: TMensagem,
) {
    idConversa.value = dados.id_conversa;

    const idAntigoUsuario = mensagemUsuario.id;
    mensagemUsuario.id = dados.id_mensagem_pergunta;
    delete mapMensagens.value[idAntigoUsuario];
    mapMensagens.value[mensagemUsuario.id] = mensagemUsuario;

    if (mensagemUsuario.mensagem_pai !== null) {
        substituirIdFilho(
            mensagemUsuario.mensagem_pai,
            idAntigoUsuario,
            mensagemUsuario.id,
        );
    }

    const idAntigoBot = botMessage.id;
    botMessage.id = dados.id_mensagem_resposta;
    botMessage.mensagem_pai = mensagemUsuario.id;
    delete mapMensagens.value[idAntigoBot];
    mapMensagens.value[botMessage.id] = botMessage;
    substituirIdFilho(mensagemUsuario.id, idAntigoBot, botMessage.id);
}

async function criarRamificacao(
    conteudo: string,
    idMensagemPai: number | null,
    idMensagemEditada: number | null = null,
) {
    const mensagem = conteudo.trim();
    if (!mensagem || enviandoMensagem.value) return;

    erroEnvio.value = '';
    enviandoMensagem.value = true;

    const mensagemUsuario: TMensagem = {
        id: gerarIdTemporario(),
        tipo: 'USUARIO',
        conteudo: mensagem,
        mensagem_pai: idMensagemPai,
        mensagens_filhas: [],
        curtido: null,
        fontes: [],
    };

    if (idMensagemPai !== null) {
        mapMensagens.value[idMensagemPai].mensagens_filhas.push(mensagemUsuario.id);
    }

    await adicionarMensagem(mensagemUsuario);

    const botMessage: TMensagem = {
        id: gerarIdTemporario(),
        tipo: 'ASSISTENTE',
        conteudo: '',
        mensagem_pai: mensagemUsuario.id,
        mensagens_filhas: [],
        curtido: null,
        fontes: [],
        progresso: 'Enviando pergunta...',
    };

    mapMensagens.value[mensagemUsuario.id].mensagens_filhas.push(botMessage.id);
    await adicionarMensagem(botMessage);

    const payload = {
        mensagem,
        stream: true,
        id_mensagem_pai: idMensagemPai,
        id_mensagem_editada: idMensagemEditada,
        id_conversa: idConversa.value,
    };

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            throw new Error(`Falha ao enviar mensagem: HTTP ${response.status}`);
        }

        if (!response.body) {
            throw new Error('Resposta sem corpo de streaming.');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let cabecalhoProcessado = false;
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value, { stream: !done });

            let fimLinha = buffer.indexOf('\n');
            while (fimLinha !== -1) {
                const linha = buffer.slice(0, fimLinha);
                buffer = buffer.slice(fimLinha + 1);
                if (linha) {
                    const evento = JSON.parse(linha);
                    if (!cabecalhoProcessado) {
                        aplicarIdsPersistidos(evento as chatResponse, mensagemUsuario, botMessage);
                        cabecalhoProcessado = true;
                    } else if (evento.tipo === 'progresso') {
                        mapMensagens.value[botMessage.id].progresso = evento.conteudo;
                    } else if (evento.tipo === 'resposta_final') {
                        mapMensagens.value[botMessage.id].conteudo = evento.conteudo;
                        mapMensagens.value[botMessage.id].progresso = undefined;
                    } else if (evento.tipo === 'trecho') {
                        mapMensagens.value[botMessage.id].conteudo += evento.conteudo;
                        mapMensagens.value[botMessage.id].progresso = 'Escrevendo resposta...';
                        await nextTick();
                        scrollParaUltimaMensagem();
                    } else if (evento.tipo === 'fontes') {
                        mapMensagens.value[botMessage.id].fontes = evento.fontes;
                    }
                }
                fimLinha = buffer.indexOf('\n');
            }
            if (done) {
                if (!cabecalhoProcessado) throw new Error('Metadados da resposta não recebidos.');
                if (buffer.trim()) throw new Error('Resposta em streaming incompleta.');
                break;
            }
        }
    } catch (error) {
        const mensagemBotReativa = mapMensagens.value[botMessage.id];
        if (mensagemBotReativa) {
            mensagemBotReativa.conteudo = 'Ocorreu um erro ao enviar sua mensagem. Tente novamente.';
            mensagemBotReativa.progresso = undefined;
        }
        erroEnvio.value = 'Não foi possível enviar sua pergunta agora.';
        console.error(error);
    } finally {
        mapMensagens.value[botMessage.id].progresso = undefined;
        enviandoMensagem.value = false;
        await nextTick();
        focarInputMensagem();
    }
}

async function enviarMensagem() {
    const mensagem = pergunta.value.trim();
    if (!mensagem || enviandoMensagem.value) return;

    const idMensagemPai = mensagensRaiz.value.length > 0
        ? mensagemRef.value?.obterIdUltimaMensagem() ?? null
        : null;

    limparInput();
    await nextTick();
    focarInputMensagem(false);
    await criarRamificacao(mensagem, idMensagemPai);
}

async function editarMensagem(idMensagem: number, novoConteudo: string) {
    const mensagemOriginal = mapMensagens.value[idMensagem];
    if (!mensagemOriginal || mensagemOriginal.tipo !== 'USUARIO') return;

    await criarRamificacao(
        novoConteudo,
        mensagemOriginal.mensagem_pai,
        mensagemOriginal.id,
    );
}

function handlePaste(e: ClipboardEvent) {
    e.preventDefault();
    const text = e.clipboardData?.getData('text/plain') || '';
    document.execCommand('insertText', false, text);
}

function handleInput() {
    pergunta.value = editable.value?.innerText ?? '';
    ajustarAlturaEditable();
}

function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        enviarMensagem();
    }
}

function scrollParaUltimaMensagem(smooth = true) {
    const div = containerMensagens.value;
    if (div) {
        div.scrollTo({
            top: div.scrollHeight,
            behavior: smooth ? 'smooth' : 'auto',
        });
    }
}

onMounted(async () => {
    await nextTick();
    scrollParaUltimaMensagem(false);
    focarInputMensagem();
    ajustarAlturaEditable();

    window.addEventListener('focus', handleWindowFocus);
});

onUnmounted(() => {
    window.removeEventListener('focus', handleWindowFocus);
});
</script>

<template>
    <div class="mx-auto flex h-full w-full max-w-5xl flex-1 flex-col px-2 pb-2 pt-3 sm:px-4 sm:pb-4">
        <div ref="containerMensagens" class="min-h-0 flex-1 overflow-y-auto pr-1 chat-scroll-area" aria-live="polite">
            <div class="mx-auto w-full max-w-3xl space-y-4 pb-4">
                <div v-if="!temMensagens"
                    class="rounded-3xl border border-base-content/10 bg-base-100 p-5 shadow-sm sm:p-6">
                    <div class="space-y-3">
                        <h2 class="text-base font-semibold sm:text-lg">Como posso te ajudar com o CAR hoje?</h2>
                        <div class="flex flex-wrap gap-2">
                            <button v-for="sugestao in perguntasSugeridas" :key="sugestao" type="button"
                                class="btn btn-sm rounded-full border-base-content/15 bg-base-200/70 hover:bg-base-200"
                                @click="setPergunta(sugestao)">
                                {{ sugestao }}
                            </button>
                        </div>
                    </div>
                </div>

                <Mensagem ref="mensagemRef" v-if="mensagensRaiz.length > 0" :map-mensagens="mapMensagens"
                    :ids="mensagensRaiz" :edicao-desabilitada="enviandoMensagem"
                    @editar-mensagem="editarMensagem" />
            </div>
        </div>

        <div class="sticky bottom-0 z-10 bg-linear-to-t from-base-100 via-base-100/95 to-transparent pt-3">
            <form @submit.prevent="enviarMensagem" class="mx-auto w-full max-w-3xl">
                <label for="pergunta"
                    class="relative flex cursor-text items-end gap-2 rounded-[28px] border border-base-content/12 bg-base-300 px-3 py-2 shadow-lg"
                    :class="{ 'opacity-70': enviandoMensagem }" @click="editable?.focus()">
                    <span v-if="!pergunta.trim()"
                        class="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 select-none text-base-content/55">
                        Digite sua mensagem...
                    </span>

                    <div class="flex w-full items-center overflow-hidden">
                        <div id="pergunta" ref="editable" role="textbox" tabindex="0" aria-multiline="true"
                            aria-label="Mensagem para o assistente" contenteditable="true"
                            class="chat-input-editor min-h-6 w-full bg-transparent px-1 py-1.5 whitespace-pre-wrap wrap-break-word focus:outline-none"
                            @input="handleInput" @keydown="handleKeydown" @paste="handlePaste" />
                    </div>

                    <button class="btn btn-neutral h-9 w-9 btn-circle p-0" type="submit" :aria-busy="enviandoMensagem"
                        :disabled="!pergunta.trim() || enviandoMensagem">
                        <span v-if="enviandoMensagem" class="loading loading-spinner loading-sm"></span>
                        <i v-else class="bi bi-arrow-up-short text-4xl leading-none"></i>
                    </button>
                </label>

            </form>
        </div>
    </div>
</template>
