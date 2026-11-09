## Guia de integração para frontend

Esta documentação é pública e descreve o código atual. Isso não torna todos os
recursos anônimos nem significa que a integração externa já está completa.
Swagger: `/api/docs`; contrato OpenAPI: `/api/openapi.json`.
Os endereços ficam disponíveis no servidor após publicar esta versão.

### Endereço e acesso

Use a origem da instalação seguida de `/api`, por exemplo
`http://localhost:8000/api` em desenvolvimento. As rotas da API não têm barra
final. Envie corpos JSON com `Content-Type: application/json`.
A versão `1.0.0` identifica o contrato; ainda não existe prefixo `/api/v1`.

O chat permite perguntas anônimas. Para vincular conversas a uma conta, é
necessária uma sessão Django existente, criada pela tela `/contas/entrar/`.
O login atual é um fluxo de tela com redirecionamentos, não um endpoint JSON de
autenticação. Não há suporte a `Authorization: Bearer`, API key, OAuth ou JWT.
O download de fontes e a renomeação exigem a sessão do proprietário; skills
exigem usuário da equipe (`is_staff`).

Para um frontend em outra origem, esta aplicação ainda não configura CORS.
`credentials: 'include'` sozinho não resolve: o servidor deve permitir a origem
explicitamente e o uso de credenciais, e os cookies precisam ser compatíveis
com a implantação. `CSRF_TRUSTED_ORIGINS` não habilita CORS.
A integração viável com a configuração atual usa a mesma origem, por exemplo um
proxy reverso para `/api` e o login existente. Não coloque credenciais de serviço
ou a chave do provedor de IA no JavaScript do navegador.

Há pendências de isolamento de conversas anônimas e de autorização de operações
legadas. O acesso anônimo atual não oferece isolamento por visitante; não o use
para histórico confidencial. A autenticação, o isolamento e a proteção CSRF das
operações que usam sessão precisam ser consolidados antes de ampliar a exposição.

### Endpoints existentes

Todos os caminhos da tabela são relativos a `/api`.

| Método | Caminho | Uso e acesso atual |
| --- | --- | --- |
| POST | `/chat` | Enviar pergunta; aceita acesso anônimo ou sessão |
| PATCH | `/conversas/{id_conversa}` | Renomear; sessão do proprietário |
| PATCH | `/mensagens/{id_mensagem}/curtir` | Avaliar; autorização por proprietário ainda pendente |
| GET | `/mensagens/{id_mensagem}/documentos/{id_documento}/arquivo` | PDF de fonte recuperada; sessão do proprietário |
| GET | `/documentos/{id_documento}/status` | Status; atualmente sem exigência de login |
| PATCH | `/documentos/{id_documento}/tipo` | Administração legada; correções pendentes, não integrar |
| GET | `/skills/{id_skill}` | Consultar skill; equipe |
| PUT | `/skills/{id_skill}` | Editar skill; equipe |
| PATCH | `/skills/{id_skill}/status` | Ativar/desativar skill; equipe |

### Enviar e continuar uma conversa

Uma primeira pergunta cria a conversa e duas mensagens persistidas:

```bash
curl --fail-with-body http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"mensagem":"Como iniciar o CAR?","stream":false}'
```

Exemplo ilustrativo de resposta HTTP 200:

```json
{
  "id_conversa": 10,
  "id_mensagem_pergunta": 21,
  "id_mensagem_resposta": 22,
  "resposta": "Consulte o manual [Fonte 1].",
  "fontes": [
    {
      "numero": 1,
      "documento_id": 5,
      "nome": "Manual.pdf",
      "tipo": "manual",
      "trecho": "Trecho recuperado do documento."
    }
  ],
  "skill": ""
}
```

`resposta` contém Markdown. `fontes` pode ser vazio e contém os trechos recuperados,
que não necessariamente foram todos citados. `numero` corresponde à referência
`[Fonte N]` nessa resposta, não a um identificador global. `tipo` identifica o
documento (`manual` ou `legislacao`). `skill` é o nome da skill usada ou `""`.

Use os IDs efetivamente recebidos para continuar:

```json
{
  "mensagem": "E quais documentos preciso apresentar?",
  "id_conversa": 10,
  "id_mensagem_pai": 22,
  "stream": false
}
```

