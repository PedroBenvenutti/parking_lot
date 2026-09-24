import { AnimatePresence, motion } from "framer-motion";
import { BOUNDS, VehicleShape } from "./Vehicle.jsx";

// Enquadramento do mini-desenho: cada forma ocupa o cartão inteiro, com folga para os indicadores.
function viewBoxFor(effort) {
  const { w, h } = BOUNDS[effort];
  const size = Math.max(w, h) / 2 + 22;
  return `${-size} ${-size} ${size * 2} ${size * 2}`;
}
import { deadlineText, isOverdue, priorityLabel } from "../format.js";

// Fila de tarefas criadas e ainda não distribuídas. O manobrista clica num carro
// e depois numa vaga livre do andar para estacioná-lo.
export default function Patio({ cars, selectedCarId, onSelect, now }) {
  return (
    <section className="patio">
      <h2>
        Pátio <span className="count">{cars.length}</span>
      </h2>
      {cars.length === 0 && <p className="muted">Nenhuma tarefa aguardando.</p>}
      <div className="patio-list">
        <AnimatePresence initial={false}>
          {cars.map((car) => (
            <motion.button
              key={car.id}
              layout
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 60 }}
              className={car.id === selectedCarId ? "patio-card selected" : "patio-card"}
              onClick={() => onSelect(car)}
            >
              <svg viewBox={viewBoxFor(car.effort)} className="patio-vehicle">
                <VehicleShape car={car} now={now} />
              </svg>
              <div className="patio-info">
                <strong>{car.plate}</strong> · {car.task_type.name}
                <div className="patio-title">{car.title}</div>
                <div className="muted small">
                  {priorityLabel(car.priority)} ·{" "}
                  <span className={isOverdue(car, now) ? "danger" : undefined}>{deadlineText(car, now)}</span>
                </div>
              </div>
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </section>
  );
}
