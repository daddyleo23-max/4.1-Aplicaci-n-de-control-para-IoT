import { config, hasSelectedVehicle } from './config.js';
import { currentUser, currentToken } from './account-session.js';
import { request } from './api-client.js';
import { setControlGrant } from './control-session.js';

const panel = document.querySelector('#buyer-control');
const status = panel.querySelector('[role="status"]');
const acquire = panel.querySelector('[data-acquire]');
const release = panel.querySelector('[data-release]');
let lease = null;
let epoch = 0;
let pending = false;
let heartbeat;

function eligible() {
  return config.sessionAuth && currentUser()?.rol === 'USUARIO' && hasSelectedVehicle();
}
function render(message) {
  panel.hidden = !eligible();
  acquire.disabled = pending || !!lease;
  release.disabled = pending || !lease;
  if (message) status.textContent = message;
}
async function call(path, token) {
  return (await request(path, { method: 'POST', accountBound: false,
    headers: { Authorization: 'Bearer ' + token } })).data;
}
function block() {
  setControlGrant(null);
  clearInterval(heartbeat);
}
async function close(message = 'Control liberado. Puedes seguir consultando el monitoreo.') {
  if (!lease || pending) return;
  const old = lease;
  const version = ++epoch;
  pending = true;
  block();
  render('Solicitando DETENER y liberación…');
  old.socket?.close();
  try {
    await call(`/control/${old.id}/cerrar`, old.token);
    if (version !== epoch) return;
    lease = null;
    status.textContent = message;
  } catch (error) {
    if (version !== epoch) return;
    status.textContent = 'No se confirmó el cierre. ' + error.message + ' Puedes reintentar Liberar control; el servidor conserva su caducidad.';
  } finally {
    if (version === epoch) { pending = false; render(); }
  }
}
acquire.addEventListener('click', async () => {
  if (!eligible() || pending || lease) return;
  const version = ++epoch;
  const token = currentToken();
  const unit = config.vehicleId;
  pending = true;
  render('Solicitando reserva exclusiva…');
  try {
    const data = await call(`/vehiculos/${unit}/control/reservar`, token);
    if (version !== epoch || token !== currentToken() || unit !== config.vehicleId) {
      await call(`/control/${data.id_control}/cerrar`, token);
      return;
    }
    lease = { id: data.id_control, unit, token, socket: null, ack: performance.now() };
    const socket = new WebSocket(config.apiBaseUrl.replace(/^http/, 'ws') + `/ws/control/${data.id_control}`);
    lease.socket = socket;
    socket.addEventListener('open', () => {
      if (version !== epoch) { socket.close(); return; }
      socket.send(JSON.stringify({ tipo: 'autenticar', token }));
    });
    socket.addEventListener('message', event => {
      if (version !== epoch || !lease) return;
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (data.tipo === 'control_autorizado' || data.tipo === 'control_renovado') {
        lease.ack = performance.now();
        setControlGrant({ token, unit });
        render('Control exclusivo autorizado para esta pestaña.');
      }
    });
    socket.addEventListener('close', () => {
      if (version === epoch) { block(); void close('Canal desconectado; control liberado. Adquiérelo nuevamente para operar.'); }
    });
    socket.addEventListener('error', () => {
      if (version === epoch) { block(); void close('El canal de control se cerró.'); }
    });
    heartbeat = setInterval(() => {
      if (version !== epoch || !lease) return;
      if (performance.now() - lease.ack > 25000) {
        block(); void close('La renovación no fue confirmada; control liberado.');
      } else if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ tipo: 'renovar' }));
      }
    }, 10000);
    render('Reserva creada. Autorizando canal de control…');
  } catch (error) {
    if (version === epoch) {
      block();
      status.textContent = error.message;
      if (lease) { pending = false; await close('No se pudo iniciar el canal; control liberado.'); }
    }
  } finally {
    if (version === epoch) { pending = false; render(); }
  }
});
release.addEventListener('click', () => void close());

function reset() {
  const old = lease;
  epoch++;
  block();
  lease = null;
  pending = false;
  old?.socket?.close();
  if (old) void call(`/control/${old.id}/cerrar`, old.token).catch(() => {});
  render('Monitoreo disponible. Adquiere el control para enviar movimientos o demos.');
}
document.addEventListener('iot:account-session', reset);
document.addEventListener('iot:select-vehicle', reset);
document.addEventListener('iot:view', event => {
  if (event.detail.name === 'control') return;
  if (pending && !lease) { epoch++; pending = false; block(); render(); }
  else void close();
});
window.addEventListener('hashchange', () => {
  if (location.hash && location.hash !== '#control') void close();
});
window.addEventListener('pagehide', () => {
  block();
  if (!lease) return;
  lease.socket?.close();
  void fetch(new URL(`/control/${lease.id}/cerrar`, config.apiBaseUrl), {
    method: 'POST', headers: { Authorization: 'Bearer ' + lease.token }, keepalive: true,
  }).catch(() => {});
});
render();
