# 🤖 Chatbot IntegraCAR

Um chatbot inteligente baseado em RAG (Retrieval-Augmented Generation) para o sistema IntegraCAR, desenvolvido com Django, Vue.js e LangChain.

## Consultas organizadas e exportáveis

O histórico agora permite buscar conversas pelo nome (sem diferenciar acentos ou
maiúsculas) e renomeá-las com até 50 caracteres. Usuários autenticados também
podem baixar a consulta em Markdown pelo botão **Exportar consulta**. O arquivo
inclui perguntas, respostas e trechos das fontes recuperadas. Ao navegar entre
versões editadas, apenas a ramificação selecionada é exportada.

Renomeação e exportação são restritas ao proprietário da conversa. A exportação
fica indisponível enquanto a resposta é gerada. Não há migrações nem novas
dependências para esta entrega.

Roteiro de demonstração:

1. Entre na conta e faça uma pergunta sobre o CAR.
2. Renomeie a conversa para “Documentação CAR”.
3. Busque “documentacao” no histórico para reencontrá-la.
4. Edite uma pergunta e alterne entre as versões com as setas.
5. Clique em **Exportar consulta** e confira o arquivo `.md`: ele contém apenas
   a versão selecionada e os trechos das fontes, quando recuperadas.

Validação local:

```bash
npm run build
npm run typecheck
.venv/bin/python manage.py test chat.tests --noinput
```

Os testes de histórico cobrem ramificações, caminhos inválidos, conteúdo da
exportação, validação do nome e restrições de acesso. Usam objetos simulados no
acesso ao banco; o roteiro acima complementa a validação na aplicação com banco
e serviço de IA em execução.

## Recuperação adaptativa do agente

A triagem agora pode planejar até duas consultas complementares para dúvidas com
assuntos distintos, usando a mesma chamada de IA já existente. O fluxo consulta
esses aspectos antes de gerar a resposta e combina os trechos sem duplicar fontes
nem alterar os números já atribuídos. Se não houver evidência, tenta a pergunta
original quando ela difere da busca reescrita e ainda há orçamento disponível.
Sem fontes após essas tentativas, mantém a resposta de informação insuficiente.

O planejamento e as ferramentas dos especialistas compartilham o limite de duas
buscas adicionais por resposta e de 18 fontes. Buscas repetidas, inclusive com
variações de acento ou caixa, não disparam nova recuperação nem gastam tentativas.
Perguntas simples sem consultas planejadas mantêm uma única busca inicial quando
ela retorna trechos. Cada busca extra pode acrescentar latência e custo de
embedding; não há nova chamada de geração dedicada ao planejamento.

Cenário para demonstrar: pergunte “Como declarar APP e quais documentos preciso
para iniciar o CAR?”. A triagem pode separar os aspectos da pergunta e o agente
recebe os trechos complementares antes de responder. A escolha das consultas é
feita pelo modelo, portanto pode variar entre execuções.

```bash
.venv/bin/python manage.py test chat.tests.test_adaptive_retrieval --noinput
```

Os dez cenários controlados cobrem recuperação após busca vazia, preservação de
termos da pergunta original, perguntas com múltiplos assuntos, estabilidade das
citações, limites compartilhados, deduplicação de consultas e esclarecimento.
Eles verificam o fluxo com agentes e recuperação simulados; ganhos de qualidade
no acervo real ainda precisam ser avaliados com perguntas representativas.

## Memória de evidências da conversa

O agente recebe novamente snapshots dos trechos documentais das últimas 12
mensagens da ramificação selecionada. A memória prioriza mensagens recentes e
fontes citadas, com no máximo quatro trechos e 6.000 caracteres. Trechos que não
cabem são ignorados sem truncar seu conteúdo. Mensagens antigas sem fontes salvas
continuam funcionando normalmente.

