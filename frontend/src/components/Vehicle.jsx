import { motion } from "framer-motion";
import { isOverdue, priorityColor, priorityLabel } from "../format.js";

// Caixa ocupada por cada forma (usada para o contorno de seleção e para posicionar
// os indicadores). Tudo desenhado com o centro do veículo em (0, 0).
export const BOUNDS = {
  moto: { w: 36, h: 66 },
  carro: { w: 58, h: 100 },
  caminhao: { w: 154, h: 68 },
};

// Desenho estático do veículo. Usado no andar (dentro de <Vehicle>) e nos cartões do pátio.
export function VehicleShape({ car, now = new Date(), selected = false }) {
  const color = priorityColor(car.priority);
  const bounds = BOUNDS[car.effort];
  const overdue = isOverdue(car, now);
  const stale = car.clock.is_stale;

  return (
    <g>
      <title>
        {`${car.plate} · ${car.title}\nPrioridade: ${priorityLabel(car.priority)}` +
          (overdue ? "\nPrazo vencido" : "") +
          (stale ? "\nParado há muito tempo" : "") +
          (car.hazard_on ? "\nPisca-alerta: aguardando terceiro" : "")}
      </title>

      {selected && (
        <rect
          x={-bounds.w / 2 - 6}
          y={-bounds.h / 2 - 6}
          width={bounds.w + 12}
          height={bounds.h + 12}
          rx={10}
          className="vehicle-selected"
        />
      )}

      {/* Tempo parado vencido: carro esmaecido (cinza) e coberto de poeira. */}
      <g className={stale ? "vehicle-stale" : undefined}>
        {car.effort === "moto" && <Moto color={color} />}
        {car.effort === "carro" && <Carro color={color} />}
        {car.effort === "caminhao" && <Caminhao color={color} />}
        {stale && <Dust bounds={bounds} />}
        <text x={car.effort === "caminhao" ? -20 : 0} y={car.effort === "moto" ? 6 : 8} className="vehicle-icon">
          {car.task_type.icon}
        </text>
      </g>

      <Plate car={car} bounds={bounds} />

      {car.hazard_on && <HazardLights bounds={bounds} />}
      {stale && <StaleBadge bounds={bounds} />}
      {overdue && <ExpiredMeter bounds={bounds} />}
    </g>
  );
}

// Veículo animado no andar: entra pela rampa, desliza entre vagas e sai pela rampa.
export default function Vehicle({ car, x, y, ramp, selected, onClick, now }) {
  return (
    <motion.g
      initial={{ x: ramp.x, y: ramp.y, opacity: 0 }}
      animate={{ x, y, opacity: 1 }}
      exit={{ x: ramp.x, y: ramp.y, opacity: 0 }}
      transition={{ duration: 1.1, ease: "easeInOut" }}
      onClick={onClick}
      style={{ cursor: "pointer" }}
    >
      <VehicleShape car={car} now={now} selected={selected} />
    </motion.g>
  );
}

function Moto({ color }) {
  return (
    <g>
      <ellipse cx={0} cy={-26} rx={5} ry={8} fill="#222" />
      <ellipse cx={0} cy={26} rx={5} ry={8} fill="#222" />
      <rect x={-9} y={-28} width={18} height={56} rx={9} fill={color} stroke="#0003" />
      <rect x={-17} y={-20} width={34} height={5} rx={2} fill="#333" />
      <rect x={-6} y={-4} width={12} height={20} rx={5} fill="#222" />
    </g>
  );
}

function Carro({ color }) {
  return (
    <g>
      <rect x={-27} y={-48} width={54} height={96} rx={12} fill={color} stroke="#0003" strokeWidth={2} />
      <rect x={-21} y={-30} width={42} height={16} rx={4} fill="#1d2b3a" opacity={0.75} />
      <rect x={-19} y={26} width={38} height={11} rx={3} fill="#1d2b3a" opacity={0.75} />
      <rect x={-20} y={-12} width={40} height={36} rx={6} fill="#ffffff22" />
    </g>
  );
}

// Caminhão ocupa duas vagas vizinhas: desenhado deitado, com a cabine à direita.
function Caminhao({ color }) {
  return (
    <g>
      <rect x={-75} y={-32} width={108} height={64} rx={6} fill={color} stroke="#0003" strokeWidth={2} />
      <line x1={-60} y1={-32} x2={-60} y2={32} stroke="#0002" strokeWidth={2} />
      <line x1={-5} y1={-32} x2={-5} y2={32} stroke="#0002" strokeWidth={2} />
      <rect x={37} y={-28} width={38} height={56} rx={9} fill={color} stroke="#0003" strokeWidth={2} />
      <rect x={37} y={-28} width={38} height={56} rx={9} fill="#0002" />
      <rect x={62} y={-22} width={9} height={44} rx={3} fill="#1d2b3a" opacity={0.8} />
    </g>
  );
}

function Plate({ car, bounds }) {
  const x = car.effort === "caminhao" ? -20 : 0;
  const y = bounds.h / 2 - (car.effort === "caminhao" ? 2 : 0);
  return (
    <g transform={`translate(${x}, ${y})`}>
      <rect x={-24} y={-2} width={48} height={14} rx={2} className="plate" />
      <text x={0} y={9} className="plate-text">
        {car.plate}
      </text>
    </g>
  );
}

function Dust({ bounds }) {
  // Pontinhos "de poeira" espalhados de forma determinística sobre o veículo.
  const dots = [];
  for (let i = 0; i < 14; i++) {
    dots.push(
      <circle
        key={i}
        cx={((i * 37) % bounds.w) - bounds.w / 2 + 4}
        cy={((i * 53) % bounds.h) - bounds.h / 2 + 4}
        r={2 + (i % 3)}
        fill="#8a7a60"
        opacity={0.55}
      />
    );
  }
  return <g>{dots}</g>;
}

function StaleBadge({ bounds }) {
  return (
    <g transform={`translate(${-bounds.w / 2 - 4}, ${-bounds.h / 2 - 4})`}>
      <circle r={11} fill="#6b5d45" stroke="#fff" strokeWidth={2} />
      <text y={4} className="badge-text">
        zz
      </text>
    </g>
  );
}

// Prazo vencido: parquímetro vermelho pulsando no canto do veículo.
// O <g> externo posiciona; o motion.g interno anima. (Se o motion.g tivesse o
// atributo transform, o Framer Motion o sobrescreveria com a animação.)
function ExpiredMeter({ bounds }) {
  return (
    <g transform={`translate(${bounds.w / 2 + 4}, ${-bounds.h / 2 - 2})`}>
      <motion.g animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 1.4, repeat: Infinity }}>
        <rect x={-2} y={4} width={4} height={16} fill="#555" />
        <circle r={10} fill="#d83b3b" stroke="#fff" strokeWidth={2} />
        <text y={4} className="badge-text">
          !
        </text>
      </motion.g>
    </g>
  );
}

// Pisca-alerta: setas âmbar piscando dos dois lados do veículo.
function HazardLights({ bounds }) {
  const offset = bounds.w / 2 + 8;
  return (
    <motion.g animate={{ opacity: [1, 0.1, 1] }} transition={{ duration: 0.9, repeat: Infinity }}>
      <polygon points={`${-offset},0 ${-offset + 10},-9 ${-offset + 10},9`} fill="#ffb300" stroke="#7a5200" />
      <polygon points={`${offset},0 ${offset - 10},-9 ${offset - 10},9`} fill="#ffb300" stroke="#7a5200" />
    </motion.g>
  );
}
