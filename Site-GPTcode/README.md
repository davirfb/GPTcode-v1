[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/PgCp-DlW)

# GPTCode - Grupo de Pesquisa em Tecnologias Computacionais

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3+-purple.svg)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Website oficial do **GPTCode** - Grupo de Pesquisa em Tecnologias Computacionais do Instituto Federal de Brasilia (IFB).

## Links importantes

[Kanban](https://github.com/orgs/infocbra/projects/58/views/1)  
[Prototipo](https://gptcode-ifb.onrender.com/)

## Sobre o Projeto

O **GPTCode** e um grupo de pesquisa multidisciplinar do IFB dedicado ao desenvolvimento de **tecnologias computacionais inovadoras**. Este website apresenta:

- Informacoes sobre o grupo de pesquisa
- Projetos em andamento (PIBIC, PIBITI, TCC)
- Publicacoes cientificas
- Equipe de pesquisadores
- Formulario de contato
- Equipe de desenvolvedores
- Parceiros e apoiadores

## Tecnologias Utilizadas

- Python 3.8+
- Flask 2.0+
- Jinja2
- HTML5
- CSS3
- JavaScript (ES6+)
- Bootstrap 5.3

## Instalacao

1. Clone o repositorio
2. Crie um ambiente virtual
3. Instale as dependencias com `pip install -r requirements.txt`
4. Crie um arquivo `.env` com base em `.env.example`
5. Execute a aplicacao com um dos comandos abaixo:
   - Se estiver na pasta interna do projeto: `python backend/app.py`
   - Se estiver na pasta externa aberta neste workspace: `python run.py`
6. Acesse `http://localhost:5000`

## Observacao sobre a estrutura

O projeto Flask esta dentro de uma pasta interna chamada `2025-2-vespertino-pi1-g3-2025-2-main/`.
Se voce tentar rodar `python backend/app.py` a partir da pasta externa, o comando vai falhar porque `backend/` existe apenas dentro dessa pasta interna.

## Painel Administrativo

- URL: `http://localhost:5000/admin/login`
- Metodo de login: Firebase Authentication com Google
- Configure as variaveis `FIREBASE_*` do app web no `.env`
- Defina `ADMIN_ALLOWED_EMAILS` e/ou `ADMIN_ALLOWED_DOMAINS` para restringir quem pode acessar o painel
- Para validar o token no backend Flask, use `GOOGLE_APPLICATION_CREDENTIALS` ou `FIREBASE_SERVICE_ACCOUNT_PATH`

O conteudo editavel do site fica salvo em `backend/data/site_content.json`.
As imagens enviadas pelo painel sao armazenadas em `frontend/static/uploads/`.

## Estrutura

- `backend/`: codigo Flask e inicializacao da aplicacao
- `backend/data/site_content.json`: conteudo editavel do site
- `frontend/templates/`: paginas HTML renderizadas pelo Flask
- `frontend/static/css/`: estilos
- `frontend/static/js/`: scripts
- `frontend/static/imagens/`: imagens e logos
- `frontend/static/uploads/`: imagens enviadas pelo painel administrativo
- `docs/`: documentacao de apoio

## Equipe de Desenvolvimento

- Davi Rocha Fortes Bezerra
- Gabriel Azevedo Marques
- Lucas Henrique Ferreira Alves
- Luiz Gustavo Souza Batista
