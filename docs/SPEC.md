# Especificação: Parking Lot de tarefas (Adm. de Vendas)

## 1. Visão geral

Gestor visual de tarefas para o time de Administração de Vendas (10+ pessoas), em forma de edifício-garagem visto de cima. Cada pessoa tem um andar com número limitado de vagas; cada tarefa é um veículo estacionado.

Problemas que resolve:

- **Tarefas que se perdem em e-mail/Teams**: tudo entra por uma cancela única e fica visível no pátio até ser distribuído.
- **Tarefas paradas ou atrasadas que ninguém enxerga**: cada carro tem um parquímetro com prazo e tempo sem movimentação; quando vencem, a aparência do carro muda.

O limite de vagas por andar funciona como limite de trabalho em andamento (WIP): andar lotado impede novas entradas, e o acúmulo no pátio evidencia a sobrecarga do time.

## 2. Glossário

| Termo | Significado |
|---|---|
| Andar | Espaço de trabalho de uma pessoa, com N vagas |
| Vaga | Posição onde um veículo pode estacionar |
| Veículo / carro | Uma tarefa |
| Placa | ID legível da tarefa (ex: `ADV-0142`) |
| Cancela | Ponto de entrada de tarefas no sistema |
| Pátio | Fila de tarefas criadas e ainda não distribuídas |
| Manobrista | Quem move carros do pátio para os andares |
| Parquímetro | Os dois relógios da tarefa: prazo e tempo parado |
| Pisca-alerta | Tarefa aguardando terceiro |

## 3. Papéis e permissões

| Ação | Dono do andar | Manobrista | Gestor |
|---|---|---|---|
| Criar tarefa (vai para o pátio) | Sim | Sim | Sim |
| Ver o pátio | Não | Sim, apenas os tipos sob sua responsabilidade | Sim, tudo |
| Ver o próprio andar | Sim | Sim | Sim |
| Ver andares de outras pessoas | Não | Sim, todos | Sim, todos |
| Estacionar carro do pátio num andar | Não | Sim, apenas tipos sob sua responsabilidade | Sim |
| Mover carro entre vagas do próprio andar | Sim | Não | Não |
| Editar, ligar pisca-alerta, concluir | Sim, só no próprio andar | Não | Não |
| Devolver carro ao pátio | Sim, só do próprio andar | Não | Sim |
| Configurar vagas por andar | Não | Não | Sim |
| Configurar tipos por manobrista | Não | Não | Sim |
| Ver métricas (fase 2) | Não | Não | Sim |

Um usuário pode acumular papéis (ex: ser dono de um andar e também manobrista).

**Toda permissão é validada no backend.** O dono de um andar nunca recebe dados de outros andares pela API ou pelo WebSocket, nem mesmo ocultos no frontend.

## 4. Veículo (tarefa)

### Codificação visual

| Atributo | Representação |
|---|---|
| Esforço | Forma: moto (baixo, 1 vaga), carro (médio, 1 vaga), caminhão (alto, 2 vagas contíguas) |
| Prioridade | Cor: baixa, média, alta, urgente |
| Tipo | Ícone no teto do veículo |
| ID | Placa visível |
| Prazo vencido | Indicador visual próprio (ex: parquímetro vermelho) |
| Tempo parado vencido | Indicador visual distinto do prazo (ex: carro esmaecido/empoeirado) |
| Pisca-alerta | Setas piscando nos dois lados do veículo |

Os dois vencimentos devem ser distinguíveis entre si e combináveis (um carro pode estar com os dois vencidos). Não depender apenas de cor para comunicar estado.

### Campos

- `plate` (gerado automaticamente, único)
- `title`, `description`
- `task_type` (FK para tipos configuráveis)
- `effort`: `moto` | `carro` | `caminhao`
- `priority`: `baixa` | `media` | `alta` | `urgente`
- `due_at` (prazo)
- `status`: `patio` | `estacionado` | `concluido`
- `hazard_on` (pisca-alerta)
- `floor_id`, vagas ocupadas (nulos enquanto no pátio)
- `created_by`, `created_at`

### Relógios

- **Prazo**: vence quando `now > due_at`. Não pausa nunca, nem com pisca-alerta.
- **Tempo parado**: tempo desde o último evento de movimentação, **descontando intervalos em que o pisca-alerta esteve ligado**. É calculado a partir do log de eventos, não armazenado como campo editável.

## 5. Fluxo

1. **Cancela**: qualquer usuário cria uma tarefa manualmente. O carro nasce no pátio com status `patio`.
2. **Pátio**: cada manobrista vê os carros dos tipos sob sua responsabilidade.
3. **Estacionar**: o manobrista escolhe andar e vaga. O backend valida:
   - permissão do manobrista para aquele tipo;
   - vaga livre (e, para caminhão, 2 vagas contíguas livres);
   - andar não lotado.
   Falhas retornam erro claro ("Andar lotado", "Caminhão precisa de 2 vagas lado a lado").
