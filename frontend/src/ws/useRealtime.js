import { useEffect, useRef } from "react";
import { getToken } from "../api/client.js";

// Mantém uma conexão WebSocket aberta e inscrita nos canais pedidos.
// `channels`: lista de strings, ex: ["patio", "floor:3"].
// `onMessage`: chamada para cada mensagem de carro/andar recebida.
// Reconecta sozinho se a conexão cair (ex: backend reiniciou).
export function useRealtime(channels, onMessage) {
  const socketRef = useRef(null);
  const subscribedRef = useRef(new Set());
  const channelsRef = useRef(channels);
  const onMessageRef = useRef(onMessage);

  // Refs guardam o valor mais recente sem precisar recriar a conexão a cada render.
  channelsRef.current = channels;
  onMessageRef.current = onMessage;

  // Abre a conexão uma vez.
  useEffect(() => {
    let closedByUs = false;
    let retryTimer = null;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(`${protocol}://${window.location.host}/ws?token=${getToken()}`);
      socketRef.current = socket;
      subscribedRef.current = new Set();

      socket.onopen = () => syncSubscriptions(socket, channelsRef.current, subscribedRef.current);
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (["car_upserted", "car_removed", "floor_updated"].includes(message.type)) {
          onMessageRef.current(message);
        }
      };
      socket.onclose = (event) => {
        if (closedByUs || event.code === 4401) return;
        retryTimer = setTimeout(connect, 2000);
      };
    }

    connect();
    return () => {
      closedByUs = true;
      clearTimeout(retryTimer);
      socketRef.current?.close();
    };
  }, []);

  // Sempre que a lista de canais muda, inscreve/desinscreve a diferença.
  const key = channels.join("|");
  useEffect(() => {
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      syncSubscriptions(socket, channels, subscribedRef.current);
    }
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
}

function syncSubscriptions(socket, wanted, current) {
  for (const channel of current) {
    if (!wanted.includes(channel)) {
      socket.send(JSON.stringify({ action: "unsubscribe", channel }));
      current.delete(channel);
    }
  }
  for (const channel of wanted) {
    if (!current.has(channel)) {
      socket.send(JSON.stringify({ action: "subscribe", channel }));
      current.add(channel);
    }
  }
}
