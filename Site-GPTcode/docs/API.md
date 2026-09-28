# API REST do site GPTcode

Base: `/api/v1` (ex.: `http://localhost:5000/api/v1/` ou `https://gptcode-ifb.onrender.com/api/v1/`).
Coleção pronta para Postman/Insomnia: [`GPTcode-API.postman_collection.json`](GPTcode-API.postman_collection.json).

## Convenções

| Item | Regra |
|---|---|
| Formato | JSON (`Content-Type: application/json`). Rotas com imagem aceitam `multipart/form-data`. |
| Leitura (GET) | Pública para o conteúdo exibido no site. Mensagens, links, submissões, usuários e estatísticas exigem autenticação. |
| Escrita (POST/PUT/PATCH/DELETE) | Exige autenticação. |
| PUT × PATCH | `PUT` substitui o registro inteiro (campos omitidos viram `null`). `PATCH` altera só os campos enviados. |
| Ausência de valor | Sempre `null`, nunca string vazia. |
| Datas | `AAAA-MM-DD HH:MM:SS`, em UTC. |

### Autenticação

Escolha uma das opções:

1. **Token (para testes):** defina a variável de ambiente `API_TOKEN` no servidor e envie o cabeçalho
   `Authorization: Bearer <API_TOKEN>`.
2. **Sessão do painel:** depois do login em `/admin/login`, o navegador já está autenticado na API.

Sem autenticação, a escrita responde `401` com o cabeçalho `WWW-Authenticate: Bearer`.

### Códigos de resposta

| Código | Quando |
|---|---|
| 200 | Leitura ou alteração bem-sucedida (o corpo traz o registro atualizado). |
| 201 | Registro criado. O cabeçalho `Location` aponta para o novo recurso. |
| 204 | Remoção bem-sucedida (sem corpo). |
| 400 | JSON malformado ou corpo que não é um objeto. |
| 401 | Falta autenticação, ou o token é inválido. |
| 404 | Recurso inexistente. |
| 409 | Conflito: valor duplicado (título, e-mail, DOI…) ou registro em uso (ex.: categoria com membros). |
| 410 | Link de submissão inválido, expirado ou já utilizado (formulário HTML). |
| 422 | Regra de negócio violada. `campos` lista cada campo inválido. |

Formato de erro:

```json
{
  "erro": "Dados invalidos.",
  "campos": {
    "ano_fim": "O ano de termino nao pode ser anterior ao de inicio.",
    "modalidade": "Valor invalido. Use um de: PIBIC, PIBITI, TCC, EXTENSAO, OUTRO."
  }
}
```

## Recursos

| Recurso | Rotas | Observações |
|---|---|---|
| Índice | `GET /` | Lista os recursos disponíveis. |
| Categorias | `GET/POST /categorias`, `GET/PUT/PATCH/DELETE /categorias/{id}` | `DELETE` responde 409 se a categoria tiver membros. |
| Membros | `GET/POST /membros`, `GET/PUT/PATCH/DELETE /membros/{id}`, `PUT /membros/{id}/foto` | Filtros: `?categoria=<slug ou id>`, `?ativo=true/false` (este só com autenticação). Para o público, só aparecem os membros ativos, sem o e-mail. |
| Tags | `GET /tags` | Somente leitura: as tags vêm dos membros. |
| Projetos | `GET/POST /projetos`, `GET/PUT/PATCH/DELETE /projetos/{id}` | Filtros: `?status=`, `?modalidade=`. |
| Publicações | `GET/POST /publicacoes`, `GET/PUT/PATCH/DELETE /publicacoes/{id}` | Filtros: `?ano=`, `?tipo=`, `?projeto_id=`. Ordenadas por ano (mais recentes primeiro). |
| Contatos | `GET/POST /contatos`, `GET/PUT/PATCH/DELETE /contatos/{id}` | |
| Parceiros | `GET/POST /parceiros`, `GET/PUT/PATCH/DELETE /parceiros/{id}` | `POST` em multipart, com o arquivo no campo `logo`. |
| Slider | `GET/POST /slider`, `GET/PUT/PATCH/DELETE /slider/{id}` | `POST` em multipart, com o arquivo no campo `imagem`. |
| Configurações | `GET /configuracoes`, `PUT/PATCH /configuracoes` | Textos das páginas (chave → valor). |
| Destaque | `GET /destaque`, `PUT /destaque` | Item em destaque na página inicial. |
| Mensagens | `POST /mensagens` (público), `GET /mensagens`, `GET/PATCH/DELETE /mensagens/{id}` | Filtro: `?nao_lidas=1`. `PATCH {"lida": true}`. |
| Links | `GET /links`, `POST /links`, `DELETE /links/{id}` | Links de uso único para terceiros cadastrarem ou editarem. |
| Submissões | `GET /submissoes`, `GET /submissoes/{id}`, `POST /submissoes/{id}/aprovar`, `POST /submissoes/{id}/rejeitar` | Filtro: `?status=pendente|aprovada|rejeitada|todas`. |
| Usuários | `GET /usuarios` | Administradores que já acessaram o sistema (auditoria). |
| Estatísticas | `GET /estatisticas` | Contagens exibidas no dashboard. |

