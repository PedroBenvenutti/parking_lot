import { useState } from "react";
import { api, setToken } from "../api/client.js";

// Login provisório com e-mail e senha (o SSO Microsoft fica para depois, seção 11 da SPEC).
export default function Login({ onLoggedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    setError(null);
    try {
      const { access_token } = await api("/auth/login", { method: "POST", body: { email, password } });
      setToken(access_token);
      onLoggedIn();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="login">
      <form onSubmit={submit} className="modal">
        <h1>🅿️ Parking Lot</h1>
        <p className="muted">Gestor de tarefas da Adm. de Vendas</p>
        <label>
          E-mail
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </label>
        <label>
          Senha
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="primary">
          Entrar
        </button>
      </form>
    </div>
  );
}
