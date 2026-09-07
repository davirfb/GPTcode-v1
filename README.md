# GPTCode — Site Oficial

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)](https://flask.palletsprojects.com/)
[![Firebase](https://img.shields.io/badge/Firebase-Auth-orange.svg)](https://firebase.google.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple.svg)](https://getbootstrap.com/)

Website oficial do **GPTCode** — Grupo de Pesquisa em Tecnologias Computacionais do Instituto Federal de Brasília (IFB).

---

## Sobre o Projeto

O site apresenta as atividades do grupo de pesquisa: projetos em andamento (PIBIC, PIBITI, TCC), publicações científicas, equipe de pesquisadores e formas de contato.

O sistema conta com um **painel administrativo completo** que permite gerenciar todo o conteúdo do site sem editar código, além de um **sistema de links únicos** para que membros externos possam submeter projetos, publicações e perfis para aprovação do admin.

---

## Funcionalidades

### Páginas públicas
- Página inicial com slider, destaques e parceiros
- Projetos (PIBIC, PIBITI, TCC)
- Publicações científicas
- Equipe (professores, graduação, técnicos, colaboradores externos)
- Contato

### Painel administrativo (`/admin`)
- Login seguro via Firebase Authentication
- CRUD completo de projetos, publicações, membros da equipe e formas de contato
- Gerenciamento do slider e parceiros da página inicial
- Upload de imagens
- Geração de links únicos com validade de 7 dias para submissão externa
- Revisão e aprovação/rejeição de submissões pendentes
- Notificação por e-mail a cada nova submissão

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + Flask 2.3 + Jinja2 |
| Autenticação | Firebase Authentication (JS SDK + Admin SDK) |
| Frontend | HTML5, CSS3, JS ES Modules, Bootstrap 5.3 |
| Banco de dados | Arquivos JSON locais (`backend/data/`) |
| Upload de imagens | Filesystem (`frontend/static/uploads/`) |
| E-mail | Gmail SMTP SSL (porta 465) |
| Deploy | Gunicorn + Render.com |

---

## Estrutura do Projeto

```
Site-GPTcode/
├── backend/
│   ├── app.py                  # Aplicação Flask (35+ rotas)
│   ├── content_manager.py      # Leitura/escrita do site_content.json
│   ├── token_manager.py        # Geração de links únicos (TTL 7 dias)
│   ├── pending_manager.py      # Submissões pendentes de aprovação
│   ├── mailer.py               # Notificações por e-mail (Gmail SMTP)
│   └── data/
│       ├── site_content.json   # Todo o conteúdo do site
│       ├── edit_tokens.json    # Tokens de acesso único
│       └── pending_submissions.json
├── frontend/
│   ├── templates/              # Templates Jinja2
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── projetos.html
│   │   ├── publicacoes.html
│   │   ├── equipe.html
│   │   ├── contato.html
│   │   ├── admin/              # Templates do painel admin
│   │   └── submit/             # Formulários de submissão externa
│   └── static/
│       ├── css/
│       ├── js/
│       ├── imagens/
│       └── uploads/            # Imagens enviadas pelo admin
├── .env                        # Variáveis de ambiente (não versionado)
├── firebase-service-account.sitegptcode.json
├── requirements.txt
├── Procfile
├── render.yaml
└── runtime.txt
```

---

## Instalação local

### Pré-requisitos
- Python 3.12
- Conta Firebase com projeto configurado
- Conta Gmail com senha de app gerada

### Passos

1. **Clone o repositório**
```bash
git clone https://github.com/davirfb/GPTcode-v1.git
cd GPTcode-v1/Site-GPTcode
```

2. **Crie e ative o ambiente virtual**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **Configure o arquivo `.env`**

Crie o arquivo `Site-GPTcode/.env` com as seguintes variáveis:

```env
FLASK_SECRET_KEY=sua_chave_secreta

# Firebase (Console do Firebase → Configurações do projeto → Seus apps)
FIREBASE_API_KEY=
FIREBASE_AUTH_DOMAIN=
FIREBASE_PROJECT_ID=
FIREBASE_STORAGE_BUCKET=
FIREBASE_MESSAGING_SENDER_ID=
FIREBASE_APP_ID=

# Admins permitidos (separados por vírgula)
ADMIN_ALLOWED_EMAILS=seuemail@exemplo.com
ADMIN_ALLOWED_DOMAINS=.ifb.edu.br

# Conta de serviço Firebase Admin SDK
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.sitegptcode.json

# E-mail para notificações
NOTIFICATION_EMAIL_FROM=seuemail@gmail.com
NOTIFICATION_EMAIL_APP_PASSWORD=senha_de_app_gmail
```

5. **Execute o servidor**
```bash
cd ..
python run.py
```

Acesse em `http://localhost:5000`.

---

## Fluxo de autenticação admin

1. Admin acessa `/admin/login` e preenche e-mail e senha.
2. O Firebase JS SDK autentica as credenciais diretamente com os servidores do Firebase e retorna um JWT.
3. O token JWT é salvo como cookie (`firebase_id_token`) no browser.
4. A cada requisição às rotas `/admin/*`, o Flask verifica o token via Firebase Admin SDK (`verify_id_token`) e checa se o e-mail está na lista de admins permitidos.
5. Logout: Firebase JS SDK encerra a sessão e o Flask limpa o cookie.

---

## Sistema de links únicos

1. Admin gera um link único para "adicionar projeto", "editar membro", etc.
2. O link tem validade de 7 dias e pode ser usado apenas uma vez.
3. O destinatário externo preenche o formulário e submete.
4. A submissão fica pendente em `pending_submissions.json` e o admin recebe uma notificação por e-mail.
5. Admin aprova ou rejeita em `/admin/pending`.

---

## Deploy (Render.com)

O arquivo `render.yaml` contém a configuração completa. As variáveis de ambiente devem ser configuradas manualmente no dashboard do Render:

- Todas as variáveis `FIREBASE_*`
- `ADMIN_ALLOWED_EMAILS`
- `NOTIFICATION_EMAIL_FROM` e `NOTIFICATION_EMAIL_APP_PASSWORD`
- `FLASK_SECRET_KEY` (gerado automaticamente pelo Render)

**Comando de build:** `pip install -r requirements.txt`  
**Comando de start:** `gunicorn backend.app:app`  
**Root directory:** `Site-GPTcode`

---

## Equipe de Desenvolvimento

- **Davi Rocha Fortes Bezerra** — Desenvolvedor Full Stack
- **Gabriel Azevedo Marques** — Desenvolvedor Full Stack
- **Lucas Henrique Ferreira Alves** — Desenvolvedor Front End / Product Owner
- **Luiz Gustavo Souza Batista** — Desenvolvedor Backend / Product Owner

Sob orientação de:
- **Prof. Fabio Henrique Monteiro Oliveira**
- **Prof. Heitor J. dos Santos Barros**

---

## Licença

MIT License — veja o arquivo [LICENSE](LICENSE) para detalhes.

---

**Desenvolvido pelo GPTCode — IFB Campus Brasília**