## Campos de entrada

### Categoria

| Campo | Tipo | Regra |
|---|---|---|
| `titulo` | texto | Obrigatório, até 80 caracteres, único. |
| `slug` | texto | Opcional: é gerado a partir do título. Minúsculas, números e hífen. Único. |
| `mensagem_vazia` | texto | Opcional. |
| `ordem_exibicao` | inteiro ≥ 0 | Opcional: sem ele, a categoria vai para o fim da lista. |

### Membro

| Campo | Tipo | Regra |
|---|---|---|
| `categoria_id` | inteiro | Obrigatório; a categoria precisa existir. |
| `nome` | texto | Obrigatório, de 3 a 120 caracteres. |
| `funcao` | texto | Até 80 caracteres. |
| `email` | e-mail | Opcional, único. Não é exibido publicamente. |
| `github_url` | texto | Aceita o usuário (`davirfb`) ou a URL; é salvo como `https://github.com/<usuario>`. |
| `lattes_url` | texto | Aceita a URL do CNPq ou o ID de 16 dígitos. |
| `descricao` | texto | Até 800 caracteres. |
| `tags` | lista ou texto | Até 10 tags de até 40 caracteres, separadas por vírgula. Duplicatas são ignoradas. |
| `ativo` | booleano | Padrão `true`; `false` oculta o membro no site. |
| `foto` | arquivo | Só por multipart (no `POST` ou em `PUT /membros/{id}/foto`). PNG, JPG, GIF ou WEBP, até 8 MB. |

### Projeto

| Campo | Tipo | Regra |
|---|---|---|
| `titulo` | texto | Obrigatório, de 5 a 200 caracteres, único (sem diferenciar maiúsculas). |
| `modalidade` | enum | `PIBIC`, `PIBITI`, `TCC`, `EXTENSAO`, `OUTRO`. Aceita também `PTCC/TCC` e `Outros`. |
| `status` | enum | `em_andamento` (padrão), `concluido`, `suspenso`. |
| `ano_inicio`, `ano_fim` | inteiro | Entre 2000 e 2100. `ano_fim` exige `ano_inicio` e não pode ser menor que ele. Projeto `concluido` exige `ano_fim`. |
| `orientador_id` | inteiro | Membro existente. |
| `descricao` | texto | Até 3000 caracteres. |
| `participantes` | lista ou texto | Aceita `[{"membro_id": 5}, {"nome": "Fulano", "papel": "colaborador"}, "Beltrano"]` ou texto com um nome por linha. Nomes iguais aos da equipe são vinculados ao membro automaticamente. Papéis: `estudante` (padrão), `coorientador`, `colaborador`. |

Resposta (resumida):

```json
{
  "id": 2,
  "titulo": "Game Based Learning (GBL) para o ensino de estrutura de dados",
  "modalidade": "PIBITI",
  "rotulo": "PIBITI 2025/2026",
  "status": "em_andamento",
  "ano_inicio": 2025,
  "ano_fim": 2026,
  "orientador": { "id": 1, "nome": "Prof. Dr. Dauster Souza Pereira" },
  "participantes": [
    { "id": 2, "membro_id": 14, "nome": "Mayara Vieira Martins Santos", "papel": "estudante" }
  ]
}
```

### Publicação

| Campo | Tipo | Regra |
|---|---|---|
| `titulo` | texto | Obrigatório, de 5 a 300 caracteres. O par título + ano é único. |
| `ano` | inteiro | Obrigatório, entre 1950 e o ano seguinte ao atual. |
| `tipo` | enum | `artigo` (padrão), `anais`, `capitulo`, `livro`, `resumo`, `dissertacao`, `tese`, `relatorio`, `outro`. |
| `autores` | lista ou texto | Obrigatório (ao menos 1), na ordem da citação. Aceita `["PEREIRA, Dauster"]`, `[{"nome": "...", "membro_id": 1}]` ou texto com um autor por linha. |
| `veiculo` | texto | Revista, evento ou editora. |
| `doi` | texto | Opcional e único. Aceita `10.xxxx/...` ou `https://doi.org/10.xxxx/...`. |
| `url` | URL | Opcional; `http(s)://`. |
| `projeto_id` | inteiro | Projeto de origem (opcional). |

