import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken, setToken } from "./api/client.js";
import { useRealtime } from "./ws/useRealtime.js";
import Admin from "./components/Admin.jsx";
import BuildingNav from "./components/BuildingNav.jsx";
import CarPanel from "./components/CarPanel.jsx";
import Floor from "./components/Floor.jsx";
import Gate from "./components/Gate.jsx";
import Legend from "./components/Legend.jsx";
import Login from "./components/Login.jsx";
import Patio from "./components/Patio.jsx";

export default function App() {
  const [me, setMe] = useState(null);
  const [checkingSession, setCheckingSession] = useState(Boolean(getToken()));

  const loadMe = useCallback(async () => {
    try {
      setMe(await api("/auth/me"));
    } catch {
      setToken(null);
      setMe(null);
    } finally {
      setCheckingSession(false);
    }
  }, []);

  useEffect(() => {
    if (getToken()) loadMe();
  }, [loadMe]);

  if (checkingSession) return <div className="loading">Carregando…</div>;
  if (!me) return <Login onLoggedIn={loadMe} />;
  return (
    <Garage
      me={me}
      onLogout={() => {
        setToken(null);
        setMe(null);
      }}
    />
  );
}

// Upsert/remoção por id em listas de carros.
function upsert(list, car) {
  return list.some((c) => c.id === car.id) ? list.map((c) => (c.id === car.id ? car : c)) : [...list, car];
}
function without(list, carId) {
  return list.filter((c) => c.id !== carId);
}

