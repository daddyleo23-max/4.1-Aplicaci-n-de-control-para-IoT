import { config } from './config.js';
import { clearSessionApiKey, initializeLocalAuth, isLocalHost, setSessionApiKey } from './auth-session.js';
import { api, ApiError } from './api-client.js';
import { elements, feedback, renderCommands, renderDemos, setDemoStatus, setEvent, setStatus } from './ui.js';
import { connectWebSocket } from './websocket-client.js';
import { bindJoystick } from './joystick.js';
import { startHealthPolling } from './connection-status.js';

let commands = [];
let stopCommand = null;
let demoRunning = false;
let requestEpoch = 0;
let stopInFlight = false;
let commandQueue = Promise.resolve();
const commandById = new Map();

await initializeLocalAuth();

function configureAuthPanel() {
  const panel = document.querySelector('#auth-panel');
  if (isLocalHost()) return;

  panel.hidden = false;
  const input = document.querySelector('#api-key-input');
  const authorize = document.querySelector('#authorize-button');
  const forget = document.querySelector('#forget-key-button');
  const help = document.querySelector('#auth-help');
  const status = document.querySelector('#auth-status');
  const secure = window.location.protocol === 'https:' && window.isSecureContext;

  if (!secure) {
    panel.classList.add('auth-http-only');
    input.disabled = true;
    input.hidden = true;
    authorize.disabled = true;
    authorize.hidden = true;
    forget.hidden = true;
    help.textContent = 'Vista LAN HTTP: lectura y diseño; las órdenes requieren HTTPS.';
    status.hidden = true;
    return;
  }

  authorize.addEventListener('click', () => {
    if (!setSessionApiKey(input.value)) {
      status.textContent = 'Escribe tu API key para autorizar esta pestaña.';
      input.focus();
      return;
    }
    input.value = '';
    status.textContent = 'Clave cargada en memoria; la API la validará al enviar una orden.';
    authorize.textContent = 'Actualizar clave';
    forget.hidden = false;
  });
  forget.addEventListener('click', () => {
    clearSessionApiKey();
    input.value = '';
    status.textContent = 'Clave olvidada en esta pestaña.';
    authorize.textContent = 'Autorizar';
    forget.hidden = true;
  });
}

configureAuthPanel();

function sendCommand(command, { priority = false } = {}) {
  if (!command || command.activo === false) return;
  if (demoRunning && command.nombre?.toUpperCase() !== 'DETENER') { feedback('Cancela la DEMO antes de enviar otro comando.', 'DEMO ACTIVA'); return; }
  const epoch = ++requestEpoch;
  const submit = async () => {
    if (epoch === requestEpoch || priority) feedback(`Enviando ${command.nombre}…`, command.nombre);
    try {
      const response = await api.move(command.id_comando);
      if (epoch === requestEpoch || priority) feedback(`Aceptado por API · HTTP ${response.status}`, command.nombre);
    } catch (error) {
      if (epoch === requestEpoch || priority) feedback(error instanceof ApiError ? error.message : 'No se pudo enviar el comando.', command.nombre);
    }
  };
  const pending = commandQueue.then(submit, submit);
  commandQueue = pending.then(() => undefined, () => undefined);
  return pending;
}

async function stopVehicle() {
  if (stopInFlight) return;
  stopInFlight = true;
  requestEpoch += 1;
  try {
    if (demoRunning) {
      try {
        const result = await api.cancelDemo();
        setDemoRunning(false, result.data?.mensaje || 'Cancelación aceptada por API; esperando evento WSS de parada');
        return;
      } catch (error) {
        setDemoStatus(`No se confirmó la cancelación: ${error.message}`);
      }
    }
    if (!stopCommand) { feedback('DETENER no aparece en el catálogo de la API.', 'DETENER NO DISPONIBLE'); return; }
    await sendCommand(stopCommand, { priority: true });
  } finally {
    stopInFlight = false;
  }
}

function setDemoRunning(active, message) {
  demoRunning = active;
  elements.demoStart.disabled = active || !elements.demoSelect.value;
  elements.demoCancel.disabled = !active;
  setDemoStatus(message);
}

async function loadInitialData() {
  const [vehicleResult, commandResult, demoResult] = await Promise.allSettled([api.vehicle(), api.commands(), api.demos()]);
  if (vehicleResult.status === 'fulfilled') {
    const vehicle = vehicleResult.value;
    document.querySelector('#vehicle-name').textContent = vehicle.nombre || `Vehículo ${config.vehicleId}`;
    document.querySelector('.eyebrow').textContent = `MANDO TRASPEED · VEHÍCULO ${String(vehicle.id_vehiculo || config.vehicleId).padStart(2,'0')}`;
  } else feedback(`No se pudo cargar el vehículo: ${vehicleResult.reason.message}`);
  if (commandResult.status === 'fulfilled') {
    commands = commandResult.value.comandos || [];
    commands.forEach((command) => commandById.set(command.id_comando, command));
    stopCommand = commands.find((item) => item.nombre?.trim().toUpperCase() === 'DETENER') || null;
    renderCommands(commands, {
      onCommand: (command) => sendCommand(command),
      onDemo: () => {
        if (!elements.demoSelect.value) {
          setDemoStatus('Selecciona una secuencia antes de iniciar la DEMO.');
          elements.demoSelect.focus();
          return;
        }
        elements.demoStart.click();
      },
    });
    bindJoystick(commands, sendCommand, stopVehicle);
    if (!stopCommand) { elements.stop.disabled = true; elements.stop.title = 'DETENER no está disponible en el catálogo'; }
  } else {
    document.querySelector('#command-grid').innerHTML = '<div class="empty-state">No se pudo cargar el catálogo. Verifica conexión y CORS.</div>';
    document.querySelector('#command-count').textContent = 'Catálogo no disponible';
    feedback(`No se pudo cargar el catálogo: ${commandResult.reason.message}`);
  }
  if (demoResult.status === 'fulfilled') renderDemos(demoResult.value.demos || []);
  else { renderDemos([]); setDemoStatus(`No se pudo consultar DEMO: ${demoResult.reason.message}`); }
}

elements.stop.addEventListener('click', stopVehicle);
elements.demoStart.addEventListener('click', async () => {
  const idDemo = Number(elements.demoSelect.value);
  if (!Number.isInteger(idDemo) || idDemo <= 0 || demoRunning) return;
  elements.demoStart.disabled = true; setDemoStatus('Solicitando inicio de DEMO…');
  try { const result = await api.startDemo(idDemo); setDemoRunning(true, result.data?.mensaje || 'Inicio aceptado por API; esperando eventos WSS'); }
  catch (error) { setDemoRunning(false, error.message); }
});
elements.demoCancel.addEventListener('click', async () => {
  elements.demoCancel.disabled = true; setDemoStatus('Solicitando cancelación…');
  try { const result = await api.cancelDemo(); setDemoStatus(result.data?.mensaje || 'Cancelación solicitada; esperando evento WSS'); }
  catch (error) { elements.demoCancel.disabled = false; setDemoStatus(error.message); }
});
document.addEventListener('iot:demo-state', (event) => setDemoRunning(event.detail.active, event.detail.message));

connectWebSocket();
startHealthPolling();
loadInitialData();
