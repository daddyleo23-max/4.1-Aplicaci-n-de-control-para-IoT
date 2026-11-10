import { config } from './config.js';
import { setEvent, setStatus } from './ui.js';

export function connectWebSocket() {
  let socket;
  let retry = 0;
  let closedByUser = false;
  let timer;
  const open = () => {
    if (closedByUser) return;
    setStatus('status-ws', retry ? 'checking' : 'checking', retry ? 'Reconectando' : 'Conectando', 'Sesión de este navegador');
    try { socket = new WebSocket(config.websocketUrl); }
    catch { scheduleRetry(); return; }
    socket.addEventListener('open', () => { retry = 0; setStatus('status-ws', 'online', 'En línea', 'Navegador conectado por WSS'); });
    socket.addEventListener('message', (event) => {
      let payload;
      try { payload = JSON.parse(event.data); } catch { setEvent('Se recibió un mensaje no JSON por WSS.'); return; }
      const type = payload?.tipo || 'evento';
      const name = payload?.comando ? ` · ${payload.comando}` : '';
      const order = Number.isInteger(payload?.orden) ? ` · paso ${payload.orden}` : '';
      setEvent(`${type}${name}${order}`, payload?.timestamp);
      if (type === 'estado_inicial' && payload?.estado?.comando) setEvent(`Estado inicial · ${payload.estado.comando}`, payload.estado.fecha_actualizacion);
      if (type === 'demo_inicio') document.dispatchEvent(new CustomEvent('iot:demo-state', { detail: { active: true, message: 'DEMO en ejecución' } }));
      if (['demo_fin','demo_cancelada','demo_error'].includes(type)) document.dispatchEvent(new CustomEvent('iot:demo-state', { detail: { active: false, message: type === 'demo_fin' ? 'DEMO finalizada' : type === 'demo_cancelada' ? 'DEMO cancelada' : 'La DEMO reportó un error' } }));
    });
    socket.addEventListener('error', () => setStatus('status-ws', 'offline', 'Desconectado', 'Error en la sesión WSS'));
    socket.addEventListener('close', () => { setStatus('status-ws', 'offline', 'Desconectado', 'Reintentando conexión WSS'); scheduleRetry(); });
  };
  const scheduleRetry = () => {
    if (closedByUser || timer) return;
    retry += 1; const delay = Math.min(1000 * 2 ** Math.min(retry, 5), 30_000);
    setStatus('status-ws', 'checking', 'Reconectando', `Nuevo intento en ${Math.round(delay / 1000)} s`);
    timer = setTimeout(() => { timer = null; open(); }, delay);
  };
  open();
  return () => { closedByUser = true; clearTimeout(timer); socket?.close(1000, 'Cierre de la aplicación'); };
}
