import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// Tela do gestor: vagas por andar, papéis e tipos por manobrista, novos usuários e tipos.
export default function Admin({ floors, taskTypes, onFloorsChanged, onTypesChanged, onError, onInfo }) {
  const [users, setUsers] = useState([]);

  async function loadUsers() {
    try {
      setUsers(await api("/users"));
    } catch (err) {
      onError(err.message);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function saveCapacity(floorId, capacity) {
    try {
      await api(`/floors/${floorId}`, { method: "PATCH", body: { capacity: Number(capacity) } });
      onInfo("Capacidade atualizada");
      onFloorsChanged();
    } catch (err) {
      onError(err.message);
    }
  }

  async function saveUser(user, changes) {
    try {
      const updated = await api(`/users/${user.id}`, { method: "PATCH", body: changes });
      setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      onError(err.message);
    }
  }

  function toggleType(user, typeId) {
    const ids = user.valet_type_ids.includes(typeId)
      ? user.valet_type_ids.filter((id) => id !== typeId)
      : [...user.valet_type_ids, typeId];
    saveUser(user, { valet_type_ids: ids });
  }

  const floorPosition = Object.fromEntries(floors.map((f) => [f.id, f.position]));

  return (
    <div className="admin">
      <section>
        <h2>Vagas por andar</h2>
        <table>
          <thead>
            <tr>
              <th>Andar</th>
              <th>Dono</th>
              <th>Ocupadas</th>
              <th>Capacidade</th>
            </tr>
          </thead>
          <tbody>
            {[...floors]
              .sort((a, b) => a.position - b.position)
              .map((floor) => (
                <CapacityRow key={floor.id} floor={floor} onSave={saveCapacity} />
              ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Papéis e tipos por manobrista</h2>
        <table>
          <thead>
            <tr>
              <th>Pessoa</th>
              <th>Andar</th>
              <th>Gestor</th>
              <th>Manobrista</th>
              <th>Tipos sob responsabilidade</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>
                  {user.name}
                  <div className="muted small">{user.email}</div>
                </td>
                <td>{user.floor_id ? `${floorPosition[user.floor_id]}º` : "—"}</td>
                <td>
                  <input
                    type="checkbox"
                    checked={user.is_manager}
                    onChange={(e) => saveUser(user, { is_manager: e.target.checked })}
                  />
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={user.is_valet}
                    onChange={(e) => saveUser(user, { is_valet: e.target.checked })}
                  />
                </td>
                <td>
                  {user.is_valet ? (
                    <div className="chips">
                      {taskTypes.map((t) => (
                        <label key={t.id} className="chip">
                          <input
                            type="checkbox"
                            checked={user.valet_type_ids.includes(t.id)}
                            onChange={() => toggleType(user, t.id)}
                          />
                          {t.icon} {t.name}
                        </label>
                      ))}
                    </div>
                  ) : (
                    <span className="muted small">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <div className="admin-forms">
        <NewUserForm
          onCreated={() => {
            loadUsers();
            onFloorsChanged();
            onInfo("Usuário criado");
          }}
          onError={onError}
        />
        <NewTypeForm
          onCreated={() => {
            onTypesChanged();
            onInfo("Tipo criado");
          }}
          onError={onError}
        />
      </div>
    </div>
  );
}

function CapacityRow({ floor, onSave }) {
  const [value, setValue] = useState(floor.capacity);
  useEffect(() => setValue(floor.capacity), [floor.capacity]);
  return (
    <tr>
      <td>{floor.position}º</td>
      <td>{floor.owner.name}</td>
      <td>{floor.occupied}</td>
      <td>
        <input type="number" min={1} max={60} value={value} onChange={(e) => setValue(e.target.value)} className="narrow" />
        {Number(value) !== floor.capacity && (
          <button className="primary small-btn" onClick={() => onSave(floor.id, value)}>
            Salvar
          </button>
        )}
      </td>
    </tr>
  );
}

function NewUserForm({ onCreated, onError }) {
  const empty = { name: "", email: "", password: "", is_manager: false, is_valet: false, floor_capacity: "" };
  const [form, setForm] = useState(empty);
  const update = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  async function submit(event) {
    event.preventDefault();
    try {
      await api("/users", {
        method: "POST",
        body: { ...form, floor_capacity: form.floor_capacity === "" ? null : Number(form.floor_capacity) },
      });
      setForm(empty);
      onCreated();
    } catch (err) {
      onError(err.message);
    }
  }

  return (
    <form className="panel-form card" onSubmit={submit}>
      <h3>Novo usuário</h3>
      <label>
        Nome
        <input value={form.name} onChange={(e) => update("name", e.target.value)} required />
      </label>
      <label>
        E-mail
        <input type="email" value={form.email} onChange={(e) => update("email", e.target.value)} required />
      </label>
      <label>
        Senha inicial
        <input type="password" value={form.password} onChange={(e) => update("password", e.target.value)} minLength={6} required />
      </label>
      <label>
        Vagas do andar (vazio = sem andar)
        <input type="number" min={1} max={60} value={form.floor_capacity} onChange={(e) => update("floor_capacity", e.target.value)} />
      </label>
      <label className="inline">
        <input type="checkbox" checked={form.is_valet} onChange={(e) => update("is_valet", e.target.checked)} /> Manobrista
      </label>
      <label className="inline">
        <input type="checkbox" checked={form.is_manager} onChange={(e) => update("is_manager", e.target.checked)} /> Gestor
      </label>
      <button type="submit" className="primary">
        Criar usuário
      </button>
    </form>
  );
}

function NewTypeForm({ onCreated, onError }) {
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("");

  async function submit(event) {
    event.preventDefault();
    try {
      await api("/task-types", { method: "POST", body: { name, icon } });
      setName("");
      setIcon("");
      onCreated();
    } catch (err) {
      onError(err.message);
    }
  }

  return (
    <form className="panel-form card" onSubmit={submit}>
      <h3>Novo tipo de tarefa</h3>
      <label>
        Nome
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Ícone (emoji)
        <input value={icon} onChange={(e) => setIcon(e.target.value)} required maxLength={4} className="narrow" />
      </label>
      <button type="submit" className="primary">
        Criar tipo
      </button>
    </form>
  );
}
