const $ = (selector) => document.querySelector(selector);

export function setStatus(id, state, label, detail) {
  const card = $(`#${id}`);
  if (!card) return;
  card.dataset.state = state;
  card.querySelector('.status-value').textContent = label;
  if (detail) card.querySelector('.status-detail').textContent = detail;
  updateOverall();
}

function updateOverall() {
  const ws = $('#status-ws').dataset.state;
  const api = $('#status-api').dataset.state;
  let label = 'Conectando servicios';
  if (ws === 'online' && api === 'available') label = 'Servicios conectados';
  else if (api === 'available' && ws === 'checking') label = 'API activa · conectando WSS';
  else if (api === 'available' && ws === 'offline') label = 'API activa · WSS sin conexión';
  else if (ws === 'online' && api === 'checking') label = 'WSS activo · comprobando API';
  else if (api === 'unavailable' && ws === 'online') label = 'WSS activo · API no disponible';
  else if (api === 'unavailable') label = 'API no disponible';
  else if (ws === 'offline') label = 'Esperando WebSocket';
  $('#overall-status').textContent = label;
}

export function feedback(message, command = '') {
  const action = $('#action-feedback');
  if (action) action.textContent = message;
  const current = $('#current-command');
  if (current && command) current.textContent = command;
}

export function setEvent(message, timestamp = '') {
  $('#last-event').textContent = message;
  const time = $('#last-event-time');
  if (timestamp) {
    const date = new Date(timestamp);
    time.textContent = Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    time.dateTime = date.toISOString();
  }
}

export function setDemoStatus(message) {
  const status = $('#demo-status');
  if (status?.lastElementChild) status.lastElementChild.textContent = message;
}

const normalize = (text = '') => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().trim();
const available = (command) => Boolean(command && command.activo !== false && command.activo !== 0);

function findCommand(commands, aliases) {
  const accepted = aliases.map(normalize);
  return commands.find((command) => {
    if (!available(command)) return false;
    const name = normalize(command.nombre || '');
    return accepted.some((alias) => name === alias || name.includes(alias));
  }) || null;
}

function bindSingleCommand(button, commands, aliases, onCommand, unavailableText) {
  if (!button) return null;
  const command = findCommand(commands, aliases);
  button.disabled = !command;
  button.dataset.available = String(Boolean(command));
  if (!command) {
    button.title = unavailableText || `No hay un comando activo para: ${aliases[0]}.`;
    return null;
  }
  button.title = command.descripcion || command.nombre;
  button.addEventListener('click', () => onCommand(command));
  return command;
}

function bindTimedButton(button, shortCommand, longCommand, onShort, onLong, thresholdMs = 550) {
  if (!button) return;
  let startedAt = null;
  let measuredDuration = null;

  const start = (event) => {
    if (event.type === 'pointerdown' && event.button !== 0) return;
    if (startedAt !== null) return;
    startedAt = performance.now();
    button.dataset.pressed = 'true';
    if (event.type === 'pointerdown' && button.setPointerCapture) {
      try { button.setPointerCapture(event.pointerId); } catch { /* El dispositivo no permite captura. */ }
    }
  };
  const end = (event) => {
    if (startedAt === null) return;
    measuredDuration = performance.now() - startedAt;
    startedAt = null;
    delete button.dataset.pressed;
    if (event?.type === 'pointerup' && button.releasePointerCapture) {
      try { button.releasePointerCapture(event.pointerId); } catch { /* La captura ya se liberó. */ }
    }
  };

  button.addEventListener('pointerdown', start);
  button.addEventListener('pointerup', end);
  button.addEventListener('pointercancel', end);
  button.addEventListener('lostpointercapture', end);
  button.addEventListener('keydown', (event) => {
    if (event.repeat || ![' ', 'Enter'].includes(event.key)) return;
    start(event);
  });
  button.addEventListener('keyup', (event) => {
    if ([' ', 'Enter'].includes(event.key)) end(event);
  });
  button.addEventListener('blur', () => end());
  button.addEventListener('click', () => {
    const longPress = measuredDuration !== null && measuredDuration >= thresholdMs;
    measuredDuration = null;
    if (longPress) onLong(longCommand);
    else onShort(shortCommand);
  });
}

