import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import {
  EFFORTS,
  EVENT_LABELS,
  PRIORITIES,
  deadlineText,
  effortLabel,
  formatDateTime,
  formatDuration,
  isOverdue,
  priorityColor,
  priorityLabel,
  toLocalInput,
} from "../format.js";

// Painel lateral com os detalhes de um veículo, o parquímetro, as ações permitidas
// e o histórico de eventos. Os botões só aparecem para quem pode usá-los, mas quem
// decide de verdade é o backend (ele devolve erro se não puder).
export default function CarPanel({ car, me, taskTypes, onChanged, onClose, onError, now }) {
  const [events, setEvents] = useState([]);
  const [editing, setEditing] = useState(false);
  const [returning, setReturning] = useState(false);

  const isOwner = car.status === "estacionado" && car.floor_id === me.owned_floor_id;
  const canReturn = car.status === "estacionado" && (isOwner || me.is_manager);
  const canPark =
    car.status === "patio" && (me.is_manager || (me.is_valet && me.valet_type_ids.includes(car.task_type.id)));

  // Recarrega o histórico sempre que o carro muda (nova versão chegou por API ou WebSocket).
  useEffect(() => {
    let cancelled = false;
    api(`/cars/${car.id}/events`)
      .then((data) => !cancelled && setEvents(data))
      .catch(() => !cancelled && setEvents([]));
    return () => {
      cancelled = true;
    };
  }, [car]);

  useEffect(() => {
    setEditing(false);
    setReturning(false);
  }, [car.id]);

  async function run(path, body) {
    try {
      const updated = await api(`/cars/${car.id}${path}`, { method: "POST", body });
      onChanged(updated);
      return true;
    } catch (err) {
      onError(err.message);
      return false;
    }
  }

  const overdue = isOverdue(car, now);
  const stale = car.clock.is_stale;

  return (
    <aside className="car-panel">
      <header>
        <span className="plate-big">{car.plate}</span>
        <button className="icon-btn" onClick={onClose} title="Fechar">
          ✕
        </button>
      </header>
      <h3>{car.title}</h3>
      {car.description && <p className="description">{car.description}</p>}

      <dl>
        <dt>Tipo</dt>
        <dd>
          {car.task_type.icon} {car.task_type.name}
        </dd>
        <dt>Esforço</dt>
        <dd>{effortLabel(car.effort)}</dd>
        <dt>Prioridade</dt>
        <dd>
          <span className="swatch" style={{ background: priorityColor(car.priority) }} />
          {priorityLabel(car.priority)}
        </dd>
        <dt>Situação</dt>
        <dd>
          {{ patio: "No pátio", estacionado: `Vaga ${car.spot_positions.map((p) => p + 1).join(" e ")}`, concluido: "Concluída" }[
            car.status
          ]}
        </dd>
      </dl>

      {car.status !== "concluido" && (
        <div className="meter">
          <h4>Parquímetro</h4>
          <div className={overdue ? "clock danger" : "clock"}>
            <span>{overdue ? "🔴" : "🟢"} Prazo</span>
            <span>
              {formatDateTime(car.due_at)} · {deadlineText(car, now)}
            </span>
          </div>
          <div className={stale ? "clock stale" : "clock"}>
            <span>{stale ? "💤" : "⏱️"} Tempo parado</span>
            <span>
              {formatDuration(car.clock.stopped_seconds)} úteis (limite {formatDuration(car.clock.stale_limit_seconds)})
              {car.hazard_on && " · pausado pelo pisca-alerta"}
            </span>
          </div>
          {car.hazard_on && <div className="clock hazard">⚠️ Pisca-alerta: aguardando terceiro</div>}
        </div>
      )}

      {canPark && <p className="hint">Escolha um andar e clique numa vaga destacada para estacionar.</p>}
      {isOwner && !editing && !returning && (
        <p className="hint">Para trocar de vaga, clique numa vaga destacada do seu andar.</p>
      )}

      {isOwner && !editing && !returning && (
        <div className="actions wrap">
          <button onClick={() => setEditing(true)}>✏️ Editar</button>
          <button onClick={() => run("/hazard", { on: !car.hazard_on })}>
            {car.hazard_on ? "Desligar pisca-alerta" : "⚠️ Ligar pisca-alerta"}
          </button>
          <button className="primary" onClick={() => run("/complete", undefined)}>
            ✅ Concluir
          </button>
        </div>
      )}
      {canReturn && !editing && !returning && (
        <div className="actions">
          <button onClick={() => setReturning(true)}>↩️ Devolver ao pátio</button>
        </div>
      )}

      {editing && (
        <EditForm
          car={car}
          taskTypes={taskTypes}
          onCancel={() => setEditing(false)}
          onSave={async (changes) => {
            try {
              onChanged(await api(`/cars/${car.id}`, { method: "PATCH", body: changes }));
              setEditing(false);
            } catch (err) {
              onError(err.message);
            }
          }}
        />
      )}
      {returning && (
        <ReturnForm
          onCancel={() => setReturning(false)}
          onConfirm={async (reason) => {
            if (await run("/return", { reason })) setReturning(false);
          }}
        />
      )}

      <h4>Histórico</h4>
      <ol className="events">
        {[...events].reverse().map((event) => (
          <li key={event.id}>
            <strong>{EVENT_LABELS[event.type] ?? event.type}</strong>
            <span className="muted small">
              {" "}
              · {event.actor.name} · {formatDateTime(event.timestamp)}
            </span>
            {event.payload.reason && <div className="small">Motivo: {event.payload.reason}</div>}
          </li>
        ))}
      </ol>
    </aside>
  );
}

function EditForm({ car, taskTypes, onSave, onCancel }) {
  const [form, setForm] = useState({
    title: car.title,
    description: car.description,
    task_type_id: car.task_type.id,
    effort: car.effort,
    priority: car.priority,
    due_at: toLocalInput(car.due_at),
  });
  const update = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  return (
    <form
      className="panel-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ ...form, task_type_id: Number(form.task_type_id), due_at: new Date(form.due_at).toISOString() });
      }}
    >
      <label>
        Título
        <input value={form.title} onChange={(e) => update("title", e.target.value)} required />
      </label>
      <label>
        Descrição
        <textarea value={form.description} onChange={(e) => update("description", e.target.value)} rows={3} />
      </label>
      <label>
        Tipo
        <select value={form.task_type_id} onChange={(e) => update("task_type_id", e.target.value)}>
          {taskTypes.map((t) => (
            <option key={t.id} value={t.id}>
              {t.icon} {t.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Esforço
        <select value={form.effort} onChange={(e) => update("effort", e.target.value)}>
          {EFFORTS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Prioridade
        <select value={form.priority} onChange={(e) => update("priority", e.target.value)}>
          {PRIORITIES.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Prazo
        <input type="datetime-local" value={form.due_at} onChange={(e) => update("due_at", e.target.value)} required />
      </label>
      <div className="actions">
        <button type="button" onClick={onCancel}>
          Cancelar
        </button>
        <button type="submit" className="primary">
          Salvar
        </button>
      </div>
    </form>
  );
}

function ReturnForm({ onConfirm, onCancel }) {
  const [reason, setReason] = useState("");
  return (
    <form
      className="panel-form"
      onSubmit={(e) => {
        e.preventDefault();
        onConfirm(reason);
      }}
    >
      <label>
        Motivo da devolução
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} required autoFocus />
      </label>
      <div className="actions">
        <button type="button" onClick={onCancel}>
          Cancelar
        </button>
        <button type="submit" className="primary">
          Devolver
        </button>
      </div>
    </form>
  );
}
