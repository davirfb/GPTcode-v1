# Site do GPTCode

Site oficial do **GPTCode** — Grupo de Pesquisa em Tecnologias Computacionais do Instituto Federal de Brasília —
com painel administrativo para manter o conteúdo. Este repositório contém **somente os arquivos do site**.

## O que tem em cada pasta

| Pasta / arquivo | Para que serve |
|---|---|
| `backend/` | O programa do site (Python/Flask): páginas, painel, API e acesso ao banco |
| `backend/data/semente.db` | Conteúdo inicial do site (equipe, projetos, publicações...) |
| `frontend/templates/` | As páginas (HTML) |
| `frontend/static/` | CSS, JavaScript, imagens do site e `uploads/` (imagens enviadas pelo painel) |
| `database/schema.sql` | Estrutura do banco de dados |
| `passenger_wsgi.py` | Ponto de entrada para hospedagem com cPanel (HostGator) |
| `requirements.txt` | Bibliotecas Python que o site precisa |
| `Procfile`, `render.yaml` | Configuração para publicar no Render (não são usados no HostGator) |
| `.env.exemplo` | Modelo das configurações secretas (copie para `.env`) |

O banco em uso (`backend/data/gptcode.db`) é criado sozinho na primeira execução, a partir da semente, e **não vai
para o git**. Ele guarda as mensagens do formulário de contato e os e-mails de quem acessou o painel.

## Login do painel

O login do painel (`/admin`) é feito pelo **Firebase Authentication** (e-mail e senha). Só entram e-mails liberados em
`ADMIN_ALLOWED_EMAILS` (ou domínios em `ADMIN_ALLOWED_DOMAINS`). As contas e senhas ficam no Firebase, não no site.

## Configuração (`.env`)

Copie `.env.exemplo` para `.env` e preencha. O arquivo `.env` e o JSON da conta de serviço do Firebase **nunca devem
ir para o git**.

## Rodar no computador

```bash
pip install -r requirements.txt
python -c "from backend.app import app; app.config['SESSION_COOKIE_SECURE']=False; app.run(port=5000)"
```

Abra <http://localhost:5000>.

## Publicar no HostGator (cPanel)

O site é um aplicativo **Python**, então o plano precisa ter **"Setup Python App"** (Passenger) no cPanel. Em
hospedagem que só serve HTML/PHP o site não funciona.

1. No cPanel, abra **Setup Python App → Create Application**: escolha o Python 3.9 ou mais novo, deixe
   *Application root* apontando para a pasta onde enviou os arquivos, *Startup file* `passenger_wsgi.py` e
   *Entry point* `application`.
2. Envie **todo o conteúdo deste repositório** (menos a pasta `.git`) para a pasta do aplicativo.
3. Em **Configuration files**, instale o `requirements.txt`.
4. Em **Environment variables**, cadastre as variáveis do `.env.exemplo`. Para a conta de serviço do Firebase,
   use `FIREBASE_SERVICE_ACCOUNT_JSON` (o conteúdo do arquivo em uma linha).
5. Clique em **Restart**.

Atualizações: envie os arquivos novos e reinicie o aplicativo. Não apague `backend/data/gptcode.db` nem
`frontend/static/uploads/`: é onde ficam os dados e as imagens do site.
