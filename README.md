# Parking Lot de tarefas

Gestor visual de tarefas em forma de edifício-garagem para o time de Adm. de Vendas.
Especificação completa em [`docs/SPEC.md`](docs/SPEC.md).

## Como rodar

```bash
# 1. Banco
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/python seed.py
.venv/bin/uvicorn app.main:app --reload

# 3. Frontend (outro terminal)
cd frontend
npm install
npm run dev
```

Acesse http://localhost:5173. Usuários do seed (senha `senha123`):

| E-mail | Papéis |
|---|---|
| `gestora@exemplo.com` | Gestor |
| `marcos@exemplo.com` | Manobrista (Pedido, Nota fiscal, Cadastro de cliente) |
| `ana.souza@exemplo.com` | Dona do 1º andar + manobrista (Devolução, Cotação, Contrato) |
| `bruno.lima@exemplo.com` e demais `nome.sobrenome@exemplo.com` | Donos de andar |

## Testes

```bash
cd backend && .venv/bin/pytest
```

Os testes rodam contra o banco `parking_lot_test` (criado automaticamente pelo Docker Compose).

## Como usar

- **Cancela** (botão no topo): qualquer pessoa cria uma tarefa, que vai para o pátio.
- **Manobrista/gestor**: clica num carro do pátio, navega até o andar e clica numa vaga destacada.
- **Dono do andar**: clica num carro para ver o parquímetro, editar, ligar o pisca-alerta,
  concluir ou devolver ao pátio. Com o carro selecionado, clicar numa vaga destacada troca de vaga.
- **Gestor**: em Configuração, ajusta vagas por andar, papéis, tipos por manobrista, cria usuários e tipos.

## Decisões tomadas onde a SPEC não detalhava

- **Contiguidade**: vagas são geradas em fileiras de `SPOTS_PER_ROW` (padrão 6). Caminhão ocupa a vaga
  escolhida e a vizinha da direita, na mesma fileira.
- **Dia útil**: segunda a sexta no fuso `TIMEZONE` (padrão `America/Sao_Paulo`); feriados não são descontados.
  "3 dias úteis" = 72h de tempo em dias úteis.
- **Carro concluído** mantém o `floor_id` do andar onde foi concluído, para o histórico do andar.
- **Devolver ao pátio ou concluir** com pisca-alerta ligado o desliga automaticamente (com evento `hazard_off`).
- **Dono de andar** tentando ver um carro de outro andar recebe 404 (não revela que o carro existe).
- **Log imutável**: um trigger no Postgres bloqueia UPDATE e DELETE na tabela `events`.
- **Autenticação provisória**: e-mail e senha com token JWT (SSO fica para depois, como na SPEC).
- **Usuários e tipos de tarefa** podem ser criados pelo gestor na tela de Configuração.
- **Vencimentos no tempo real**: uma tarefa em segundo plano recalcula os relógios a cada
  `CLOCK_TICK_SECONDS` e transmite os carros cujo prazo ou tempo parado acabou de vencer.

Todos os valores provisórios da seção 11 ficam em `backend/app/config.py` e podem ser
sobrescritos por variáveis de ambiente (veja `backend/.env.example`).