4. **No andar**: o dono trabalha a tarefa, edita, reorganiza vagas, liga ou desliga o pisca-alerta.
5. **Devolução**: o dono pode devolver o carro ao pátio (tarefa que não é dele). Registrar o motivo.
6. **Saída**: o dono conclui; o carro sai com animação e vai para o histórico (status `concluido`).

## 6. Tempo real

- WebSocket com canais por andar e um canal do pátio.
- Toda movimentação (chegada, saída, troca de vaga, pisca-alerta, vencimentos) é transmitida para quem tem permissão de ver aquele andar.
- O frontend anima chegada (carro entrando pela rampa até a vaga) e saída.
- Vencimentos de relógio podem ser recalculados no frontend a partir dos timestamps; o backend é a fonte da verdade.

## 7. Histórico e eventos

Log imutável desde o MVP. Alimenta o relógio de tempo parado e as métricas da fase 2.

Tipos de evento sugeridos: `created`, `parked`, `moved_spot`, `updated`, `hazard_on`, `hazard_off`, `returned_to_patio`, `completed`.

Cada evento guarda: `car_id`, `type`, `actor_id`, `timestamp`, `payload` (JSON com antes/depois quando aplicável).

## 8. Modelo de dados inicial

- `User` (nome, e-mail, papéis)
- `Floor` (dono, capacidade, ordem no prédio)
- `Spot` (andar, posição; gerado a partir da capacidade)
- `TaskType` (nome, ícone)
- `ValetAssignment` (manobrista ↔ tipos)
- `Car` (campos da seção 4)
- `CarSpot` (carro ↔ vagas, para suportar caminhão em 2 vagas)
- `Event` (seção 7)

## 9. Requisitos não funcionais

- Desktop como alvo principal.
- Tela de um andar legível com a capacidade máxima configurada.
- Regras de negócio e permissões exclusivamente no backend.
- Regras críticas cobertas por testes automatizados (seção 12).

## 10. Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, WebSocket nativo do FastAPI.
- **Frontend**: React (Vite), andar renderizado em SVG, animações com Framer Motion.
- **Ambiente**: Docker Compose para o Postgres (e opcionalmente a aplicação).
- **Hospedagem**: própria, fora do tenant Microsoft.

## 11. Valores provisórios (a confirmar)

Decisões ainda não validadas com o time. Usar estes valores até segunda ordem e mantê-los **configuráveis**, não fixos no código:

- Tempo parado vence após **3 dias úteis** sem movimentação.
- **Qualquer evento** do log conta como movimentação, exceto `hazard_on`/`hazard_off`.
- Login provisório com e-mail e senha (SSO Microsoft Entra ID fica para depois).
- Fragmentação de vagas é aceita no MVP: se não houver 2 vagas contíguas, o caminhão não entra. Sem reorganização automática.
- Ausências (férias) não têm tratamento especial no MVP.

## 12. MVP: escopo e critérios de aceite

Incluído:

- Cadastro manual de tarefas, pátio, andares com vagas limitadas.
- Três papéis com as permissões da seção 3.
- Dois relógios e pisca-alerta.
- Devolução ao pátio.
- Tempo real com animação de chegada e saída.
- Log de eventos.
- Script de seed: ~12 andares com capacidades diferentes, carros de todos os tamanhos e prioridades, alguns com prazo vencido, alguns parados, alguns com pisca-alerta.

Critérios de aceite (devem ter teste):

- Manobrista não estaciona tipo fora da sua responsabilidade.
- Andar lotado rejeita novos carros.
- Caminhão só estaciona em 2 vagas contíguas livres.
- Dono não acessa dados de outros andares por nenhum endpoint nem pelo WebSocket.
- Tempo parado desconta os intervalos com pisca-alerta ligado.
- Prazo continua correndo com pisca-alerta ligado.
- Concluir remove o carro da vaga e registra evento.

## 13. Roadmap

1. **MVP** (seção 12).
2. **Fase 2**: IA na cancela (sugere tipo, esforço, prioridade e título; manobrista confirma) e painel de métricas para o gestor (tempo médio por tarefa, atrasos por pessoa).
3. **Fase 3**: entrada por e-mail encaminhado e por mensagem do Teams via Microsoft Graph (depende de registro de app e consentimento da TI).

## 14. Questões em aberto

- Limite de tempo parado: valor único ou por tipo de tarefa?
- Login definitivo: SSO Microsoft Entra ID exige registro de app na TI.
- Tarefas podem conter dados de clientes; hospedar fora da estrutura da empresa pode esbarrar em política de TI ou LGPD.
- Fragmentação de vagas: reorganização automática, manual ou aceita?
- Tratamento do andar de quem está de férias.

## 15. Fora do escopo

Aplicativo mobile, integração com SAP, subtarefas ou dependências entre carros, visão isométrica ou 3D.
