import { elements, feedback } from './ui.js';

const aliases = {
  up: ['ADELANTE','AVANZAR','FORWARD'], down: ['ATRAS','ATRÁS','RETROCEDER','BACKWARD'],
  left: ['IZQUIERDA','GIRAR IZQUIERDA','TURN LEFT'], right: ['DERECHA','GIRAR DERECHA','TURN RIGHT'],
};
const normalize = (text = '') => text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase();

export function bindJoystick(commands, sendCommand, sendStop) {
  const pad = elements.joystick; const knob = elements.knob; let pointer = null; let active = null;
  const find = (direction) => commands.find((command) => aliases[direction].some((name) => normalize(command.nombre).includes(normalize(name))) && command.activo !== false);
  // Keep the last accepted vector state separately so neutral can request stop.
  let moving = false;
  const apply = (direction) => {
    if (!direction) { if (moving) sendStop(); moving = false; active = null; feedback('Mando en posición neutral', 'EN ESPERA'); return; }
    const command = find(direction);
    knob.style.left = `${50 + (direction === 'left' ? -27 : direction === 'right' ? 27 : 0)}%`;
    knob.style.top = `${50 + (direction === 'up' ? -27 : direction === 'down' ? 27 : 0)}%`;
    if (!command) { feedback(`Falta comando de ${direction} en el catálogo`, 'SIN ASIGNAR'); return; }
    if (active !== command.id_comando) { active = command.id_comando; sendCommand(command); }
    moving = true;
  };
  const directionAt = (event) => {
    const rect = pad.getBoundingClientRect(); const dx = (event.clientX - (rect.left + rect.width / 2)) / (rect.width / 2); const dy = (event.clientY - (rect.top + rect.height / 2)) / (rect.height / 2);
    const length = Math.hypot(dx, dy); const max = .68; const scale = length > max ? max / length : 1;
    knob.style.left = `${50 + dx * scale * 40}%`; knob.style.top = `${50 + dy * scale * 40}%`;
    if (length < .2) return null;
    return Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up');
  };
  pad.addEventListener('pointerdown', (event) => { if (event.button !== undefined && event.button !== 0) return; pointer = event.pointerId; pad.setPointerCapture(pointer); apply(directionAt(event)); });
  pad.addEventListener('pointermove', (event) => { if (event.pointerId === pointer) apply(directionAt(event)); });
  const release = (event) => { if (pointer !== null && (!event || event.pointerId === pointer)) { pointer = null; knob.style.left = '50%'; knob.style.top = '50%'; apply(null); } };
  pad.addEventListener('pointerup', release); pad.addEventListener('pointercancel', release); pad.addEventListener('lostpointercapture', release);
  pad.addEventListener('keydown', (event) => { const map = { ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right' }; if (map[event.key]) { event.preventDefault(); apply(map[event.key]); } else if (event.key === ' ' || event.key === 'Escape') { event.preventDefault(); apply(null); } });
  pad.addEventListener('keyup', (event) => { if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key)) { event.preventDefault(); knob.style.left = '50%'; knob.style.top = '50%'; apply(null); } });
  window.addEventListener('blur', () => release());
}
