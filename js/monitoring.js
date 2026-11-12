import { config } from './config.js';
import { api } from './api-client.js';

const $ = (selector) => document.querySelector(selector);
const view = $('#view-monitor');
const latestCommand = $('#monitor-latest-command');
const latestVehicle = $('#monitor-latest-vehicle');
const latestCode = $('#monitor-latest-code');
const latestTime = $('#monitor-latest-time');
const latestSource = $('#monitor-latest-source');
const historyMessage = $('#history-message');
const historyCount = $('#history-count');
const historyRows = $('#history-rows');
const historyWrap = $('#history-table-wrap');

let active = false;
let stateEpoch = 0;
let historyEpoch = 0;
let eventVersion = 0;
let currentLatestTimestamp = '';
let knownVehicleName = 'Montacargas IoT';

function vehicleIdOf(payload) {
  const value = payload?.id_vehiculo ?? payload?.estado?.id_vehiculo;
  return Number(value);
}

function timestampOf(payload) {
  return payload?.timestamp || payload?.fecha_actualizacion || payload?.fecha_hora || payload?.estado?.fecha_actualizacion || '';
}

function timestampRank(value) {
  if (!/(?:Z|[+-]\d{2}:?\d{2})$/i.test(String(value || ''))) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatTimestamp(raw) {
  if (!raw) return { date: 'Sin fecha', time: 'Sin hora', dateTime: '' };
  const text = String(raw);
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text);
  // Los GET de estado e historial entregan UTC sin sufijo; se contrastó
  // fecha_actualizacion con el evento WSS del mismo instante (offset -06:00).
  const iso = hasZone ? text : /T| /.test(text) ? `${text.replace(' ', 'T')}Z` : text;
  const date = new Date(iso);
  if (!Number.isNaN(date.getTime())) {
    const options = { timeZone: 'America/Mexico_City' };
    return {
      date: new Intl.DateTimeFormat('es-MX', { ...options, year: 'numeric', month: '2-digit', day: '2-digit' }).format(date),
      time: new Intl.DateTimeFormat('es-MX', { ...options, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(date),
      dateTime: date.toISOString(),
    };
  }
  return { date: text, time: '', dateTime: '' };
}

function showLatest(payload, source, { permitOlder = false } = {}) {
  const data = payload?.estado || payload;
  const eventLabels = {
    estado_inicial: 'Estado inicial recibido',
    demo_inicio: 'DEMO iniciada',
    demo_fin: 'DEMO finalizada',
    demo_cancelada: 'DEMO cancelada',
    demo_error: 'Error reportado por DEMO',
  };
  const name = data?.comando || payload?.comando || data?.nombre || eventLabels[payload?.tipo] || 'Estado recibido';
  const stamp = timestampOf(payload);
  if (!permitOlder && stamp && currentLatestTimestamp && timestampRank(stamp) && timestampRank(currentLatestTimestamp) && timestampRank(stamp) < timestampRank(currentLatestTimestamp)) return;
  if (stamp) currentLatestTimestamp = stamp;
  latestCommand.textContent = String(name);
  const reportedVehicle = data?.vehiculo || payload?.vehiculo || knownVehicleName;
  latestVehicle.textContent = `${reportedVehicle} · Vehículo ${config.vehicleId}`;
  const code = data?.codigo ?? payload?.codigo;
  latestCode.textContent = code === undefined || code === null ? '' : `Código ${code}`;
  const formatted = formatTimestamp(stamp);
  latestTime.textContent = stamp ? `${formatted.date} · ${formatted.time}${formatted.dateTime ? ' · hora de Ciudad de México' : ' · hora reportada por backend; zona no indicada'}` : 'Fecha y hora no proporcionadas';
  latestTime.dateTime = formatted.dateTime;
  latestSource.textContent = source;
}

function extractRecords(response) {
  const candidates = [response?.historial, response?.movimientos, response?.registros, response?.data?.historial, response?.data?.movimientos];
  return candidates.find(Array.isArray) || [];
}

function recordTimestamp(record) {
  return record?.fecha_hora || record?.timestamp || record?.fecha_actualizacion || '';
}

function renderHistory(response) {
  const records = extractRecords(response).filter((record) => Number(record?.id_vehiculo ?? config.vehicleId) === config.vehicleId);
  // El endpoint confirmado ya devuelve filas en orden más reciente → más antigua;
  // conservarlo evita inventar una zona horaria para los datetime sin offset.
  const latestTen = records.slice(0, 10);
  historyRows.replaceChildren();
  historyCount.textContent = `${latestTen.length} / 10 registros`;
  historyWrap.hidden = latestTen.length === 0;
  historyMessage.hidden = latestTen.length > 0;
  historyMessage.textContent = latestTen.length ? '' : 'Sin movimientos persistidos para este vehículo.';

  for (const [index, record] of latestTen.entries()) {
    const row = document.createElement('tr');
    const stamp = formatTimestamp(recordTimestamp(record));
    const values = [String(index + 1), record?.comando || 'Comando sin nombre', stamp.date, stamp.time || 'Sin hora'];
    for (const [column, value] of values.entries()) {
      const cell = document.createElement(column === 0 ? 'th' : 'td');
      if (column === 0) cell.scope = 'row';
      cell.textContent = String(value);
      row.append(cell);
    }
    historyRows.append(row);
  }
}

async function syncState() {
  const request = ++stateEpoch;
  const eventAtStart = eventVersion;
  try {
    const state = await api.vehicleState();
    if (request !== stateEpoch || eventAtStart !== eventVersion) return;
    if (Number(state?.id_vehiculo) !== config.vehicleId) return;
    if (state?.vehiculo) knownVehicleName = state.vehiculo;
    showLatest(state, 'Estado consultado por REST · API/RDS', { permitOlder: true });
  } catch (error) {
    if (request !== stateEpoch) return;
    latestSource.textContent = latestCommand.textContent === 'Cargando estado…'
      ? `No se pudo consultar el estado: ${error.message}`
      : `No se pudo actualizar; se conserva el último dato conocido. ${error.message}`;
  }
}

async function syncHistory() {
  const request = ++historyEpoch;
  historyMessage.hidden = false;
  historyMessage.textContent = 'Consultando historial persistido…';
  historyWrap.hidden = true;
  try {
    const result = await api.vehicleHistory();
    if (request !== historyEpoch) return;
    renderHistory(result);
  } catch (error) {
    if (request !== historyEpoch) return;
    historyRows.replaceChildren();
    historyWrap.hidden = true;
    historyCount.textContent = 'No disponible';
    historyMessage.hidden = false;
    historyMessage.textContent = `No se pudo cargar el historial: ${error.message}`;
  }
}

export async function syncMonitoring() {
  if (!active) return;
  await Promise.allSettled([syncState(), syncHistory()]);
}

function setView(name, updateUrl = true) {
  const monitor = name === 'monitor';
  active = monitor;
  $('#view-control').hidden = monitor;
  view.hidden = !monitor;
  $('#tab-control').classList.toggle('is-active', !monitor);
  $('#tab-monitor').classList.toggle('is-active', monitor);
  $('#tab-control').setAttribute('aria-pressed', String(!monitor));
  $('#tab-monitor').setAttribute('aria-pressed', String(monitor));
  if (updateUrl) history.replaceState(null, '', monitor ? '#monitoreo' : '#control');
  if (monitor) syncMonitoring();
}

$('#tab-control').addEventListener('click', () => setView('control'));
$('#tab-monitor').addEventListener('click', () => setView('monitor'));
$('#monitor-refresh').addEventListener('click', syncMonitoring);

document.addEventListener('iot:ws-state', (event) => {
  if (event.detail?.state === 'online' && active) syncMonitoring();
});

document.addEventListener('iot:ws-message', (event) => {
  const payload = event.detail;
  if (!payload || vehicleIdOf(payload) !== config.vehicleId) return;
  const type = String(payload.tipo || '');
  const isIndividual = type === 'movimiento';
  const isState = type === 'estado_inicial';
  const isDemo = ['demo_inicio', 'demo_movimiento', 'demo_fin', 'demo_cancelada', 'demo_error'].includes(type);
  if (!isIndividual && !isState && !isDemo) return;
  eventVersion += 1;
  stateEpoch += 1;
  if (isState && payload.estado?.vehiculo) knownVehicleName = payload.estado.vehiculo;
  showLatest(payload, `Evento WSS recibido · ${isIndividual ? 'movimiento individual' : isDemo ? 'evento DEMO' : 'estado inicial'}`);
  if (isIndividual && active) syncHistory();
});

window.addEventListener('hashchange', () => setView(window.location.hash === '#monitoreo' ? 'monitor' : 'control', false));

document.addEventListener('iot:vehicle-name', (event) => {
  if (event.detail?.name) knownVehicleName = event.detail.name;
});

// Las vistas se comparten dentro del mismo documento; el hash permite enlazar directamente.
if (window.location.hash === '#monitoreo') setView('monitor', false);
