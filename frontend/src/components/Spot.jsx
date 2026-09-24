import { SPOT_H, SPOT_W, spotX, spotY } from "./layout.js";

// Uma vaga: faixas brancas nas laterais e o número. Quando o usuário está escolhendo
// onde estacionar/mover, as vagas válidas ficam destacadas e clicáveis.
export default function Spot({ spot, target, onClick }) {
  const x = spotX(spot.column);
  const y = spotY(spot.row);
  return (
    <g onClick={target ? onClick : undefined} style={{ cursor: target ? "pointer" : "default" }}>
      <rect x={x} y={y} width={SPOT_W} height={SPOT_H} className={target ? "spot spot-target" : "spot"} />
      <line x1={x} y1={y} x2={x} y2={y + SPOT_H} className="spot-line" />
      <line x1={x + SPOT_W} y1={y} x2={x + SPOT_W} y2={y + SPOT_H} className="spot-line" />
      {/* Número na faixa acima da vaga, para não ficar escondido sob o veículo. */}
      <text x={x + SPOT_W / 2} y={y - 5} className="spot-number">
        {spot.position + 1}
      </text>
    </g>
  );
}