function Garage({ me, onLogout }) {
  const canSeePatio = me.is_manager || me.is_valet;
  const canSeePatioCar = (car) => me.is_manager || (me.is_valet && me.valet_type_ids.includes(car.task_type.id));

  const [floors, setFloors] = useState([]);
  const [taskTypes, setTaskTypes] = useState([]);
  const [view, setView] = useState(me.owned_floor_id ? { kind: "floor", id: me.owned_floor_id } : { kind: "none" });
  const [floorDetail, setFloorDetail] = useState(null);
  const [patioCars, setPatioCars] = useState([]);
  const [selectedCar, setSelectedCar] = useState(null);
  const [gateOpen, setGateOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [now, setNow] = useState(new Date());
  // Ref com o carro selecionado atual, para ler dentro do callback do WebSocket.
  const selectedRef = useRef(null);
  selectedRef.current = selectedCar;

  // Relógio local: re-renderiza a cada 30s para atualizar "vence em..." e o prazo vencido.
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(timer);
  }, []);

  const showError = (text) => setToast({ kind: "error", text });
  const showInfo = (text) => setToast({ kind: "info", text });
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  // --- carregamento -------------------------------------------------------------

  const loadFloors = useCallback(async () => {
    const data = await api("/floors");
    setFloors(data);
    return data;
  }, []);

  const loadTaskTypes = useCallback(async () => setTaskTypes(await api("/task-types")), []);

  useEffect(() => {
    loadTaskTypes();
    loadFloors().then((data) => {
      // Sem andar próprio (gestor/manobrista), começa pelo primeiro andar.
      if (!me.owned_floor_id && data.length > 0) {
        const first = [...data].sort((a, b) => a.position - b.position)[0];
        setView({ kind: "floor", id: first.id });
      }
    });
    if (canSeePatio) api("/patio").then(setPatioCars);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (view.kind !== "floor") return;
    let cancelled = false;
    setFloorDetail(null);
    api(`/floors/${view.id}`)
      .then((data) => !cancelled && setFloorDetail(data))
      .catch((err) => showError(err.message));
    return () => {
      cancelled = true;
    };
  }, [view]);

  // A ocupação na navegação muda a cada movimentação; agrupamos recargas próximas.
  const floorsTimer = useRef(null);
  const refreshFloorsSoon = useCallback(() => {
    clearTimeout(floorsTimer.current);
    floorsTimer.current = setTimeout(loadFloors, 400);
  }, [loadFloors]);

  // --- aplicar mudanças (vindas da API ou do WebSocket) ----------------------------

  const applyCar = useCallback(
    (car) => {
      setFloorDetail((detail) => {
        if (!detail) return detail;
        const here = car.status === "estacionado" && car.floor_id === detail.id;
        return { ...detail, cars: here ? upsert(detail.cars, car) : without(detail.cars, car.id) };
      });
      if (canSeePatio) {
        setPatioCars((list) => (car.status === "patio" && canSeePatioCar(car) ? upsert(list, car) : without(list, car.id)));
      }
      setSelectedCar((current) => (current && current.id === car.id ? car : current));
      refreshFloorsSoon();
    },
    [refreshFloorsSoon] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const refreshSelected = useCallback((carId) => {
    api(`/cars/${carId}`)
      .then((car) => setSelectedCar((current) => (current && current.id === car.id ? car : current)))
      .catch(() => setSelectedCar((current) => (current && current.id === carId ? null : current)));
  }, []);

  const handleRealtime = useCallback(
    (message) => {
      if (message.type === "car_upserted") {
        applyCar(message.car);
      } else if (message.type === "car_removed") {
        if (message.channel === "patio") {
          setPatioCars((list) => without(list, message.car_id));
        } else {
          const floorId = Number(message.channel.split(":")[1]);
          setFloorDetail((detail) =>
            detail && detail.id === floorId ? { ...detail, cars: without(detail.cars, message.car_id) } : detail
          );
        }
        if (selectedRef.current?.id === message.car_id) refreshSelected(message.car_id);
        refreshFloorsSoon();
      } else if (message.type === "floor_updated") {
        setFloorDetail((detail) => (detail && detail.id === message.floor.id ? message.floor : detail));
        refreshFloorsSoon();
      }
    },
    [applyCar, refreshSelected, refreshFloorsSoon]
  );

  const channels = [...(canSeePatio ? ["patio"] : []), ...(view.kind === "floor" ? [`floor:${view.id}`] : [])];
  useRealtime(channels, handleRealtime);

  // --- estacionar / trocar de vaga ------------------------------------------------

  // `placing` é o veículo que está esperando o clique numa vaga (null = nenhum).
  let placing = null;
  if (selectedCar && floorDetail) {
    const fromPatio =
      selectedCar.status === "patio" && canSeePatioCar(selectedCar);
    const moving =
      selectedCar.status === "estacionado" &&
      selectedCar.floor_id === me.owned_floor_id &&
      floorDetail.id === me.owned_floor_id;
    if (fromPatio || moving) placing = selectedCar;
  }

  async function handleSpotClick(spot) {
    if (!placing) return;
    try {
      const car =
        placing.status === "patio"
          ? await api(`/cars/${placing.id}/park`, { method: "POST", body: { floor_id: floorDetail.id, spot_id: spot.id } })
          : await api(`/cars/${placing.id}/move`, { method: "POST", body: { spot_id: spot.id } });
      applyCar(car);
      if (placing.status === "patio") setSelectedCar(null);
    } catch (err) {
      showError(err.message);
    }
  }

  // --- tela -----------------------------------------------------------------------

  // Calculado dos carros na tela (que o WebSocket mantém atualizados), não do valor carregado.
  const occupied = floorDetail ? floorDetail.cars.reduce((sum, car) => sum + car.spot_ids.length, 0) : 0;

  const roles = [
    me.owned_floor_id && "dono de andar",
    me.is_valet && "manobrista",
    me.is_manager && "gestor",
  ].filter(Boolean);

  return (
    <div className="app">
      <header className="topbar">
        <h1>🅿️ Parking Lot</h1>
        <button className="primary" onClick={() => setGateOpen(true)}>
          🚧 Cancela: nova tarefa
        </button>
        <div className="spacer" />
        <span className="muted">
          {me.name} {roles.length > 0 && `(${roles.join(", ")})`}
        </span>
        <button onClick={onLogout}>Sair</button>
      </header>

      <div className="layout">
        <BuildingNav floors={floors} view={view} onNavigate={setView} me={me} />

        <main className="center">
          {view.kind === "floor" && !floorDetail && <p className="muted">Carregando andar…</p>}
          {view.kind === "floor" && floorDetail && (
            <>
              <div className="floor-header">
                <h2>
                  {floorDetail.position}º andar · {floorDetail.owner.name}
                </h2>
                <span className={occupied >= floorDetail.capacity ? "badge full" : "badge"}>
                  {occupied}/{floorDetail.capacity} vagas
                  {occupied >= floorDetail.capacity && " · LOTADO"}
                </span>
              </div>
              {placing && (
                <p className="hint">
                  {placing.status === "patio" ? "Estacionando" : "Movendo"} <strong>{placing.plate}</strong>: clique
                  numa vaga destacada.
                  {placing.effort === "caminhao" && " Caminhão ocupa a vaga clicada e a da direita."}
                </p>
              )}
              <Floor
                key={floorDetail.id}
                floor={floorDetail}
                selectedCarId={selectedCar?.id}
                placing={placing}
                onSpotClick={handleSpotClick}
                onCarClick={setSelectedCar}
                now={now}
              />
              <Legend />
            </>
          )}
          {view.kind === "admin" && (
            <Admin
              floors={floors}
              taskTypes={taskTypes}
              onFloorsChanged={loadFloors}
              onTypesChanged={loadTaskTypes}
              onError={showError}
              onInfo={showInfo}
            />
          )}
          {view.kind === "none" && (
            <p className="muted">Você não tem um andar. Use a cancela para registrar tarefas.</p>
          )}
        </main>

        {(canSeePatio || selectedCar) && (
          <div className="sidebar">
            {selectedCar && (
              <CarPanel
                car={selectedCar}
                me={me}
                taskTypes={taskTypes}
                now={now}
                onChanged={applyCar}
                onClose={() => setSelectedCar(null)}
                onError={showError}
              />
            )}
            {canSeePatio && (
              <Patio cars={patioCars} selectedCarId={selectedCar?.id} onSelect={setSelectedCar} now={now} />
            )}
          </div>
        )}
      </div>

      {gateOpen && (
        <Gate
          taskTypes={taskTypes}
          onClose={() => setGateOpen(false)}
          onCreated={(car) => {
            setGateOpen(false);
            showInfo(`Tarefa ${car.plate} criada e enviada ao pátio`);
            applyCar(car);
          }}
        />
      )}

      {toast && <div className={`toast ${toast.kind}`}>{toast.text}</div>}
    </div>
  );
}
