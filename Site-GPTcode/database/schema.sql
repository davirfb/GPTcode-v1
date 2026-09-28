-- =====================================================================
-- GPTcode - Site Institucional do Grupo de Pesquisa
-- Modelo Fisico v2 - SGBD: SQLite 3 (>= 3.38, com JSON1)
-- Projeto Integrador III - TSI/IFB - 2026.2
--
-- Regras gerais adotadas:
--   * toda tabela tem chave primaria; entidades usam INTEGER AUTOINCREMENT
--   * ausencia de valor e representada por NULL (nunca por string vazia)
--   * atributos categorizados sao restritos por CHECK ... IN (...)
--   * toda chave estrangeira declara politica de exclusao
--   * nenhum atributo multivalorado (1FN): listas viram tabelas associativas
--   * nomes em snake_case, minusculos e sem acentuacao
--
-- A conexao da aplicacao executa PRAGMA foreign_keys = ON a cada abertura.
-- =====================================================================

-- ---------------------------------------------------------------------
-- usuario: administradores que acessaram o painel ou a API (RF007).
-- A autenticacao e feita pelo Firebase (Google); aqui fica o registro
-- usado para auditoria (criado_por / atualizado_por).
-- ---------------------------------------------------------------------
CREATE TABLE usuario (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nome              TEXT    NOT NULL CHECK (length(trim(nome)) > 0),
    email             TEXT    NOT NULL UNIQUE COLLATE NOCASE
                              CHECK (email LIKE '_%@_%._%'),
    perfil            TEXT    NOT NULL DEFAULT 'admin'
                              CHECK (perfil IN ('admin', 'editor', 'api')),
    ativo             INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em         TEXT    NOT NULL DEFAULT (datetime('now')),
    ultimo_acesso_em  TEXT
);

