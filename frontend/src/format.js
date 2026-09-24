// Rótulos em português e utilidades de formatação.

export const EFFORTS = [
  { value: "moto", label: "Moto (baixo)" },
  { value: "carro", label: "Carro (médio)" },
  { value: "caminhao", label: "Caminhão (alto, 2 vagas)" },
];

export const PRIORITIES = [
  { value: "baixa", label: "Baixa", color: "#4caf7a" },
  { value: "media", label: "Média", color: "#3d8bd9" },
  { value: "alta", label: "Alta", color: "#f0a020" },
  { value: "urgente", label: "Urgente", color: "#d83b3b" },
];

export const EVENT_LABELS = {
  created: "Criada na cancela",
  parked: "Estacionada",
  moved_spot: "Trocou de vaga",
  updated: "Editada",
  hazard_on: "Pisca-alerta ligado",
  hazard_off: "Pisca-alerta desligado",
  returned_to_patio: "Devolvida ao pátio",
  completed: "Concluída",
};

export function priorityColor(priority) {
  return PRIORITIES.find((p) => p.value === priority)?.color ?? "#888";
}

export function priorityLabel(priority) {
  return PRIORITIES.find((p) => p.value === priority)?.label ?? priority;
}

export function effortLabel(effort) {
  return EFFORTS.find((e) => e.value === effort)?.label ?? effort;
}

export function formatDateTime(iso) {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

// 93784 segundos -> "1d 2h"
export function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}min`;
  return `${minutes}min`;
}

// O prazo pode ser recalculado no navegador (é só comparar datas).
// O tempo parado depende de dias úteis e do pisca-alerta: vem pronto do backend.
export function isOverdue(car, now = new Date()) {
  return car.status !== "concluido" && now > new Date(car.due_at);
}

export function deadlineText(car, now = new Date()) {
  const diff = (new Date(car.due_at) - now) / 1000;
  return diff >= 0 ? `vence em ${formatDuration(diff)}` : `venceu há ${formatDuration(-diff)}`;
}

// Converte ISO (UTC) para o formato do <input type="datetime-local"> no horário local.
export function toLocalInput(iso) {
  const date = new Date(iso);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date - offset).toISOString().slice(0, 16);
}