`id_mensagem_pai` deve ser uma mensagem do **assistente** da mesma conversa.
Ele seleciona a ramificação cujo histórico será enviado à IA. Omiti-lo inicia
uma nova raiz, mesmo quando `id_conversa` foi informado: o servidor não escolhe
automaticamente a última mensagem. Sem `id_conversa`, o servidor cria outra
conversa; omita também os IDs de mensagens nesse caso.

Para editar uma pergunta, envie `id_conversa`, a nova `mensagem` e
`id_mensagem_editada` com o ID da pergunta do **usuário**. Isso cria outra versão
e outra resposta, preservando a anterior. O pai da pergunta original é
reutilizado e `id_mensagem_pai`, se enviado junto, é ignorado.

### Streaming NDJSON

Envie `stream: true` no mesmo endpoint. A resposta é
`application/x-ndjson; charset=utf-8`, com um objeto JSON por linha. Não é SSE e
não usa `EventSource`. Para testar, acrescente `--no-buffer` ao curl.

| Evento | Formato | Como consumir |
| --- | --- | --- |
| Primeira linha (sem `tipo`) | IDs da conversa, pergunta e resposta | Guardar para continuidade |
| `progresso` | `{"tipo":"progresso","conteudo":"Analisando..."}` | Atualizar indicador; pode se repetir durante a espera |
| `skill` | `{"tipo":"skill","conteudo":"nome-da-skill"}` | Guardar skill, quando houver |
| `trecho` | `{"tipo":"trecho","conteudo":"texto"}` | Acrescentar ao texto provisório |
| `resposta_final` | `{"tipo":"resposta_final","conteudo":"texto completo"}` | Substituir todo o texto provisório |
| `fontes` | `{"tipo":"fontes","fontes":[]}` | Atualizar fontes; último evento do fluxo concluído |

Os blocos de rede podem dividir uma linha JSON ou conter várias linhas. Use um
buffer e um decodificador UTF-8 incremental. Exemplo para mesma origem, com sessão
se disponível:

```javascript
async function perguntar(payload, onEvento, signal) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, stream: true }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  if (!response.body) throw new Error('Streaming indisponível');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalRecebido = false;
  let fontesRecebidas = false;
  function emitir(linha) {
    if (!linha.trim()) return;
    const evento = JSON.parse(linha);
    if (evento.tipo === 'resposta_final') finalRecebido = true;
    if (evento.tipo === 'fontes') fontesRecebidas = true;
    onEvento(evento);
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      const linhas = buffer.split('\n');
      buffer = linhas.pop() ?? '';
      for (const linha of linhas) emitir(linha);
      if (done) break;
    }
    emitir(buffer);
    if (!finalRecebido || !fontesRecebidas) {
      throw new Error('Resposta interrompida antes de concluir o protocolo');
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
```

Sanitize o HTML resultante ao renderizar Markdown. O contrato atual não possui
evento de erro estruturado: se a geração falhar após o início do streaming,
a conexão já tem HTTP 200 e pode emitir `resposta_final` com uma mensagem de
indisponibilidade, seguida pelo fechamento normal com `fontes: []`. Pode haver
mais de um `resposta_final`; o último prevalece. Conclusão do protocolo não
comprova sucesso da IA. Não diferencie sucesso e falha apenas pelo status HTTP.

Cancelar o `fetch` interrompe o consumo no navegador; não há endpoint que confirme
o cancelamento da geração nem garantia de persistência após desconexão.
Também não há retomada do stream nem chave de idempotência. Reenviar a mesma
pergunta pode criar mensagens duplicadas e cobrar outra geração.

### Renomear, avaliar e abrir fontes

`PATCH /conversas/10` recebe `{"nome":"Minha consulta"}` e retorna
`{"id":10,"nome":"Minha consulta"}`. O nome é aparado e deve ter entre 1 e
50 caracteres após essa limpeza. Anônimos recebem 403; conversa indisponível
para o usuário retorna 404.

`PATCH /mensagens/22/curtir` recebe `{"curtido":true}`, `false` ou `null`
(remover avaliação) e retorna o mesmo campo. Esse endpoint ainda precisa de
verificação de propriedade antes de ser oferecido a clientes externos.

`GET /mensagens/22/documentos/5/arquivo` retorna `application/pdf` com sessão do
proprietário. O documento precisa constar nas fontes salvas da resposta. Sem
login retorna 403; mensagem de outro usuário ou documento fora das fontes retorna
404. Não construa URLs diretas de `/media` para contornar essa verificação.

### Documentos e skills

