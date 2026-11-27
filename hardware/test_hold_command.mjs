import test from 'node:test';
import assert from 'node:assert/strict';
import { bindHoldCommand } from '../js/hold-command.js';

function setup() {
  globalThis.window = new EventTarget();
  globalThis.document = new EventTarget();
  document.hidden = false;
  class Button extends EventTarget {
    disabled = false; dataset = {};
    setPointerCapture() {}
  }
  const button = new Button(), events = [], controller = new AbortController();
  bindHoldCommand(button, 'SUBIR', command => events.push(command), () => events.push('STOP'), controller.signal);
  return { button, events, controller };
}
function fire(target, type, fields = {}) {
  const event = new Event(type, { cancelable: true });
  Object.assign(event, { button: 0, pointerId: 7, ...fields });
  target.dispatchEvent(event);
}
test('mantiene movimiento y detiene una sola vez al soltar', () => {
  const { button, events } = setup();
  fire(button, 'pointerdown'); fire(button, 'pointerdown');
  assert.deepEqual(events, ['SUBIR']);
  fire(button, 'pointerup'); fire(button, 'lostpointercapture'); fire(button, 'click', { detail: 1 });
  assert.deepEqual(events, ['SUBIR', 'STOP']);
});
test('cancela por pérdida de foco, cancelación o captura', () => {
  for (const type of ['blur', 'pointercancel', 'lostpointercapture']) {
    const { button, events } = setup();
    fire(button, 'pointerdown'); fire(button, type);
    assert.deepEqual(events, ['SUBIR', 'STOP']);
  }
});
test('espacio y Enter mantienen/soltar sin repeticiones del teclado', () => {
  for (const key of [' ', 'Enter']) {
    const { button, events } = setup();
    fire(button, 'keydown', { key, repeat: false }); fire(button, 'keydown', { key, repeat: true });
    assert.deepEqual(events, ['SUBIR']);
    fire(button, 'keyup', { key });
    assert.deepEqual(events, ['SUBIR', 'STOP']);
  }
});
test('cambio de pestaña o ventana y abortar controles solicitan STOP', () => {
  for (const kind of ['window', 'document', 'abort']) {
    const { button, events, controller } = setup();
    fire(button, 'pointerdown');
    if (kind === 'window') fire(window, 'blur');
    if (kind === 'document') { document.hidden = true; fire(document, 'visibilitychange'); }
    if (kind === 'abort') controller.abort();
    assert.deepEqual(events, ['SUBIR', 'STOP']);
    controller.abort();
  }
});
test('no actúa deshabilitado ni con botón secundario', () => {
  const { button, events } = setup();
  fire(button, 'pointerdown', { button: 2 });
  button.disabled = true; fire(button, 'pointerdown');
  assert.deepEqual(events, []);
});
test('clic accesible produce toque seguido de STOP', () => {
  const { button, events } = setup();
  fire(button, 'click', { detail: 0 });
  assert.deepEqual(events, ['SUBIR', 'STOP']);
});
