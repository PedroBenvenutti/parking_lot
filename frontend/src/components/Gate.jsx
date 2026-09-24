import { useState } from "react";
import { api } from "../api/client.js";
import { EFFORTS, PRIORITIES, toLocalInput } from "../format.js";

// Cancela: formulário de criação de tarefa. Toda tarefa nasce no pátio.
export default function Gate({ taskTypes, onClose, onCreated }) {
  const tomorrow = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
  const [form, setForm] = useState({
    title: "",
    description: "",
    task_type_id: taskTypes[0]?.id ?? "",
    effort: "carro",
    priority: "media",
    due_at: toLocalInput(tomorrow),
  });
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const car = await api("/cars", {
        method: "POST",
        body: {
          ...form,
          task_type_id: Number(form.task_type_id),
          // datetime-local não tem fuso: new Date() interpreta como horário local.
          due_at: new Date(form.due_at).toISOString(),
        },
      });
      onCreated(car);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>🚧 Cancela: nova tarefa</h2>
        <label>
          Título
          <input value={form.title} onChange={(e) => update("title", e.target.value)} required autoFocus />
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
        <div className="row">
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
        </div>
        <label>
          Prazo
          <input type="datetime-local" value={form.due_at} onChange={(e) => update("due_at", e.target.value)} required />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="primary" disabled={saving}>
            Enviar ao pátio
          </button>
        </div>
      </form>
    </div>
  );
}