-- ---------------------------------------------------------------------
-- configuracao: textos editaveis das paginas (chave/valor).
-- ---------------------------------------------------------------------
CREATE TABLE configuracao (
    chave           TEXT    PRIMARY KEY
                            CHECK (chave GLOB '[a-z]*' AND chave NOT GLOB '*[^a-z0-9_]*'),
    valor           TEXT    NOT NULL DEFAULT '',
    atualizado_em   TEXT    NOT NULL DEFAULT (datetime('now')),
    atualizado_por  INTEGER REFERENCES usuario(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- categoria_membro: secoes da pagina Equipe.
-- ---------------------------------------------------------------------
CREATE TABLE categoria_membro (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT    NOT NULL UNIQUE
                            CHECK (slug GLOB '[a-z]*' AND slug NOT GLOB '*[^a-z0-9-]*'),
    titulo          TEXT    NOT NULL UNIQUE COLLATE NOCASE
                            CHECK (length(trim(titulo)) > 0),
    mensagem_vazia  TEXT    NOT NULL DEFAULT 'Nenhum membro por enquanto',
    ordem_exibicao  INTEGER NOT NULL DEFAULT 0 CHECK (ordem_exibicao >= 0)
);

-- ---------------------------------------------------------------------
-- membro: integrantes do grupo (RF005, RF010).
-- ---------------------------------------------------------------------
CREATE TABLE membro (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria_id    INTEGER NOT NULL
                            REFERENCES categoria_membro(id) ON DELETE RESTRICT,
    nome            TEXT    NOT NULL CHECK (length(trim(nome)) >= 3),
    funcao          TEXT,
    email           TEXT    UNIQUE COLLATE NOCASE
                            CHECK (email IS NULL OR email LIKE '_%@_%._%'),
    github_url      TEXT    CHECK (github_url IS NULL OR github_url LIKE 'https://github.com/_%'),
    lattes_url      TEXT    CHECK (lattes_url IS NULL
                                   OR lattes_url LIKE 'http://%cnpq.br/_%'
                                   OR lattes_url LIKE 'https://%cnpq.br/_%'),
    descricao       TEXT,
    foto            TEXT,
    ativo           INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    ordem_exibicao  INTEGER NOT NULL DEFAULT 0 CHECK (ordem_exibicao >= 0),
    criado_em       TEXT    NOT NULL DEFAULT (datetime('now')),
    atualizado_em   TEXT    NOT NULL DEFAULT (datetime('now')),
    atualizado_por  INTEGER REFERENCES usuario(id) ON DELETE SET NULL
);

-- tag + membro_tag: areas de interesse (antes um JSON dentro de membro).
CREATE TABLE tag (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome  TEXT    NOT NULL UNIQUE COLLATE NOCASE
                  CHECK (length(trim(nome)) BETWEEN 1 AND 40)
);

CREATE TABLE membro_tag (
    membro_id  INTEGER NOT NULL REFERENCES membro(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tag(id)    ON DELETE CASCADE,
    ordem      INTEGER NOT NULL DEFAULT 0 CHECK (ordem >= 0),
    PRIMARY KEY (membro_id, tag_id)
);

-- ---------------------------------------------------------------------
-- projeto: projetos de pesquisa (RF003, RF008).
-- O antigo "badge" ("PIBIC 2025/2026") foi decomposto em modalidade +
-- ano_inicio/ano_fim; o rotulo exibido e derivado na aplicacao.
-- ---------------------------------------------------------------------
CREATE TABLE projeto (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo          TEXT    NOT NULL UNIQUE COLLATE NOCASE
                            CHECK (length(trim(titulo)) >= 5),
    modalidade      TEXT    NOT NULL
                            CHECK (modalidade IN ('PIBIC', 'PIBITI', 'TCC', 'EXTENSAO', 'OUTRO')),
    status          TEXT    NOT NULL DEFAULT 'em_andamento'
                            CHECK (status IN ('em_andamento', 'concluido', 'suspenso')),
    ano_inicio      INTEGER CHECK (ano_inicio IS NULL OR ano_inicio BETWEEN 2000 AND 2100),
    ano_fim         INTEGER CHECK (ano_fim IS NULL OR ano_fim BETWEEN 2000 AND 2100),
    descricao       TEXT,
    orientador_id   INTEGER REFERENCES membro(id) ON DELETE RESTRICT,
    ordem_exibicao  INTEGER NOT NULL DEFAULT 0 CHECK (ordem_exibicao >= 0),
    criado_em       TEXT    NOT NULL DEFAULT (datetime('now')),
    atualizado_em   TEXT    NOT NULL DEFAULT (datetime('now')),
    criado_por      INTEGER REFERENCES usuario(id) ON DELETE SET NULL,
    atualizado_por  INTEGER REFERENCES usuario(id) ON DELETE SET NULL,
    -- regra de negocio: o fim nao pode anteceder o inicio
    CHECK (ano_fim IS NULL OR (ano_inicio IS NOT NULL AND ano_fim >= ano_inicio)),
    -- regra de negocio: projeto concluido precisa do ano de encerramento
    CHECK (status <> 'concluido' OR ano_fim IS NOT NULL)
);

-- projeto_participante: estudantes/colaboradores de cada projeto (N:N).
-- Um participante e OU um membro cadastrado (membro_id) OU uma pessoa
-- externa (nome_externo) -- nunca os dois, nunca nenhum.
CREATE TABLE projeto_participante (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id    INTEGER NOT NULL REFERENCES projeto(id) ON DELETE CASCADE,
    membro_id     INTEGER REFERENCES membro(id) ON DELETE SET NULL,
    nome_externo  TEXT    CHECK (nome_externo IS NULL OR length(trim(nome_externo)) >= 3),
    papel         TEXT    NOT NULL DEFAULT 'estudante'
                          CHECK (papel IN ('estudante', 'coorientador', 'colaborador')),
    ordem         INTEGER NOT NULL DEFAULT 0 CHECK (ordem >= 0),
    CHECK ((membro_id IS NULL) <> (nome_externo IS NULL)),
    UNIQUE (projeto_id, membro_id),
    UNIQUE (projeto_id, nome_externo)
);

-- ---------------------------------------------------------------------
-- publicacao: producao academica (RF004, RF009).
-- ---------------------------------------------------------------------
CREATE TABLE publicacao (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo          TEXT    NOT NULL COLLATE NOCASE CHECK (length(trim(titulo)) >= 5),
    ano             INTEGER NOT NULL CHECK (ano BETWEEN 1950 AND 2100),
    tipo            TEXT    NOT NULL DEFAULT 'artigo'
                            CHECK (tipo IN ('artigo', 'anais', 'capitulo', 'livro', 'resumo',
                                            'dissertacao', 'tese', 'relatorio', 'outro')),
    veiculo         TEXT,
    doi             TEXT    UNIQUE CHECK (doi IS NULL OR doi LIKE '10.%/%'),
    url             TEXT    CHECK (url IS NULL OR url LIKE 'http://%' OR url LIKE 'https://%'),
    projeto_id      INTEGER REFERENCES projeto(id) ON DELETE SET NULL,
    ordem_exibicao  INTEGER NOT NULL DEFAULT 0 CHECK (ordem_exibicao >= 0),
    criado_em       TEXT    NOT NULL DEFAULT (datetime('now')),
    atualizado_em   TEXT    NOT NULL DEFAULT (datetime('now')),
    criado_por      INTEGER REFERENCES usuario(id) ON DELETE SET NULL,
    atualizado_por  INTEGER REFERENCES usuario(id) ON DELETE SET NULL,
    -- regra de negocio: a mesma obra nao e cadastrada duas vezes no mesmo ano
    UNIQUE (titulo, ano)
);

-- publicacao_autor: autores na ordem da citacao (N:N com membro opcional).
-- nome_citacao e o nome como aparece na referencia ("PEREIRA, Dauster S."),
-- atributo proprio da autoria e nao uma copia de membro.nome.
CREATE TABLE publicacao_autor (
    publicacao_id  INTEGER NOT NULL REFERENCES publicacao(id) ON DELETE CASCADE,
    ordem          INTEGER NOT NULL CHECK (ordem > 0),
    nome_citacao   TEXT    NOT NULL CHECK (length(trim(nome_citacao)) >= 2),
    membro_id      INTEGER REFERENCES membro(id) ON DELETE SET NULL,
    PRIMARY KEY (publicacao_id, ordem),
    UNIQUE (publicacao_id, membro_id)
);

-- ---------------------------------------------------------------------
-- contato: canais exibidos na pagina Contato (RF006, RF011).
-- ---------------------------------------------------------------------
CREATE TABLE contato (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT    NOT NULL
                            CHECK (tipo IN ('email', 'telefone', 'endereco', 'rede_social', 'site', 'outro')),
    titulo          TEXT    NOT NULL CHECK (length(trim(titulo)) > 0),
    valor           TEXT    NOT NULL CHECK (length(trim(valor)) > 0),
    subtitulo       TEXT,
    link            TEXT    CHECK (link IS NULL OR link LIKE 'http://%' OR link LIKE 'https://%'
                                   OR link LIKE 'mailto:%' OR link LIKE 'tel:%'),
    icone           TEXT    NOT NULL DEFAULT 'bi-chat-dots-fill' CHECK (icone GLOB 'bi-[a-z0-9]*'),
    ordem_exibicao  INTEGER NOT NULL DEFAULT 0 CHECK (ordem_exibicao >= 0),
    atualizado_em   TEXT    NOT NULL DEFAULT (datetime('now')),
    atualizado_por  INTEGER REFERENCES usuario(id) ON DELETE SET NULL,
    CHECK (tipo <> 'email' OR valor LIKE '_%@_%._%'),
    UNIQUE (tipo, valor)
);

-- mensagem_contato: mensagens do formulario publico (RF006).
CREATE TABLE mensagem_contato (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_remetente   TEXT    NOT NULL CHECK (length(trim(nome_remetente)) >= 2),
    email_remetente  TEXT    NOT NULL CHECK (email_remetente LIKE '_%@_%._%'),
    assunto          TEXT,
    mensagem         TEXT    NOT NULL CHECK (length(trim(mensagem)) BETWEEN 1 AND 5000),
    lida             INTEGER NOT NULL DEFAULT 0 CHECK (lida IN (0, 1)),
    recebida_em      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- Pagina inicial: slider, parceiros e destaque.
-- ---------------------------------------------------------------------
CREATE TABLE slider_imagem (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    imagem             TEXT    NOT NULL UNIQUE,
    texto_alternativo  TEXT    NOT NULL CHECK (length(trim(texto_alternativo)) > 0),
    ordem_exibicao     INTEGER NOT NULL DEFAULT 0 CHECK (ordem_exibicao >= 0)
);

CREATE TABLE parceiro (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT    NOT NULL UNIQUE COLLATE NOCASE CHECK (length(trim(nome)) > 0),
    link            TEXT    CHECK (link IS NULL OR link LIKE 'http://%' OR link LIKE 'https://%'),
    logo            TEXT    NOT NULL,
    ordem_exibicao  INTEGER NOT NULL DEFAULT 0 CHECK (ordem_exibicao >= 0)
);

-- destaque: linha unica (id = 1) que aponta para no maximo UM item.
-- Substitui o par (tipo, item_id) em texto, que nao tinha integridade
-- referencial: agora, se o item for removido, o destaque e limpo.
CREATE TABLE destaque (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    projeto_id     INTEGER REFERENCES projeto(id)    ON DELETE SET NULL,
    publicacao_id  INTEGER REFERENCES publicacao(id) ON DELETE SET NULL,
    CHECK (projeto_id IS NULL OR publicacao_id IS NULL)
);

-- ---------------------------------------------------------------------
-- Links de uso unico para cadastro/edicao por terceiros + submissoes.
-- (antes em arquivos JSON, que se perdiam a cada deploy)
-- ---------------------------------------------------------------------
CREATE TABLE link_submissao (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash     TEXT    NOT NULL UNIQUE CHECK (length(token_hash) = 64),
    recurso        TEXT    NOT NULL CHECK (recurso IN ('projeto', 'publicacao', 'membro')),
    acao           TEXT    NOT NULL CHECK (acao IN ('criar', 'editar')),
    projeto_id     INTEGER REFERENCES projeto(id)    ON DELETE CASCADE,
    publicacao_id  INTEGER REFERENCES publicacao(id) ON DELETE CASCADE,
    membro_id      INTEGER REFERENCES membro(id)     ON DELETE CASCADE,
    criado_por     INTEGER REFERENCES usuario(id)    ON DELETE SET NULL,
    criado_em      TEXT    NOT NULL DEFAULT (datetime('now')),
    expira_em      TEXT    NOT NULL,
    usado_em       TEXT,
    -- o alvo precisa ser do mesmo tipo do recurso
    CHECK ((recurso = 'projeto'    AND publicacao_id IS NULL AND membro_id IS NULL)
        OR (recurso = 'publicacao' AND projeto_id IS NULL    AND membro_id IS NULL)
        OR (recurso = 'membro'     AND projeto_id IS NULL    AND publicacao_id IS NULL)),
    -- link de criacao nao tem alvo; link de edicao obrigatoriamente tem
    CHECK ((acao = 'criar') = (coalesce(projeto_id, publicacao_id, membro_id) IS NULL)),
    CHECK (expira_em > criado_em)
);

-- submissao: dados enviados por um link, aguardando validacao do admin.
-- link_id UNIQUE garante no banco que cada link gera no maximo 1 envio.
CREATE TABLE submissao (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id       INTEGER NOT NULL UNIQUE REFERENCES link_submissao(id) ON DELETE CASCADE,
    dados         TEXT    NOT NULL CHECK (json_valid(dados)),
    status        TEXT    NOT NULL DEFAULT 'pendente'
                          CHECK (status IN ('pendente', 'aprovada', 'rejeitada')),
    enviada_em    TEXT    NOT NULL DEFAULT (datetime('now')),
    avaliada_em   TEXT,
    avaliada_por  INTEGER REFERENCES usuario(id) ON DELETE SET NULL,
    CHECK ((status = 'pendente') = (avaliada_em IS NULL))
);

-- =====================================================================
-- Gatilhos
-- =====================================================================

-- Ao remover um membro, os vinculos com projetos viram participantes
-- externos com o mesmo nome: o historico do projeto nao se perde.
CREATE TRIGGER trg_membro_preserva_participacao
BEFORE DELETE ON membro
BEGIN
    UPDATE projeto_participante
       SET nome_externo = OLD.nome, membro_id = NULL
     WHERE membro_id = OLD.id;
END;

-- Manutencao automatica de atualizado_em.
CREATE TRIGGER trg_membro_atualizado AFTER UPDATE ON membro
WHEN NEW.atualizado_em = OLD.atualizado_em
BEGIN
    UPDATE membro SET atualizado_em = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_projeto_atualizado AFTER UPDATE ON projeto
WHEN NEW.atualizado_em = OLD.atualizado_em
BEGIN
    UPDATE projeto SET atualizado_em = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_publicacao_atualizado AFTER UPDATE ON publicacao
WHEN NEW.atualizado_em = OLD.atualizado_em
BEGIN
    UPDATE publicacao SET atualizado_em = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_contato_atualizado AFTER UPDATE ON contato
WHEN NEW.atualizado_em = OLD.atualizado_em
BEGIN
    UPDATE contato SET atualizado_em = datetime('now') WHERE id = NEW.id;
END;

-- Tags sem nenhum membro sao removidas.
CREATE TRIGGER trg_tag_orfa AFTER DELETE ON membro_tag
BEGIN
    DELETE FROM tag
     WHERE id = OLD.tag_id
       AND NOT EXISTS (SELECT 1 FROM membro_tag WHERE tag_id = OLD.tag_id);
END;

-- =====================================================================
-- Indices (consultas das paginas publicas e chaves estrangeiras)
-- =====================================================================
CREATE INDEX idx_membro_categoria        ON membro (categoria_id, ativo, ordem_exibicao);
CREATE INDEX idx_membro_tag_tag          ON membro_tag (tag_id);
CREATE INDEX idx_projeto_listagem        ON projeto (status, ordem_exibicao);
CREATE INDEX idx_projeto_orientador      ON projeto (orientador_id);
CREATE INDEX idx_participante_membro     ON projeto_participante (membro_id);
CREATE INDEX idx_publicacao_ano          ON publicacao (ano DESC, ordem_exibicao);
CREATE INDEX idx_publicacao_projeto      ON publicacao (projeto_id);
CREATE INDEX idx_autor_membro            ON publicacao_autor (membro_id);
CREATE INDEX idx_mensagem_lida           ON mensagem_contato (lida, recebida_em DESC);
CREATE INDEX idx_submissao_status        ON submissao (status, enviada_em DESC);
CREATE INDEX idx_link_projeto            ON link_submissao (projeto_id);
CREATE INDEX idx_link_publicacao         ON link_submissao (publicacao_id);
CREATE INDEX idx_link_membro             ON link_submissao (membro_id);

INSERT INTO destaque (id) VALUES (1);

PRAGMA user_version = 2;
