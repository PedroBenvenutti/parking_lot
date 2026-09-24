// Geometria do andar em unidades do SVG. Tudo é desenhado visto de cima:
// a rampa fica à esquerda, as fileiras de vagas à direita, com uma pista entre elas.

export const SPOT_W = 84;
export const SPOT_H = 120;
export const LANE_H = 56;
export const RAMP_W = 90;
export const PAD = 20;

export function spotX(column) {
  return RAMP_W + PAD + column * SPOT_W;
}

export function spotY(row) {
  return PAD + row * (SPOT_H + LANE_H);
}

export function floorSize(spots) {
  const columns = Math.max(1, ...spots.map((s) => s.column + 1));
  const rows = Math.max(1, ...spots.map((s) => s.row + 1));
  return {
    width: RAMP_W + PAD * 2 + columns * SPOT_W,
    height: PAD + rows * (SPOT_H + LANE_H),
  };
}

// Ponto onde os carros surgem (chegada) e para onde vão (saída): pé da rampa.
export function rampPoint(size) {
  return { x: RAMP_W / 2, y: size.height - 30 };
}

// Centro do veículo: média dos centros das vagas que ele ocupa (caminhão = 2 vagas).
export function vehicleCenter(car, spotsById) {
  const spots = car.spot_ids.map((id) => spotsById[id]).filter(Boolean);
  if (spots.length === 0) return null;
  const xs = spots.map((s) => spotX(s.column) + SPOT_W / 2);
  const ys = spots.map((s) => spotY(s.row) + SPOT_H / 2);
  return {
    x: xs.reduce((a, b) => a + b, 0) / xs.length,
    y: ys.reduce((a, b) => a + b, 0) / ys.length,
  };
}