export function renderCommands(commands, { onCommand, onDemo, onUnavailable }) {
  const activeCount = commands.filter(available).length;
  $('#command-count').textContent = `${activeCount} comandos activos · API`;

  const bindings = [
    [$('#key-speed'), ['VELOCIDAD', 'SPEED']],
    [$('#key-fork-up'), ['SUBIR_HORQUILLA', 'SUBIR', 'RISE', 'LIFT UP']],
    [$('#key-fork-down'), ['BAJAR_HORQUILLA', 'BAJAR', 'LOWER']],
  ];
  for (const [button, aliases] of bindings) bindSingleCommand(button, commands, aliases, onCommand);

  const demoCommand = findCommand(commands, ['DEMO', 'AUTO DEMO']);
  const demoButton = $('#key-demo');
  if (demoButton) {
    demoButton.disabled = !demoCommand;
    demoButton.dataset.available = String(Boolean(demoCommand));
    demoButton.title = demoCommand ? 'Iniciar la secuencia DEMO seleccionada.' : 'La función DEMO no aparece activa en el catálogo.';
    if (demoCommand) demoButton.addEventListener('click', () => onDemo(demoCommand));
  }

  const horn = findCommand(commands, ['SONIDO', 'CLAXON', 'HORN']);
  const lights = findCommand(commands, ['LUCES', 'LUZ', 'LIGHTS', 'LIGHT']);
  // SONIDO se conserva como claxon. La música requiere un comando propio porque el firmware
  // recibe un único id_comando y no puede inferir qué control físico originó el mismo código.
  const music = findCommand(commands, ['MUSICA', 'MUSIC']);
  const power = findCommand(commands, ['POWER', 'ENCENDER']);
  const center = $('#key-power-horn');
  if (center) {
    center.disabled = !horn;
    center.dataset.available = String(Boolean(horn));
    center.title = power
      ? 'Pulsación corta: claxon. Pulsación larga: encender (pendiente de habilitar en el firmware).'
      : 'Pulsación corta: claxon. Pulsación larga: encender (comando no disponible).';
    bindTimedButton(center, horn, power,
      (command) => command ? onCommand(command) : onUnavailable('El claxon no está activo en el catálogo.'),
      () => onUnavailable('Encender desde el botón central todavía no está habilitado en el firmware.'));
  }

  const combined = $('#key-light-sound');
  if (combined) {
    const shortAction = lights;
    const longAction = music;
    combined.disabled = !shortAction && !longAction;
    combined.dataset.available = String(Boolean(shortAction || longAction));
    combined.dataset.longAvailable = String(Boolean(longAction));
    combined.title = longAction
      ? 'Pulsación corta: luces. Pulsación larga: música.'
      : 'Pulsación corta: luces. Música todavía no tiene un comando separado en el catálogo.';
    bindTimedButton(combined, shortAction, longAction,
      (command) => command ? onCommand(command) : onUnavailable('Luces no está activo en el catálogo.'),
      (command) => command ? onCommand(command) : onUnavailable('Música todavía no tiene un comando separado en el catálogo; no se envió una orden.'));
  }

  document.querySelectorAll('[data-stick-axis]').forEach((stick) => {
    stick.dataset.ready = String(commands.length > 0);
  });
}

export function renderDemos(demos) {
  const select = $('#demo-select'); select.replaceChildren();
  const first = document.createElement('option'); first.value = ''; first.textContent = demos.length ? 'Selecciona una DEMO' : 'No hay DEMOs disponibles'; select.append(first);
  for (const demo of demos) {
    const option = document.createElement('option'); option.value = String(demo.id_demo); option.textContent = demo.nombre || `DEMO ${demo.id_demo}`; option.disabled = demo.activo === false || demo.activo === 0; select.append(option);
  }
  select.disabled = !demos.length;
  $('#demo-start').disabled = true;
  $('#demo-cancel').disabled = true;
  select.addEventListener('change', () => { $('#demo-start').disabled = !select.value; });
}

export const elements = {
  sticks: [...document.querySelectorAll('[data-stick-axis]')],
  stop: $('#stop-button'),
  demoSelect: $('#demo-select'),
  demoStart: $('#demo-start'),
  demoCancel: $('#demo-cancel'),
};
