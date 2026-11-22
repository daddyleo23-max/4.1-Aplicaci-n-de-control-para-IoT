import { request } from './api-client.js';
import { config } from './config.js';

let token = '';
let epoch = 0;
let socket;
let clock;
let deadline = 0;
let online = false;
let closing = false;
let busy = false;
let status;
let remaining;
let commands;
let buttons = [];
let startPending = false;
let closeButton;
const host = () => document.querySelector('#guest-trial');

function node(tag, text, className) {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = text;
  if (className) result.className = className;
  return result;
}

async function call(path, options = {}, key = token) {
  return (await request(path, { ...options, accountBound: false,
    headers: key ? { Authorization: 'Bearer ' + key } : {} })).data;
}

function updateButtons() {
  for (const [button, command] of buttons) {
    button.disabled = !online || closing || performance.now() >= deadline || (busy && command.nombre !== 'DETENER');
  }
}

export async function closeGuestTrial(message = 'Prueba finalizada.') {
  if (closing || !token) return;
  closing = true;
  online = false;
  clearInterval(clock);
  updateButtons();
  closeButton.disabled = true;
  status.textContent = 'Solicitando cierre y DETENER…';
  const key = token;
  const version = ++epoch;
  try {
    await call('/invitados/sesion/cerrar', { method: 'POST' }, key);
    if (version !== epoch) return;
    token = '';
    status.textContent = message + ' El servidor procesó la solicitud de parada.';
    remaining.textContent = 'Prueba terminada';
    closeButton.textContent = 'Prueba finalizada';
  } catch (error) {
    if (version !== epoch) return;
    status.textContent = 'No se confirmó el cierre. ' + error.message + ' Puedes reintentarlo; la reserva tiene caducidad en el servidor.';
    closeButton.textContent = 'Reintentar cierre';
    closeButton.disabled = false;
  } finally {
    closing = false;
    socket?.close();
  }
}

async function move(command) {
  if (!online || closing || !token || (busy && command.nombre !== 'DETENER')) return;
  const version = epoch;
  if (command.nombre !== 'DETENER') busy = true;
  updateButtons();
  status.textContent = 'Solicitando ' + command.nombre + '…';
  try {
    await call('/invitados/movimientos', { method: 'POST', body: { id_comando: command.id_comando } });
    if (version === epoch) status.textContent = 'Solicitud aceptada y parada solicitada por el servidor.';
  } catch (error) {
    if (version === epoch) {
      status.textContent = error.message;
      if (error.status === 401) void closeGuestTrial('La sesión venció.');
    }
  } finally {
    if (version === epoch) { busy = false; updateButtons(); }
  }
}

export async function reserveGuestTrial(unit) {
  if (token || startPending) throw new Error('Finaliza la prueba actual antes de reservar otra unidad.');
  startPending = true;
  const version = ++epoch;
  const area = host();
  area.hidden = false;
  area.replaceChildren(node('h3', 'Prueba de ' + unit.nombre));
  status = node('p', 'Solicitando reserva exclusiva…');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  area.append(status);
  try {
    const data = await call('/invitados/sesiones', { method: 'POST', body: { id_vehiculo: unit.id_vehiculo } }, '');
    if (version !== epoch) {
      await call('/invitados/sesion/cerrar', { method: 'POST' }, data.access_token);
      return;
    }
    token = data.access_token;
    busy = closing = online = false;
    deadline = performance.now() + Math.max(0, data.segundos_restantes) * 1000;
    remaining = node('p', '', 'guest-countdown');
    remaining.setAttribute('role', 'timer');
    commands = node('div', undefined, 'account-actions guest-commands');
    buttons = [];
    for (const command of data.comandos) {
      const button = node('button', command.nombre.replaceAll('_', ' '));
      button.type = 'button';
      if (command.nombre === 'DETENER') button.className = 'guest-stop';
      button.addEventListener('click', () => void move(command));
      buttons.push([button, command]);
      commands.append(button);
    }
    closeButton = node('button', 'Finalizar prueba');
    closeButton.type = 'button';
    closeButton.addEventListener('click', () => void closeGuestTrial());
    area.append(remaining, node('p', 'Cada orden es un pulso breve. Sólo se muestran comandos autorizados.'), commands,
      node('p', 'Los eventos recibidos confirman solicitudes del servidor; no confirman por sí solos movimiento físico.'), closeButton);
    status.textContent = 'Conectando el canal de la prueba…';
    updateButtons();
    const tick = () => {
      if (version !== epoch) return;
      const seconds = Math.max(0, Math.ceil((deadline - performance.now()) / 1000));
      remaining.textContent = 'Tiempo restante: ' + seconds + ' s';
      if (seconds === 0) void closeGuestTrial('Tiempo agotado.');
    };
    tick();
    if (version !== epoch) return;
    clock = setInterval(tick, 250);
    const ws = new WebSocket(config.apiBaseUrl.replace(/^http/, 'ws') + '/ws/invitados');
    socket = ws;
    ws.addEventListener('open', () => {
      if (version !== epoch) { ws.close(); return; }
      ws.send(JSON.stringify({ tipo: 'autenticar', token }));
    });
    ws.addEventListener('message', event => {
      if (version !== epoch) return;
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (Number(data.id_vehiculo) !== unit.id_vehiculo) return;
      if (data.tipo === 'estado_inicial') {
        online = true;
        status.textContent = 'Reserva autorizada. Puedes enviar los comandos disponibles.';
        updateButtons();
      } else if (data.tipo === 'movimiento') {
        status.textContent = 'Evento del servidor: ' + data.comando;
      }
    });
    ws.addEventListener('close', () => {
      if (version !== epoch || closing || !token) return;
      online = false;
      updateButtons();
      void closeGuestTrial('Canal desconectado; prueba finalizada.');
    });
    ws.addEventListener('error', () => {
      if (version === epoch) { online = false; updateButtons(); void closeGuestTrial('No se pudo mantener el canal de control.'); }
    });
  } catch (error) {
    if (version === epoch) {
      status.textContent = error.message;
      if (token) void closeGuestTrial('La prueba no pudo iniciarse.');
    }
    throw error;
  } finally {
    startPending = false;
  }
}

document.addEventListener('iot:account-session', () => {
  if (startPending) epoch++;
  if (token) void closeGuestTrial('Se cambió la cuenta; prueba finalizada.');
});
window.addEventListener('pagehide', () => {
  if (!token) return;
  socket?.close();
  // keepalive complementa el cierre WS; la caducidad del servidor es independiente.
  void fetch(new URL('/invitados/sesion/cerrar', config.apiBaseUrl), { method: 'POST',
    headers: { Authorization: 'Bearer ' + token }, keepalive: true }).catch(() => {});
});
