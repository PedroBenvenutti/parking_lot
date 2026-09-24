# Parking Lot de tarefas

Gestor visual de tarefas em forma de estacionamento para o time de Adm. de Vendas.
A especificação completa está em `docs/SPEC.md`. Leia antes de qualquer tarefa e siga-a como fonte da verdade.

## Escopo atual: somente o MVP

Trabalhe apenas no que está na seção 12 da SPEC.
Não implemente nada das fases 2 e 3 (IA na cancela, métricas, e-mail, Teams, Microsoft Graph), nem deixe "ganchos" especulativos para elas.
Se algo parecer exigir uma decisão que não está na SPEC, pergunte em vez de decidir sozinho.

## Stack

- Backend: Python, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, pytest
- Frontend: React + Vite, SVG para o andar, Framer Motion para animações
- Tempo real: WebSocket nativo do FastAPI
- Ambiente: Docker Compose para o Postgres

## Estrutura

```
backend/
  app/
    models/      # SQLAlchemy
    schemas/     # Pydantic
    services/    # regras de negócio (vagas, relógios, permissões)
    api/         # rotas REST
    ws/          # WebSocket e broadcast por andar
  tests/
  alembic/
  seed.py
frontend/
  src/
    components/  # Floor, Spot, Vehicle, Patio, BuildingNav
    api/
    ws/
docs/
  SPEC.md
docker-compose.yml
```

## Regras de arquitetura

- Toda regra de negócio e toda permissão ficam no backend, em `services/`. As rotas só orquestram.
- O frontend nunca é a única barreira: nada de esconder dados que a API não deveria ter enviado.
- O WebSocket filtra por permissão antes de transmitir, igual à API.
- O tempo parado é calculado a partir da tabela `Event`, descontando intervalos com pisca-alerta. Não criar campo editável para isso.
- Todo mutação em `Car` gera um `Event` na mesma transação.
- Valores da seção 11 da SPEC (limite de tempo parado etc.) ficam em configuração, nunca fixos no código.

## Ordem de trabalho sugerida

1. Docker Compose, modelos, migrations e seed.
2. Serviços de regra de negócio com testes (critérios de aceite da seção 12).
3. API REST.
4. WebSocket com broadcast por andar.
5. Frontend: andar em SVG, pátio, navegação entre andares, animações.

Não avance de etapa sem os testes da etapa anterior passando.

## Comandos

```bash
docker compose up -d db                      # Postgres (cria também o banco parking_lot_test)
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
cd backend && cp .env.example .env           # ajuste SECRET_KEY
cd backend && .venv/bin/alembic upgrade head && .venv/bin/python seed.py
cd backend && .venv/bin/uvicorn app.main:app --reload
cd backend && .venv/bin/pytest               # usa o banco parking_lot_test
cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd frontend && npm install && npm run dev    # http://localhost:5173 (proxy para o backend em :8000)
cd frontend && npm run build                 # gera frontend/dist, servido pelo FastAPI em produção
```

Atualize esta seção se os comandos mudarem.

## Convenções

- Código e nomes de variáveis em inglês; textos da interface em português.
- Type hints em todo o código Python.
- Commits pequenos, um por etapa ou funcionalidade.
- O desenvolvedor tem nível intermediário em Python e menos familiaridade com React: no frontend, prefira código simples e explícito a abstrações espertas, e explique brevemente decisões não óbvias.
