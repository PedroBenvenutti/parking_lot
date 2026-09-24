import { PRIORITIES } from "../format.js";

// Legenda fixa abaixo do andar: cores de prioridade, formas de esforço e indicadores.
export default function Legend() {
  return (
    <div className="legend">
      <span>
        <strong>Prioridade:</strong>
        {PRIORITIES.map((p) => (
          <span key={p.value} className="legend-item">
            <span className="swatch" style={{ background: p.color }} /> {p.label}
          </span>
        ))}
      </span>
      <span>
        <strong>Esforço:</strong> moto = baixo · carro = médio · caminhão = alto (2 vagas)
      </span>
      <span>
        <span className="legend-item">🔴❗ prazo vencido</span>
        <span className="legend-item">💤 cinza e empoeirado = parado demais</span>
        <span className="legend-item">⚠️ setas piscando = aguardando terceiro</span>
      </span>
    </div>
  );
}
