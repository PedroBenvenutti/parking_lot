import { AnimatePresence } from "framer-motion";
import Spot from "./Spot.jsx";
import Vehicle from "./Vehicle.jsx";
import { LANE_H, PAD, RAMP_W, SPOT_H, floorSize, rampPoint, spotY, vehicleCenter } from "./layout.js";

// Calcula em quais vagas o veículo `placing` pode começar.
// Caminhão precisa da vaga clicada + a vizinha da direita (mesma fileira) livres.
// No caso de troca de vaga, as vagas do próprio veículo contam como livres.
function targetSpotIds(floor, placing) {
  if (!placing) return new Set();
  const own = new Set(placing.spot_ids);
  const occupied = new Set(floor.cars.flatMap((c) => c.spot_ids).filter((id) => !own.has(id)));
  const byRowCol = {};
  for (const s of floor.spots) byRowCol[`${s.row}:${s.column}`] = s;

  const targets = new Set();
  for (const spot of floor.spots) {
    if (occupied.has(spot.id)) continue;
    if (placing.effort === "caminhao") {
      const neighbor = byRowCol[`${spot.row}:${spot.column + 1}`];
      if (!neighbor || occupied.has(neighbor.id)) continue;
    }
    targets.add(spot.id);
  }
  return targets;
}

export default function Floor({ floor, selectedCarId, placing, onSpotClick, onCarClick, now }) {
  const size = floorSize(floor.spots);
  const ramp = rampPoint(size);
  const spotsById = Object.fromEntries(floor.spots.map((s) => [s.id, s]));
  const targets = targetSpotIds(floor, placing);
  const rows = new Set(floor.spots.map((s) => s.row)).size;

  return (
    <svg viewBox={`0 0 ${size.width} ${size.height}`} className="floor-svg" style={{ maxWidth: size.width }}>
      <rect width={size.width} height={size.height} className="asphalt" />

      {/* Rampa de entrada/saída */}
      <rect x={0} y={0} width={RAMP_W} height={size.height} className="ramp" />
      <text x={RAMP_W / 2} y={30} className="ramp-label">
        RAMPA
      </text>
      {[0.35, 0.55, 0.75].map((f) => (
        <text key={f} x={RAMP_W / 2} y={size.height * f} className="ramp-arrow">
          ⇅
        </text>
      ))}

      {/* Faixa tracejada no meio de cada pista */}
      {Array.from({ length: rows }, (_, row) => (
        <line
          key={row}
          x1={RAMP_W}
          x2={size.width}
          y1={spotY(row) + SPOT_H + LANE_H / 2}
          y2={spotY(row) + SPOT_H + LANE_H / 2}
          className="lane-line"
        />
      ))}

      {floor.spots.map((spot) => (
        <Spot
          key={spot.id}
          spot={spot}
          target={targets.has(spot.id)}
          onClick={() => onSpotClick(spot)}
        />
      ))}

      {/* initial={false}: carros que já estavam no andar ao abrir a tela não animam;
          só os que chegam depois entram pela rampa. */}
      <AnimatePresence initial={false}>
        {floor.cars.map((car) => {
          const center = vehicleCenter(car, spotsById);
          if (!center) return null;
          return (
            <Vehicle
              key={car.id}
              car={car}
              x={center.x}
              y={center.y}
              ramp={ramp}
              now={now}
              selected={car.id === selectedCarId}
              onClick={() => onCarClick(car)}
            />
          );
        })}
      </AnimatePresence>

      {floor.cars.length === 0 && (
        <text x={(size.width + RAMP_W) / 2} y={PAD + SPOT_H / 2} className="empty-floor">
          Andar vazio
        </text>
      )}
    </svg>
  );
}