`GET /documentos/5/status` retorna `{"status":"processado"}`. Os valores são
`pendente`, `processando`, `processado` e `erro`. Não há endpoint JSON de upload
ou listagem de documentos. A alteração de tipo recebe `{"tipo":"manual"}` ou
`{"tipo":"legislacao"}`, mas a implementação legada salva e tenta retornar um
erro sem contrato de resposta correspondente; precisa de correção antes do uso.

As operações de skills são administrativas. `GET /skills/1` retorna `id`, `nome`,
`arquivo`, `titulo`, `status`, `conteudo`, `observacoes`, `arquivo_origem` (URL ou
null) e `arquivos_origem` (lista de objetos com `nome` e `url`).
`PUT /skills/1` recebe `{"conteudo":"..."}` com Markdown e cabeçalho válido
(`titulo`, `descricao`, `rotas`); `PATCH /skills/1/status` recebe `{"ativa":true}`
ou `false`. Ambas retornam a skill atualizada. Exigem equipe (403), retornam
404 para ID inexistente e 400 para conteúdo inválido ou skill em geração/erro.

### Erros e limitações do contrato

| HTTP | Situação |
| --- | --- |
| 200 | Resposta JSON completa ou início de streaming; verificar também os eventos |
| 400 | Pergunta vazia: `{"resposta":"Mensagem vazia"}`; outras operações podem retornar `detail` |
| 403 | Sessão/permissão insuficiente nas operações que a verificam |
| 404 | Recurso não encontrado nas operações que usam essa validação |
| 422 | Corpo JSON/campos inválidos; `detail` contém os erros de validação |
| 503 | Falha conhecida do provedor no modo sem streaming; inclui `resposta` e os três IDs |

O contrato ainda não padroniza todos os erros: uma conversa inexistente ou
inacessível em `/chat` pode produzir 500; falhas inesperadas também podem produzir
500. Fora do streaming, o tratamento 503 cobre erros conhecidos do provedor.
Não repita automaticamente um POST após erro de rede/500/503: mensagens podem
já ter sido criadas. Ainda não há limite de requisições na camada da API nem
resposta 429 implementada por ela.

### Recursos que ainda faltam para um frontend independente

Os caminhos abaixo são propostas, **não estão implementados**:

| Prioridade | Contrato proposto | Objetivo |
| --- | --- | --- |
| Essencial | Autenticação JSON ou integração OIDC com o sistema consumidor; `/api/auth/me` e logout | Identificar usuário, expiração e permissões sem depender das telas |
| Essencial | `GET /api/conversas?busca=...&limit=...&offset=...` | Histórico do usuário com busca e paginação |
| Essencial | `GET /api/conversas/{id}` e/ou `GET /api/conversas/{id}/mensagens` | Recuperar mensagens, fontes, avaliações e relações pai/filhas |
| Essencial | `DELETE /api/conversas/{id}` | Excluir conversa com autorização do proprietário |
| Essencial | Estado de geração (`pendente`, `gerando`, `concluida`, `erro`, `cancelada`) e consulta por ID | Recuperar a interface após falha, atualização ou reconexão |
| Recomendado | `GET /api/conversas/{id}/exportar?ultima_mensagem=...` | Exportar uma ramificação sem fluxo de tela |
| Recomendado | Cancelamento de geração e idempotência no POST | Controlar custo e evitar duplicação ao tentar novamente |
| Operacional | `/api/health` e `/api/ready` sem dados sensíveis | Monitorar aplicação e disponibilidade de dependências |

`POST /chat` já cria conversas; um `POST /conversas` separado é opcional.
Edição de perguntas e avaliação já têm rotas, portanto não precisam de outro
endpoint para a mesma função. A exportação já existe em
`GET /c/{id}/exportar/?ultima_mensagem={id}`, mas depende de sessão e pode
redirecionar ao login. A listagem e o detalhe atuais dependem de Inertia, e a
exclusão usa um POST de tela com redirecionamento.

Antes de disponibilizar a integração, priorize autorização por proprietário em
todas as operações, isolamento do visitante anônimo, proteção dos arquivos,
CORS/CSRF adequados à autenticação escolhida, limites de uso e erros padronizados.
Upload, exclusão de documentos e gestão de skills devem continuar como funções
de administração, com permissões próprias; não são necessários ao frontend que
apenas conversa.

Referências de implementação:
[Django Ninja: respostas e status](https://django-ninja.dev/guide/responses/),
[Django Ninja: CSRF](https://django-ninja.dev/guide/csrf/),
[MDN: CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS).
