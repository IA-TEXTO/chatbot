# 🤖 Chatbot IntegraCAR

Um chatbot inteligente baseado em RAG (Retrieval-Augmented Generation) para o sistema IntegraCAR, desenvolvido com Django, Vue.js e LangChain.

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
5. **Filtro de domínio**: Restringe a busca a manuais, legislação ou ambos
6. **Orquestração Agno**: Faz triagem estruturada e seleciona especialistas
7. **Revisão**: Respostas legislativas e mistas passam por revisão de evidências

```python
@staticmethod
def top_k_resultados(query: str, k: int = 5, tipos=None):
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

Os especialistas podem consultar orientações canônicas, buscar até duas vezes mais
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