A triagem usa esses trechos para entender referências como “essa exceção”. Os
especialistas recebem a união da busca atual com a memória, deduplicada por
documento e conteúdo; fontes novas mantêm prioridade. Os trechos reutilizados são
identificados como snapshots e ficam disponíveis na ferramenta de consulta, nas
fontes salvas da nova resposta e, consequentemente, na exportação. O revisor
recebe também o histórico com as citações remapeadas para os números atuais.
Referências sem trecho disponível são marcadas como fora do contexto atual.

A memória vem exclusivamente do histórico da ramificação fornecido pelo Django,
sem estado global por usuário e sem recuperar outras conversas. Os snapshots não
comprovam relevância nem vigência para a nova pergunta: os prompts orientam a
conferir o suporte documental e buscar mais evidências quando necessário. A busca
atual continua acontecendo e o limite total de 18 fontes permanece.

```bash
.venv/bin/python manage.py test chat.tests.test_evidence_memory --noinput
```

Os testes simulados cobrem continuidade, numeração, deduplicação, limites,
compatibilidade com registros antigos, isolamento entre execuções e contexto do
revisor. A avaliação da qualidade das respostas com o modelo real continua sendo
necessária.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura do Sistema](#arquitetura-do-sistema)
- [Backend (Django)](#backend-django)
- [Frontend (Vue.js)](#frontend-vuejs)
- [Banco de Dados](#banco-de-dados)
- [Sistema RAG](#sistema-rag)
- [Infraestrutura](#infraestrutura)
- [Como Executar](#como-executar)

## 🎯 Visão Geral

O Chatbot IntegraCAR é uma aplicação de inteligência artificial que utiliza a técnica RAG (Retrieval-Augmented Generation) para responder perguntas baseadas em documentos PDF carregados no sistema. O sistema combina busca semântica (embeddings) com busca lexical (BM25) para recuperar os trechos mais relevantes dos documentos antes de gerar as respostas.

### Stack Tecnológico

| Camada | Tecnologia |
|--------|------------|
| **Backend** | Django 5.1, Django Ninja, Django-Q2 |
| **Frontend** | Vue.js 3, Inertia.js, TailwindCSS, DaisyUI |
| **Banco de Dados** | PostgreSQL (ParadeDB) com pgvector |
| **IA/ML** | Agno, LangChain, OpenAI, OpenAI Embeddings |
| **Build Tools** | Vite, uv (Python), npm |
| **Containerização** | Docker, Docker Compose |

## 🏗️ Arquitetura do Sistema

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                   CLIENTE                                    │
│                              (Navegador Web)                                 │
└─────────────────────────────────────┬────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CAMADA FRONTEND                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                         Vue.js 3 + Inertia.js                          │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │  │
│  │  │   Páginas    │  │  Componentes │  │        Estilos               │  │  │
│  │  │  - Index     │  │  - Layout    │  │  - TailwindCSS               │  │  │
│  │  │  - Chat      │  │  - Chat      │  │  - DaisyUI                   │  │  │
│  │  │  - Login     │  │  - Mensagem  │  │                              │  │  │
│  │  │  - Cadastro  │  │  - Forms     │  │                              │  │  │
│  │  │  - Docs      │  │              │  │                              │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                          Vite Dev Server (:5173)                             │
└─────────────────────────────────────┬────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CAMADA BACKEND                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                        Django 5.1 (:8000)                              │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │  │
│  │  │                         CORE                                     │  │  │
│  │  │  - Settings    - URLs       - Middleware    - API (Ninja)        │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │  │
│  │  │      APP: Chat          │  │        APP: Contas                  │  │  │
│  │  │  - Models (Documento,   │  │  - Models (Usuario)                 │  │  │
│  │  │    Conversa, Mensagem)  │  │  - Views (Login, Cadastro, Sair)    │  │  │
│  │  │  - Views (Index, Docs)  │  │  - Forms                            │  │  │
│  │  │  - API REST (chat)      │  │  - Managers                         │  │  │
│  │  │  - RAG System           │  │                                     │  │  │
│  │  │  - Tasks (Django-Q2)    │  │                                     │  │  │
│  │  │  - Signals              │  │                                     │  │  │
│  │  └─────────────────────────┘  └─────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────┬────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           CAMADA DE DADOS                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                 PostgreSQL (ParadeDB) (:5432)                          │  │
│  │  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │  │
│  │  │    Extensões            │  │         Tabelas Principais          │  │  │
│  │  │  - pgvector (vetores)   │  │  - Usuario                          │  │  │
│  │  │  - ParadeDB (BM25)      │  │  - Documento                        │  │  │
│  │  │                         │  │  - ChunkDocumento (embeddings)      │  │  │
│  │  │                         │  │  - Conversa / Mensagem              │  │  │
│  │  │                         │  │  - RespostaCanonica                 │  │  │
│  │  └─────────────────────────┘  └─────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────┬────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           SERVIÇOS EXTERNOS                                  │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────────┐    │
│  │       OpenAI API        │  │              Django-Q2                  │    │
│  │  - Modelo configurável  │  │  - Processamento assíncrono             │    │
│  │  - text-embedding-3     │  │  - Geração de embeddings em background  │    │
│  └─────────────────────────┘  └─────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 🐍 Backend (Django)

### Estrutura de Diretórios

```
├── core/                          # Configurações centrais do Django
│   ├── settings.py               # Configurações do projeto
│   ├── settings_production.py    # Configurações de produção
│   ├── urls.py                   # URLs raiz do projeto
│   ├── api.py                    # Configuração do Django Ninja API
│   ├── middleware.py             # Middlewares customizados
│   ├── utils.py                  # Utilitários gerais
│   ├── wsgi.py                   # Configuração WSGI
│   └── asgi.py                   # Configuração ASGI
│
├── apps/                          # Aplicações Django
│   ├── chat/                     # App principal do chatbot
│   │   ├── models.py            # Modelos de dados
│   │   ├── views.py             # Views (Inertia)
│   │   ├── api.py               # Endpoints REST (Ninja)
│   │   ├── rag.py               # Sistema RAG
│   │   ├── tasks.py             # Tarefas assíncronas (Django-Q)
│   │   ├── signals.py           # Sinais Django
│   │   ├── schemas.py           # Schemas Ninja (validação)
│   │   ├── indexes.py           # Índices customizados (BM25)
│   │   ├── functions.py         # Funções SQL customizadas
│   │   ├── forms.py             # Formulários Django
│   │   └── admin.py             # Admin Django
│   │
│   └── contas/                   # App de autenticação
│       ├── models.py            # Modelo Usuario
│       ├── views.py             # Views de login/cadastro
│       ├── forms.py             # Formulários de auth
│       ├── managers.py          # Managers customizados
│       └── admin.py             # Admin Django
│
└── manage.py                      # CLI Django
```

### Core - Configurações Principais

#### `core/settings.py`
- **Banco de dados**: PostgreSQL com suporte a pgvector
- **Autenticação**: Modelo de usuário customizado (`contas.Usuario`)
- **Static files**: WhiteNoise para servir arquivos estáticos
- **Vite Integration**: Django-Vite para integração com frontend
- **Inertia.js**: Configurado para SSR-ready
- **Django-Q**: Configuração para processamento assíncrono

#### `core/api.py`
```python
from ninja import NinjaAPI

api = NinjaAPI()
api.add_router('', 'chat.api.chat_router')
```

#### `core/middleware.py`
- **DataShareMiddleware**: Compartilha dados globais (user, URLs, messages) com o frontend via Inertia
- **FlushStdoutMiddleware**: Força flush do stdout em desenvolvimento

### App: Chat

#### Models (`apps/chat/models.py`)

| Modelo | Descrição |
|--------|-----------|
| `Documento` | Armazena PDFs carregados com status de processamento |
| `ChunkDocumeto` | Pedaços do documento com embeddings vetoriais (1536 dims) |
| `RespostaCanonica` | Perguntas/respostas pré-definidas com embeddings |
| `Conversa` | Conversas de usuários |
| `Mensagem` | Mensagens individuais (usuário/assistente) |

#### Sistema RAG (`apps/chat/rag.py`)

A classe `Rag` implementa a recuperação documental. A geração e a
orquestração ficam em `apps/chat/agents`:

1. **Extração de Texto**: Processa PDFs usando `PyPDFLoader`
2. **Chunking**: Divide documentos em chunks de ~1000 caracteres com 200 de overlap
3. **Embedding**: Gera vetores usando `text-embedding-3-small` (1536 dimensões)
4. **Busca Híbrida**: Combina BM25 (50%) + Busca Semântica (50%)
5. **Busca no acervo**: Considera todos os documentos processados, sem filtrar por tipo
6. **Orquestração Agno**: Faz triagem estruturada e seleciona especialistas
7. **Revisão**: Respostas legislativas e mistas passam por revisão de evidências

```python
@staticmethod
def top_k_resultados(query: str, k: int = 5):
    # Busca BM25 (lexical)
    ranked_by_bm25 = ChunkDocumeto.objects.filter(conteudo__bm25=query)
    
    # Busca Semântica (vetorial)
    ranked_by_semantic = ChunkDocumeto.objects.annotate(
        score=CosineDistance('embedding', embedding_query)
    )
    
    # Fusão com pesos: BM25 (50%) + Semantic (50%)
    # Reciprocal Rank Fusion
```

#### Agentes (`apps/chat/agents`)

| Agente | Responsabilidade |
|--------|------------------|
| Triagem | Classifica em manual, legislação, mista, conversacional ou fora do escopo |
| Manual | Explica procedimentos, documentos, campos e erros do CAR |
| Legislação | Responde com base nos documentos normativos recuperados |
| Revisor | Remove afirmações sem evidência e confere as citações |
| Geral | Atende cumprimentos e informa o escopo do assistente |

Os especialistas podem consultar orientações canônicas, usar o saldo das duas buscas complementares por resposta
nos PDFs e examinar um trecho pelo número da fonte. Essas ferramentas são apenas
de leitura; os trechos adicionais mantêm números estáveis na resposta. Cada
especialista tem limite de quatro chamadas de ferramenta por execução. As
citações inexistentes são sinalizadas na resposta final, mas essa validação
numérica não prova que o trecho sustente a afirmação.

O histórico e as permissões continuam sob responsabilidade do Django. A
telemetria do Agno fica desativada nos agentes. O streaming envia eventos de
`progresso`, `trecho`, `resposta_final` e `fontes`, com atualização periódica de
progresso durante etapas demoradas. Perguntas que exigem informação atual
ou pesquisa online são enviadas a um agente com a ferramenta nativa
`web_search` da OpenAI via Agno. A rota web transmite o texto à medida
que é gerado e substitui a versão parcial pela resposta com links de
citação ao final. Sem links verificáveis, o assistente informa que não
conseguiu confirmar a resposta. Essa rota não usa os PDFs locais.

#### Views (`apps/chat/views.py`)

| View | URL | Descrição |
|------|-----|-----------|
| `IndexView` | `/` | Página inicial do chat |
| `DocumentosView` | `/documentos/` | Gerenciamento de documentos |
| `ExcluirDocumentoView` | `/documentos/<id>/excluir/` | Exclusão de documentos |

#### API REST (`apps/chat/api.py`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/chat` | POST | Endpoint principal do chat (com streaming) |
| `/api/documentos/{id}/status` | GET | Status de processamento do documento |

#### Signals (`apps/chat/signals.py`)

- **`pre_save`**: Define nome do documento automaticamente
- **`post_save`**: Dispara chain de tarefas para extrair texto e gerar embeddings

#### Tasks (`apps/chat/tasks.py`)

Processamento assíncrono via Django-Q2:
1. `extrair_e_salvar_conteudo`: Extrai texto do PDF
2. `gerar_embedding_documento`: Gera chunks e embeddings

### App: Contas

#### Models (`apps/contas/models.py`)

O modelo `Usuario` estende `AbstractBaseUser`:
- Email como identificador único
- Validações de nome (apenas letras, mín. 3 caracteres)
- Campos: `email`, `name`, `is_staff`, `is_active`, `created_at`, `updated_at`

#### Views (`apps/contas/views.py`)

| View | URL | Descrição |
|------|-----|-----------|
| `LoginView` | `/contas/entrar/` | Login de usuários |
| `CadastroView` | `/contas/cadastrar/` | Registro de novos usuários |
| `SairView` | `/contas/sair/` | Logout |

## ⚡ Frontend (Vue.js)

### Estrutura de Diretórios

```
frontend/
├── base.html                      # Template base Django/Inertia
├── css/
│   ├── main.css                  # Estilos principais
│   └── tailwind.css              # Config TailwindCSS
│
├── js/
│   ├── main.js                   # Entry point Vue/Inertia
│   │
│   ├── pages/                    # Páginas Inertia
│   │   ├── Index.vue            # Página inicial
│   │   ├── Chat/
│   │   │   ├── Chat.vue         # Chat autenticado
│   │   │   ├── ChatAnonimo.vue  # Chat anônimo
│   │   │   └── Documentos.vue   # Gerenciamento de docs
│   │   └── Contas/
│   │       ├── Login.vue        # Página de login
│   │       └── Cadastro.vue     # Página de cadastro
│   │
│   ├── components/               # Componentes reutilizáveis
│   │   ├── Layout.vue           # Layout autenticado (sidebar)
│   │   ├── LayoutAnonimo.vue    # Layout não autenticado
│   │   ├── IntegracarLogo.vue   # Logo do sistema
│   │   ├── Chat/
│   │   │   ├── ChatComponente.vue  # Componente principal do chat
│   │   │   ├── Mensagem.vue        # Wrapper de mensagem
│   │   │   ├── MensagemBot.vue     # Mensagem do assistente
│   │   │   └── MensagemUsuario.vue # Mensagem do usuário
│   │   └── form/
│   │       └── DjangoForm.vue   # Renderização de forms Django
│   │
│   ├── types/                    # TypeScript types
│   │   └── index.ts             # Definições de tipos
│   │
│   └── env.d.ts                  # Declarações de ambiente
│
├── public/                        # Assets estáticos
└── tsconfig.json                  # Config TypeScript
```

### Fluxo da Aplicação

#### Entry Point (`frontend/js/main.js`)

```javascript
import { createInertiaApp } from "@inertiajs/vue3";
import { createApp, h } from "vue";

createInertiaApp({
    resolve: async (name) => {
        const page = (await pages[`./pages/${name}.vue`]()).default;
        return page;
    },
    setup({ el, App, props, plugin }) {
        createApp({ render: () => h(App, props) })
            .use(plugin)
            .mount(el);
    },
});
```

#### Componentes Principais

**`ChatComponente.vue`**
- Input com `contenteditable` para mensagens multilinhas
- Streaming de respostas via `fetch` + `ReadableStream`
- Auto-scroll para última mensagem
- Renderização de markdown nas respostas

**`Layout.vue`**
- Sidebar responsiva com DaisyUI drawer
- Navegação entre páginas
- Menu do usuário com logout

### Integração Inertia.js

O Inertia.js conecta o backend Django com o frontend Vue sem necessidade de API tradicional:

```python
# Backend (views.py)
from inertia import render

def get(self, request):
    return render(request, 'Chat/Documentos', {
        'documentos': documentos,
        'documentos_processados': count
    })
```

```vue
<!-- Frontend (Documentos.vue) -->
<script setup>
defineProps<{
    documentos: Documento[];
    documentos_processados: number;
}>();
</script>
```

### Estilos

- **TailwindCSS 4**: Utilitários CSS
- **DaisyUI 5**: Componentes pré-estilizados (drawer, navbar, buttons, forms)
- **Bootstrap Icons**: Ícones via CDN

## 🗄️ Banco de Dados

### ParadeDB (PostgreSQL)

O projeto utiliza [ParadeDB](https://www.paradedb.com/), uma distribuição PostgreSQL que inclui:

- **pgvector**: Operações vetoriais e busca por similaridade
- **pg_search**: Busca full-text com BM25

### Schema Principal

```sql
-- Documentos e Embeddings
CREATE TABLE documento (
    id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(255),
    arquivo VARCHAR(100),
    conteudo TEXT,
    status VARCHAR(20),  -- pendente, processando, processado
    criado_em TIMESTAMP
);

CREATE TABLE chunkdocumeto (
    id BIGSERIAL PRIMARY KEY,
    documento_id BIGINT REFERENCES documento(id),
    conteudo TEXT,
    embedding VECTOR(1536),  -- pgvector
    criado_em TIMESTAMP
);

-- Índice BM25 para busca lexical
CREATE INDEX bm25_index_conteudo 
ON chunkdocumeto 
USING bm25 (id, conteudo);

-- Usuários e Conversas
CREATE TABLE usuario (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(254) UNIQUE,
    name VARCHAR(150),
    password VARCHAR(128),
    is_staff BOOLEAN,
    is_active BOOLEAN
);

CREATE TABLE conversa (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT REFERENCES usuario(id),
    nome VARCHAR(50),
    criado_em TIMESTAMP
);

CREATE TABLE mensagem (
    id BIGSERIAL PRIMARY KEY,
    conversa_id BIGINT REFERENCES conversa(id),
    tipo_usuario VARCHAR(20),  -- USUARIO, ASSISTENTE
    conteudo TEXT,
    like BOOLEAN,
    criado_em TIMESTAMP
);
```

## 🔧 Sistema RAG

### Fluxo de Processamento de Documentos

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLUXO DE PROCESSAMENTO DE DOCUMENTOS                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│   Upload     │────▶│   Signal     │────▶│  Django-Q    │────▶│  Extração   │
│    PDF       │     │  post_save   │     │   Chain      │     │   PyPDF     │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬──────┘
                                                                       │
                                                                       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│   Busca      │◀────│   Salvar     │◀────│   OpenAI     │◀────│   Chunking  │
│   Pronto!    │     │   Postgres   │     │  Embeddings  │     │   1000/200  │
└──────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
```

### Fluxo de Pergunta/Resposta

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FLUXO DE PERGUNTA/RESPOSTA                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────────────────────────────┐
│   Pergunta   │────▶│           BUSCA HÍBRIDA              │
│   Usuário    │     │                                      │
└──────────────┘     │  ┌────────────┐    ┌─────────────┐   │
                     │  │   BM25     │    │  Semântica  │   │
                     │  │   (50%)    │    │   (50%)     │   │
                     │  └─────┬──────┘    └──────┬──────┘   │
                     │        │                  │          │
                     │        └────────┬─────────┘          │
                     │                 ▼                    │
                     │       Reciprocal Rank Fusion         │
                     └──────────────────┬───────────────────┘
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │         Top-K Chunks (12)            │
                     └──────────────────┬───────────────────┘
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │     Agno: especialista + revisor      │
                     │      (Streaming Response)             │
                     └──────────────────┬───────────────────┘
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │          Resposta Markdown           │
                     └──────────────────────────────────────┘
```

### Configurações do RAG

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| Chunk Size | 1000 | Tamanho de cada chunk em caracteres |
| Chunk Overlap | 200 | Sobreposição entre chunks |
| Embedding Model | text-embedding-3-small | Modelo OpenAI para embeddings |
| Embedding Dims | 1536 | Dimensões do vetor |
| Chat Model | Configurável por ambiente | Modelo usado pelos agentes Agno |
| BM25 Weight | 50% | Peso da busca lexical |
| Semantic Weight | 50% | Peso da busca vetorial |
| Top-K | 12 | Chunks retornados para contexto |

## 🐳 Infraestrutura

### Docker Compose

O projeto utiliza 5 serviços Docker:

| Serviço | Imagem | Porta | Descrição |
|---------|--------|-------|-----------|
| `web` | dev.Dockerfile | 8000 | Django application server |
| `qcluster` | dev.Dockerfile | - | Django-Q worker |
| `vite` | vite.Dockerfile | 5173 | Vite dev server (HMR) |
| `db` | paradedb/paradedb | 5432 | PostgreSQL + pgvector + BM25 |
| `pgadmin` | dpage/pgadmin4 | 5050 | Interface de administração DB |

### Dockerfiles

**`dev.Dockerfile`** (Backend)
```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm
WORKDIR /app
RUN uv sync --all-extras
```

**`vite.Dockerfile`** (Frontend)
```dockerfile
FROM node:20
WORKDIR /app
RUN npm install
```

### Volumes

| Volume | Descrição |
|--------|-----------|
| `app_shared` | Arquivos de media (PDFs) |
| `postgres_data` | Dados do PostgreSQL |
| `pgadmin_data` | Configurações pgAdmin |

## 🚀 Como Executar

### Pré-requisitos

- Docker e Docker Compose
- Chave de API OpenAI

### Configuração

1. Clone o repositório:
```bash
git clone <repo-url>
cd chatbot
```

2. Crie o arquivo `.env`:
```env
SECRET_KEY=sua-chave-secreta
DEBUG=True
OPENAI_API_KEY=sua-chave-openai
INTEGRACAR_CHAT_MODEL=gpt-6-luna
DATABASE_URL=postgres://postgres:postgres@db:5432/chatbot-integracar
```

3. Inicie os containers:
```bash
docker compose up -d
```

4. Execute as migrações:
```bash
docker compose exec web uv run python manage.py migrate
```

5. Crie um superusuário:
```bash
docker compose exec web uv run python manage.py createsuperuser
```

6. Acesse a aplicação:
- **Frontend**: http://localhost:8000
- **Admin Django**: http://localhost:8000/admin
- **pgAdmin**: http://localhost:5050

### Desenvolvimento

Para desenvolvimento com hot-reload:
```bash
docker compose watch
```

### Scripts Disponíveis (taskipy)

```bash
uv run task run              # Executa servidor Django
uv run task makemigrations   # Cria migrações
uv run task migrate          # Aplica migrações
uv run task collectstatic    # Coleta arquivos estáticos
uv run task createsuperuser  # Cria superusuário
uv run task lint             # Verifica código (ruff + djlint)
uv run task format           # Formata código
```

## 📁 Estrutura de Arquivos

```
chatbot/
├── apps/                      # Aplicações Django
│   ├── chat/                 # App do chatbot
│   └── contas/               # App de autenticação
├── core/                      # Configurações Django
├── frontend/                  # Frontend Vue.js
│   ├── js/                   # JavaScript/TypeScript
│   ├── css/                  # Estilos
│   └── public/               # Assets estáticos
├── docker-compose.yaml        # Orquestração de containers
├── dev.Dockerfile            # Dockerfile desenvolvimento
├── prod.Dockerfile           # Dockerfile produção
├── vite.Dockerfile           # Dockerfile Vite
├── pyproject.toml            # Dependências Python (uv)
├── package.json              # Dependências Node.js
├── vite.config.js            # Configuração Vite
├── tailwind.config.js        # Configuração Tailwind
└── manage.py                 # CLI Django
```

## 📝 Licença

Este projeto é privado e de uso interno do IntegraCAR.


## Deploy automático pelo GitHub Actions

O workflow `.github/workflows/deploy.yaml` publica pushes na branch **main** de
**ia-texto/chatbot** e permite execução manual em **Actions → Deploy to Production
→ Run workflow**. Os deploys são serializados.

O job `package` roda no GitHub, empacota somente os arquivos versionados necessários
ao build e publica um artefato com retenção de três dias. O job `deploy` roda no
servidor, baixa o artefato e executa `scripts/deploy.sh`, sem SSH e sem fazer
`git reset` no diretório de produção. Os secrets `SSH_*` não são usados por esse
workflow; não os remova se outros fluxos ainda dependerem deles.

O pacote é validado e extraído antes do build Docker. Após construir a imagem,
o script verifica o Django e aguarda o banco. Então para a aplicação e o
`qcluster`; o `/start` existente aplica migrations, coleta estáticos e inicia o
Gunicorn. O worker só é iniciado após o healthcheck HTTP da tela de login
responder 200. Falhas na inicialização exibem os logs e interrompem o deploy.
Há indisponibilidade entre a parada e a conclusão da inicialização; não há
rollback automático de banco ou aplicação.

### Configuração do servidor e do repositório

1. No repositório **ia-texto/chatbot**, registre um runner Linux x64 dedicado, com
   as labels `self-hosted`, `Linux`, `X64` e **`chatbot-production`**. Instale-o
   como serviço, usando um usuário com acesso a `sudo -n docker`. O runner do
   outro repositório não recebe jobs deste repositório automaticamente.
2. Crie o ambiente **production**, restrinja-o à branch **main** e configure a
   variável **`DEPLOY_PATH=/home/chatbot/chatbot`**, ajustando para o caminho real
   da instalação existente. O usuário do runner precisa escrever nesse diretório.
3. Preserve o `.env` de produção nesse diretório e a rede Docker externa `proxy`.
   Mantenha o mesmo diretório e nome de projeto Compose da instalação anterior
   para reutilizar os volumes `postgres_data`, `app_shared` e `static_volume`.
   Caso a instalação use `COMPOSE_PROJECT_NAME`, preserve também esse valor.
4. Verifique que Docker Compose suporta `up --wait --wait-timeout` e que há saída
   HTTPS para GitHub Actions, artefatos, registries Docker e dependências Python
   e npm. Habilite as atualizações automáticas do runner.

O workflow instala apenas `docker-compose.prod.yaml` e o pacote do commit no
diretório de produção. Não substitui o `.env` nem apaga volumes ou mídia. O código
local desse diretório deixa de ser atualizado por `git reset`; a imagem é
construída com o commit recebido pelo workflow.

Restrinja a escrita no repositório e proteja a branch `main`: esse runner tem
acesso à produção. Labels direcionam jobs, mas não restringem workflows, e a
proteção do ambiente só se aplica aos jobs que declaram `environment: production`.
Não execute código de PRs nesse runner.

### Runner instalado no Superintegra

O runner **superintegra-chatbot** está registrado em **IA-TEXTO/chatbot** com a
label `chatbot-production`, instalado em `/home/chatbot/actions-runner-chatbot`.
Executa como serviço systemd do usuário `chatbot`, com `Linger=yes` para iniciar
após reboot e continuar ativo sem sessão SSH. O ambiente `production` permite
somente a branch `main` e define `DEPLOY_PATH=/home/chatbot/chatbot`.

No servidor, como `chatbot`:

```bash
systemctl --user status actions.runner.chatbot.service
journalctl --user -u actions.runner.chatbot.service -n 100 --no-pager
systemctl --user restart actions.runner.chatbot.service
loginctl show-user chatbot -p Linger
```

O serviço fica em
`~/.config/systemd/user/actions.runner.chatbot.service`. As credenciais do runner
ficam somente no seu diretório de instalação; não copie esse diretório para o
repositório ou para artefatos de build.