### Contato

| Campo | Tipo | Regra |
|---|---|---|
| `tipo` | enum | `email`, `telefone`, `endereco`, `rede_social`, `site`, `outro`. |
| `titulo` | texto | Obrigatório. |
| `valor` | texto | Obrigatório. Se o tipo for `email`, precisa ser um e-mail válido. O par tipo + valor é único. |
| `subtitulo` | texto | Opcional. |
| `link` | texto | `http(s)://`, `mailto:` ou `tel:`. Para e-mail, o padrão é `mailto:<valor>`. |
| `icone` | texto | Classe do Bootstrap Icons (`bi-...`). O padrão depende do tipo. |

### Mensagem (formulário de contato)

`nome_remetente` (2 a 120 caracteres), `email_remetente` (e-mail válido), `assunto` (opcional, até 150), `mensagem` (10 a 5000).

### Configurações

Objeto com as chaves `hero_title`, `hero_subtitle`, `about_title`, `about_lead`, `about_description`,
`about_primary_button_text`, `about_primary_button_link`, `about_secondary_button_text`, `about_secondary_button_link`,
`partners_title`, `projects_page_title`, `projects_page_subtitle`, `projects_section_title`,
`publications_page_title`, `publications_page_subtitle`, `publications_section_title`, `team_page_title` e `team_page_subtitle`.
Chaves desconhecidas são rejeitadas. Os campos `*_link` aceitam apenas caminhos internos (`/equipe`) ou `http(s)://`.

### Destaque

`{"tipo": "projeto" | "publicacao" | "nenhum", "item_id": 3}`. Se o item for removido, o destaque é limpo automaticamente.

## Links de uso único (cadastro e edição por terceiros)

Fluxo:

1. O admin gera o link, pelo painel ou pela API:

   ```http
   POST /api/v1/links
   Authorization: Bearer <API_TOKEN>
   Content-Type: application/json

   {"recurso": "membro", "acao": "editar", "item_id": 5, "validade_dias": 7}
   ```

   Resposta `201`: `{"id": 1, "url": "https://.../submit/membro/<token>", "expira_em": "...", "situacao": "ativo", ...}`.
   O token aparece **só nesta resposta**; o banco guarda apenas o hash SHA-256 dele.
2. A pessoa abre a `url`, vê o formulário (já preenchido, no caso de edição) e envia. Se houver erro, o formulário indica
   o campo e o link **continua válido**. Conflitos, como um título que já existe, também são detectados nesse momento.
3. O envio cria uma submissão `pendente` e consome o link. Uma segunda abertura responde `410`.
4. O admin revisa a submissão em `/admin/pending`, que compara campo a campo o valor atual com o enviado, ou em
   `GET /api/v1/submissoes`. Depois, **aprova** (os dados são validados de novo e publicados) ou **rejeita**.

Regras garantidas pelo banco: cada link gera no máximo uma submissão, e o tipo do alvo precisa bater com o recurso.
Um link de edição é apagado junto com o item que ele edita.

## Exemplos com curl

```bash
export API=http://localhost:5000/api/v1
export TOKEN="Authorization: Bearer $API_TOKEN"

curl $API/projetos
curl -X POST $API/projetos -H "$TOKEN" -H "Content-Type: application/json" \
     -d '{"titulo":"Realidade Aumentada e Tabagismo","modalidade":"TCC","orientador_id":1,"participantes":["Luiz Fernando de Souza Dobbin"]}'
curl -X PATCH $API/projetos/4 -H "$TOKEN" -H "Content-Type: application/json" -d '{"status":"concluido","ano_inicio":2025,"ano_fim":2026}'
curl -X DELETE $API/projetos/4 -H "$TOKEN" -i
curl -X POST $API/membros -H "$TOKEN" -F categoria_id=2 -F nome="Nova Integrante" -F tags="IA, Web" -F foto=@foto.jpg
```

## Testes automatizados

```bash
cd Site-GPTcode
pip install -r requirements-dev.txt
python -m pytest
```

A suíte (`tests/`) cobre:

- o CRUD de cada recurso e os códigos de resposta;
- as regras de negócio e as restrições do schema;
- o fluxo completo dos links de uso único;
- os formulários do painel;
- a migração do banco antigo.
