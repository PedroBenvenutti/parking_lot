// Navegação do prédio: lista de andares com ocupação, mais pátio e configuração
// (quando o usuário tem permissão). O backend só manda os andares que o usuário pode ver.
export default function BuildingNav({ floors, view, onNavigate, me }) {
  // Andares de cima para baixo, como num prédio.
  const ordered = [...floors].sort((a, b) => b.position - a.position);
  return (
    <nav className="building">
      <h2>Prédio</h2>
      {ordered.map((floor) => {
        const ratio = floor.occupied / floor.capacity;
        const active = view.kind === "floor" && view.id === floor.id;
        return (
          <button
            key={floor.id}
            className={active ? "floor-btn active" : "floor-btn"}
            onClick={() => onNavigate({ kind: "floor", id: floor.id })}
          >
            <span className="floor-num">{floor.position}º</span>
            <span className="floor-owner">
              {floor.owner.name}
              {floor.id === me.owned_floor_id && " (você)"}
            </span>
            <span className="occupancy" title={`${floor.occupied} de ${floor.capacity} vagas ocupadas`}>
              <span
                className={ratio >= 1 ? "occupancy-bar full" : "occupancy-bar"}
                style={{ width: `${Math.min(ratio, 1) * 100}%` }}
              />
            </span>
            <span className="small muted">
              {floor.occupied}/{floor.capacity}
            </span>
          </button>
        );
      })}
      {floors.length === 0 && <p className="muted small">Você ainda não tem um andar.</p>}
      {me.is_manager && (
        <button
          className={view.kind === "admin" ? "floor-btn active" : "floor-btn"}
          onClick={() => onNavigate({ kind: "admin" })}
        >
          ⚙️ Configuração
        </button>
      )}
    </nav>
  );
}
