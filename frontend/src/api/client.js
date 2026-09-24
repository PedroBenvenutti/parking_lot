// Pequeno wrapper sobre fetch: adiciona o token e transforma erros da API em exceções
// com a mensagem em português que o backend devolve em `detail`.

const TOKEN_KEY = "parking_lot_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 401) {
    setToken(null);
  }
  if (!response.ok) {
    let message = `Erro ${response.status}`;
    try {
      const data = await response.json();
      // FastAPI devolve lista de erros de validação; regras de negócio vêm como texto.
      message = Array.isArray(data.detail) ? "Dados inválidos. Confira os campos." : data.detail;
    } catch {
      // resposta sem JSON
    }
    throw new ApiError(message, response.status);
  }
  return response.status === 204 ? null : response.json();
}
