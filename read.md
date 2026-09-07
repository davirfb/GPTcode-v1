# CLAUDE.md — Guia do Projeto GPTCode

## O que é este projeto

Site oficial do **GPTCode** — Grupo de Pesquisa em Tecnologias Computacionais do Instituto Federal de Brasília (IFB). É uma aplicação web full-stack desenvolvida por alunos do curso de TSI como Projeto Integrador.

## Estrutura de diretórios

```
2025-2-vespertino-pi1-g3-2025-2-main/   ← raiz do workspace
└── Site-GPTcode/                         ← projeto Flask (trabalhe aqui)
    ├── backend/
    │   ├── app.py                        ← aplicação Flask principal (35 rotas)
    │   ├── content_manager.py            ← leitura/escrita do JSON de conteúdo
    │   └── data/site_content.json        ← "banco de dados" do site (JSON)
    ├── frontend/
    │   ├── templates/                    ← Jinja2 (base.html + páginas)
    │   └── static/
    │       ├── css/                      ← main.css, animacoes.css, etc.
    │       ├── js/                       ← main.js, admin-login.js, etc.
    │       ├── imagens/                  ← logos, equipe (alunos/professores)
    │       └── uploads/                  ← imagens enviadas pelo painel admin
    ├── docs/                             ← relatórios do PI (PDF/DOCX)
    ├── .env                              ← variáveis de ambiente (não commitado)
    ├── requirements.txt
    ├── Procfile                          ← gunicorn para Render.com
    └── README.md
```

## Stack tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.8+, Flask 2.0+, Jinja2 |
| Autenticação | Firebase Admin SDK (Google OAuth) |
| Frontend | HTML5, CSS3, JavaScript ES6+, Bootstrap 5.3 |
| "Banco de dados" | JSON file (`backend/data/site_content.json`) |
| Deploy | Gunicorn + Render.com |

## Como rodar localmente

```bash
# Dentro de Site-GPTcode/
pip install -r requirements.txt
# Criar .env com variáveis Firebase
python backend/app.py        # porta 5000
```

Ou da raiz do workspace:
```bash
python run.py
```

## Páginas públicas

| Rota | Template |
|------|----------|
| `/` | index.html |
| `/projetos` | projetos.html |
| `/publicacoes` | publicacoes.html |
| `/equipe` | equipe.html |
| `/contato` | contato.html |
| `/devs` | devs.html |

## Painel administrativo

- URL: `/admin/login` — login via Google (Firebase)
- Acesso controlado por `ADMIN_ALLOWED_EMAILS` e `ADMIN_ALLOWED_DOMAINS` no `.env`
- CRUD completo para: Home, Projetos, Publicações, Equipe
- Upload de imagens salvas em `frontend/static/uploads/` com nomes UUID

## Variáveis de ambiente necessárias (.env)

```
FLASK_SECRET_KEY=
FIREBASE_API_KEY=
FIREBASE_AUTH_DOMAIN=
FIREBASE_PROJECT_ID=
FIREBASE_STORAGE_BUCKET=
FIREBASE_MESSAGING_SENDER_ID=
FIREBASE_APP_ID=
FIREBASE_MEASUREMENT_ID=
ADMIN_ALLOWED_EMAILS=
ADMIN_ALLOWED_DOMAINS=.ifb.edu.br
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.sitegptcode.json
```

## Conteúdo editável

Todo o conteúdo do site vive em `backend/data/site_content.json`:
- `home` — hero, sobre, publicação em destaque, slider, parceiros
- `projects` — lista de projetos (PIBIC, PIBITI, TCC)
- `publications` — publicações científicas
- `team` — professores e alunos

## Convenções do projeto

- CSS por página: cada página tem seu próprio arquivo CSS além do `main.css`
- Animações centralizadas em `animacoes.css`
- JavaScript modular por página; `main.js` para comportamentos globais
- Templates herdam de `frontend/templates/base.html`
- Templates do admin herdam de `frontend/templates/admin/base.html`
- Imagens de upload recebem nome UUID para evitar colisões

## Deploy

- Plataforma: Render.com
- Comando: `gunicorn backend.app:app` (via Procfile)
- URL de produção: https://gptcode-ifb.onrender.com/

## Equipe de desenvolvimento

- Davi Rocha Fortes Bezerra
- Gabriel Azevedo Marques
- Lucas Henrique Ferreira Alves
- Luiz Gustavo Souza Batista
