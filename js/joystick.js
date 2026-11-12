import { elements, feedback } from './ui.js';

const aliases = {
  up: ['ADELANTE', 'AVANZAR', 'FORWARD'],
  down: ['ATRAS', 'ATRÁS', 'RETROCEDER', 'BACKWARD'],
  left: ['IZQUIERDA', 'GIRAR IZQUIERDA', 'TURN LEFT'],
  right: ['DERECHA', 'GIRAR DERECHA', 'TURN RIGHT'],
};
const normalize = (text = '') => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
const enabled = (command) => command && command.activo !== false && command.activo !== 0;

export function bindJoystick(commands, sendCommand, sendStop) {
  const activeAxes = new Map();
  const findCommand = (direction) => commands.find((command) =>
    aliases[direction].some((name) => normalize(command.nombre || '').includes(normalize(name))) && enabled(command));

  const neutralize = (axis) => {
    const hadCommand = activeAxes.delete(axis);
    if (!hadCommand) return;
    const remaining = [...activeAxes.values()];
    if (!remaining.length) {
      sendStop();
      feedback('Joysticks en posición neutral · se solicitó DETENER', 'EN ESPERA');
      return;
    }
    // El endpoint recibe una orden cada vez. Reafirma el otro eje que sigue sostenido.
    sendCommand(remaining[remaining.length - 1]);
  };

  const apply = (stick, direction) => {
    const knob = stick.querySelector('.stick-knob');
    const axis = stick.dataset.stickAxis;
    if (!direction) {
      knob.style.left = '50%';
      knob.style.top = '50%';
      neutralize(axis);
      return;
    }

    const horizontal = direction === 'left' || direction === 'right';
    knob.style.left = horizontal ? (direction === 'left' ? '27%' : '73%') : '50%';
    knob.style.top = horizontal ? '50%' : (direction === 'up' ? '27%' : '73%');
    const command = findCommand(direction);
    if (!command) {
      activeAxes.delete(axis);
      feedback(`Falta el comando ${aliases[direction][0]} activo en el catálogo.`, 'SIN ASIGNAR');
      return;
    }
    if (activeAxes.get(axis)?.id_comando === command.id_comando) return;
    activeAxes.set(axis, command);
    sendCommand(command);
  };

  for (const stick of elements.sticks) {
    const axis = stick.dataset.stickAxis;
    let pointerId = null;
    let heldKey = null;

    const directionAt = (event) => {
      const rect = stick.getBoundingClientRect();
      const dx = (event.clientX - (rect.left + rect.width / 2)) / (rect.width / 2);
      const dy = (event.clientY - (rect.top + rect.height / 2)) / (rect.height / 2);
      if (axis === 'vertical') return Math.abs(dy) < 0.24 ? null : dy > 0 ? 'down' : 'up';
      return Math.abs(dx) < 0.24 ? null : dx > 0 ? 'right' : 'left';
    };
    const keyDirection = (key) => {
      if (axis === 'vertical') return key === 'ArrowUp' ? 'up' : key === 'ArrowDown' ? 'down' : null;
      return key === 'ArrowLeft' ? 'left' : key === 'ArrowRight' ? 'right' : null;
    };
    const releasePointer = (event) => {
      if (pointerId === null || (event && event.pointerId !== pointerId)) return;
      const oldPointer = pointerId;
      pointerId = null;
      apply(stick, null);
      try { stick.releasePointerCapture(oldPointer); } catch { /* El puntero ya salió del control. */ }
    };

    stick.addEventListener('pointerdown', (event) => {
      if (event.button !== undefined && event.button !== 0) return;
      event.preventDefault();
      pointerId = event.pointerId;
      try { stick.setPointerCapture(pointerId); } catch { /* El navegador puede no permitir captura. */ }
      apply(stick, directionAt(event));
    });
    stick.addEventListener('pointermove', (event) => {
      if (event.pointerId === pointerId) apply(stick, directionAt(event));
    });
    stick.addEventListener('pointerup', releasePointer);
    stick.addEventListener('pointercancel', releasePointer);
    stick.addEventListener('lostpointercapture', releasePointer);
    stick.addEventListener('keydown', (event) => {
      const direction = keyDirection(event.key);
      if (direction) {
        event.preventDefault();
        heldKey = event.key;
        apply(stick, direction);
      } else if (event.key === ' ' || event.key === 'Escape') {
        event.preventDefault();
        heldKey = null;
        apply(stick, null);
      }
    });
    stick.addEventListener('keyup', (event) => {
      if (heldKey === event.key) {
        heldKey = null;
        apply(stick, null);
      }
    });
    stick.addEventListener('blur', () => {
      if (heldKey) { heldKey = null; apply(stick, null); }
      if (pointerId !== null) releasePointer();
    });
  }

  window.addEventListener('blur', () => {
    const hadActive = activeAxes.size > 0;
    activeAxes.clear();
    for (const stick of elements.sticks) {
      const knob = stick.querySelector('.stick-knob');
      knob.style.left = '50%';
      knob.style.top = '50%';
    }
    if (hadActive) sendStop();
  });
}
