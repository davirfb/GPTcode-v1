[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/PgCp-DlW)

# GPTCode — Grupo de Pesquisa em Tecnologias Computacionais

Site oficial do **GPTCode**, grupo de pesquisa multidisciplinar do Instituto Federal de Brasília (IFB). O site apresenta projetos, publicações científicas, a equipe de pesquisadores e informações de contato do grupo.

- [Kanban](https://github.com/orgs/infocbra/projects/58/views/1)
- [Protótipo em produção](https://gptcode-ifb.onrender.com/)

## Tecnologias

| | |
|---|---|
| Backend | Python 3.8+, Flask 2.0+, Jinja2 |
| Autenticação | Firebase Authentication (Google OAuth) |
| Frontend | HTML5, CSS3, JavaScript ES6+, Bootstrap 5.3 |
| Armazenamento | JSON file-based (`backend/data/site_content.json`) |
| Deploy | Gunicorn + Render.com |

## Como iniciar

```bash
# 1. Instale as dependências
pip install -r requirements.txt

# 2. Configure as variáveis de ambiente
# Crie um arquivo .env com as chaves Firebase e ADMIN_ALLOWED_EMAILS
# (veja a seção de configuração abaixo)

# 3. Execute a aplicação
python backend/app.py
# Acesse: http://localhost:5000
```

> Se você estiver na pasta raiz do workspace (fora de `Site-GPTcode/`), use `python run.py`.

## Configuração do .env

```
FLASK_SECRET_KEY=sua_chave_secreta
FIREBASE_API_KEY=...
FIREBASE_AUTH_DOMAIN=...
FIREBASE_PROJECT_ID=...
FIREBASE_STORAGE_BUCKET=...
FIREBASE_MESSAGING_SENDER_ID=...
FIREBASE_APP_ID=...
ADMIN_ALLOWED_EMAILS=email@exemplo.com
ADMIN_ALLOWED_DOMAINS=.ifb.edu.br
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.sitegptcode.json
```

## Painel Administrativo

Acesse `/admin/login` e faça login com uma conta Google autorizada. O painel permite editar todo o conteúdo do site (projetos, publicações, equipe, home) sem tocar no código.

## Equipe

- Davi Rocha Fortes Bezerra
- Gabriel Azevedo Marques
- Lucas Henrique Ferreira Alves
- Luiz Gustavo Souza Batista
