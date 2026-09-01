# Talaska Barber Shop

Sistema da Talaska Barber Shop com site público, agendamento e painel administrativo. A publicação é feita com duas aplicações independentes no Render e um banco PostgreSQL hospedado no Neon:

| Componente | Serviço | Pasta | Responsabilidade |
| --- | --- | --- | --- |
| API | `talaska-api` | `backend/` | FastAPI, autenticação, agenda, clientes e administração |
| Site | `talaska-barber-shop` | `frontend/` | React/Vite, agendamento público e rota `/admin` |
| Banco | Neon PostgreSQL | externo ao Render | dados persistentes e migrations Alembic |

O `render.yaml` configura somente os dois serviços do Render. O banco Neon não deve ser declarado como banco do Render nem ter a URL gravada no Git.

## Desenvolvimento local

1. Copie o bloco **Backend** de `.env.example` para `backend/.env` e gere valores locais seguros para `SECRET_KEY` e `ADMIN_INITIAL_PASSWORD`.
2. Copie o bloco **Frontend** para `frontend/.env`.
3. Em um terminal, execute:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

4. Em outro terminal, execute:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

5. Abra `http://localhost:5173`; o painel é `http://localhost:5173/admin`.

## Banco Neon e Alembic

1. No Neon, copie a connection string da branch de produção. Para uma API hospedada, use `sslmode=require` e mantenha credenciais apenas no gerenciador de variáveis do Render.
2. O driver desta aplicação é `psycopg` v3. Se o Neon entregar uma URL iniciando em `postgresql://`, troque **somente** o esquema para `postgresql+psycopg://` antes de preencher `DATABASE_URL`.
3. Aplique a versão de schema antes de colocar uma nova API no ar:

   ```bash
   cd backend
   alembic upgrade head
   alembic current
   ```

4. Ao alterar modelos, gere e revise a migration antes de publicar:

   ```bash
   cd backend
   alembic revision --autogenerate -m "descricao-da-alteracao"
   alembic upgrade head
   ```

`alembic upgrade head` é idempotente: uma versão já aplicada não é executada novamente. Faça backup/snapshot no Neon antes de migrations destrutivas e não use `alembic downgrade` como procedimento rotineiro em produção.

## Publicação no Render

### 1. API FastAPI

Crie o serviço **talaska-api** pelo Blueprint do repositório. A API usa a pasta `backend/`, instala `requirements.txt`, executa `alembic upgrade head` antes de iniciar o `uvicorn` e só então atende na porta fornecida pelo Render. O endpoint de verificação é `/health`.

Cadastre estes valores no serviço **talaska-api**:

| Variável | Valor |
| --- | --- |
| `ENVIRONMENT` | `production` no Render; impede iniciar com segredos de desenvolvimento |
| `DATABASE_URL` | URL do Neon com `postgresql+psycopg://` e `sslmode=require` |
| `SECRET_KEY` | segredo aleatório longo; o Blueprint pode gerá-lo na primeira criação |
| `ADMIN_EMAIL` | e-mail inicial do administrador |
| `ADMIN_INITIAL_PASSWORD` | senha inicial forte, exclusiva e não versionada |
| `FRONTEND_ORIGINS` | URL final do site, por exemplo `https://talaska-barber-shop.onrender.com` |
| `CANCELLATION_HOURS` | prazo de cancelamento em horas (padrão: `2`) |
| `APPOINTMENT_INTERVAL_MINUTES` | intervalo de agenda em minutos (padrão: `30`) |

Os valores com `sync: false` são solicitados apenas na criação inicial do Blueprint. Se o serviço já existir, eles devem ser preenchidos ou alterados manualmente em **Environment** no Render.

O Blueprint define `ENVIRONMENT=production`. Nesse modo, a API recusa segredos e senhas administrativas de desenvolvimento; confirme que `SECRET_KEY` e `ADMIN_INITIAL_PASSWORD` foram preenchidos com valores reais antes do primeiro deploy.

O Blueprint usa `alembic upgrade head && uvicorn ...` no Start Command para funcionar também no plano gratuito: se a migration falhar, a nova instância não inicia. Como `alembic upgrade head` é idempotente, ele pode rodar a cada boot de uma única instância. Ao migrar para plano pago ou para mais de uma instância, mova o comando de migration para `preDeployCommand: alembic upgrade head` e deixe o Start Command apenas com o `uvicorn`; isso evita corridas de migration entre réplicas.

Depois do primeiro deploy, copie a URL pública efetiva da API, confirme `GET https://SEU-ENDERECO/health` e use-a na configuração do site abaixo.

### 2. Site React/Vite

O Static Site público **talaska-barber-shop** já existe. Ao sincronizar o Blueprint, atualize esse serviço existente — **não crie um segundo Static Site**. Só faça essa troca depois que `frontend/package.json`, o código React e os assets estiverem enviados ao repositório; caso contrário, o build apontando para `frontend/` falhará. Ele usa:

- Root Directory: `frontend`
- Build Command: `npm install && npm run build`
- Publish Directory: `dist`
- `VITE_API_URL`: `https://URL-REAL-DA-API.onrender.com/api`

`VITE_API_URL` não é segredo, mas é incorporada no JavaScript durante o build. Portanto, depois de alterar essa variável, faça um novo deploy do site estático. Não inclua uma barra no final da URL.

O Blueprint contém uma regra de rewrite `/* -> /index.html`. Ela é necessária para que links diretos e atualizações de página em `https://SEU-SITE.onrender.com/admin` sejam atendidos pelo React, sem resposta 404.

### Ordem segura de corte

1. Aplique e confira as migrations no Neon.
2. Publique a API e valide `/health`.
3. Defina `FRONTEND_ORIGINS` com a URL do site público e faça redeploy da API se necessário.
4. Defina `VITE_API_URL` com a URL pública da API seguida de `/api`.
5. Faça redeploy do site e teste agendamento, login em `/admin` e atualização direta da rota `/admin`.

## Endpoints principais

- Públicos: `GET /api/services`, `GET /api/barbers`, `GET /api/availability`, `POST /api/appointments`
- Sessão: `POST /api/auth/login`
- Administração: `/api/admin/dashboard`, `/api/admin/appointments`, `/api/admin/customers`, `/api/admin/barbers` e `/api/admin/services`

## Segurança operacional

- Nunca versione `.env`, `DATABASE_URL`, senhas ou tokens.
- Mantenha `FRONTEND_ORIGINS` restrito aos domínios realmente usados pelo site.
- Troque a senha administrativa inicial após o primeiro acesso e registre os dados de acesso fora do repositório.
- Antes de alterar preços, agenda ou equipe em produção, valide a ação no painel e confira o resultado pelo site público.
