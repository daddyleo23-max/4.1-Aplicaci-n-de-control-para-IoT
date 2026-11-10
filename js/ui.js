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
  $('#action-feedback').textContent = message;
  if (command) $('#current-command').textContent = command;
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

export function setDemoStatus(message) { $('#demo-status').lastElementChild.textContent = message; }

const glyphs = new Map([
  ['ADELANTE','▲'],['AVANZAR','▲'],['ATRAS','▼'],['ATRÁS','▼'],['RETROCEDER','▼'],['IZQUIERDA','◀'],['GIRAR IZQUIERDA','◀'],['DERECHA','▶'],['GIRAR DERECHA','▶'],['SUBIR','⬆'],['BAJAR','⬇'],['DETENER','■'],['DEMO','⟳▶'],['LUCES','☼'],['LUZ','☼'],['SONIDO','◖))'],['CLAXON','◖))'],['VELOCIDAD','%'],['MODO_CRUCE','◴'],['CRUCE','◴'],['POWER','⏻'],
]);
export function commandGlyph(name) {
  const upper = name.toLocaleUpperCase('es-MX');
  for (const [key, glyph] of glyphs) if (upper.includes(key)) return glyph;
  return '◆';
}

export function renderCommands(commands, { onCommand, onDemo }) {
  const grid = $('#command-grid');
  grid.replaceChildren();
  $('#command-count').textContent = `${commands.length} comandos en catálogo`;
  const enabled = (item) => item.activo !== false && item.activo !== 0;
  const positions = new Map([
    ['ADELANTE','key-forward'], ['SUBIR_HORQUILLA','key-fork-up'], ['VELOCIDAD','key-speed'],
    ['GIRAR_IZQUIERDA','key-left'], ['GIRAR_DERECHA','key-right'], ['LUCES','key-lights'],
    ['POWER','key-power'], ['ATRAS','key-back'], ['BAJAR_HORQUILLA','key-fork-down'],
    ['DEMO','key-demo'], ['MODO_CRUCE','key-cross'], ['SONIDO','key-sound'],
  ]);
  const shortLabels = new Map([
    ['ADELANTE','ADELANTE'], ['ATRAS','ATRÁS'], ['SUBIR_HORQUILLA','SUBIR'], ['BAJAR_HORQUILLA','BAJAR'],
    ['GIRAR_IZQUIERDA','IZQUIERDA'], ['GIRAR_DERECHA','DERECHA'], ['VELOCIDAD','VELOCIDAD'],
    ['LUCES','LUCES'], ['POWER','POWER'], ['DEMO','DEMO'], ['MODO_CRUCE','CRUCE'], ['SONIDO','SONIDO'],
  ]);
  const addButton = (command, position = 'key-extra') => {
    const name = command.nombre?.trim().toUpperCase() || '';
    const firmwareBlocked = name === 'POWER';
    const button = document.createElement('button');
    button.type = 'button'; button.className = `command-button remote-key ${position}${firmwareBlocked ? ' command-unverified' : ''}`;
    button.disabled = !enabled(command) || firmwareBlocked;
    button.setAttribute('aria-label', firmwareBlocked ? 'POWER no está habilitado en el firmware compartido' : name === 'DEMO' ? 'Iniciar la DEMO seleccionada' : `Enviar comando ${command.nombre}`);
    button.title = firmwareBlocked ? 'No habilitado en el sketch del ESP32' : command.descripcion || command.nombre;
    const glyph = document.createElement('span'); glyph.className = 'command-glyph'; glyph.textContent = commandGlyph(command.nombre || '');
    const label = document.createElement('span'); label.className = 'command-name'; label.textContent = shortLabels.get(name) || command.nombre || `Comando ${command.id_comando}`;
    button.append(glyph, label);
    if (!firmwareBlocked && enabled(command)) {
      button.addEventListener('click', () => name === 'DEMO' ? onDemo(command) : onCommand(command));
    }
    grid.append(button);
  };
  const byName = new Map(commands.map((item) => [item.nombre?.trim().toUpperCase(), item]));
  for (const [name, position] of positions) {
    const command = byName.get(name);
    if (command) addButton(command, position);
  }
  const knownNames = new Set([...positions.keys(), 'DETENER']);
  commands.filter((item) => !knownNames.has(item.nombre?.trim().toUpperCase())).forEach((command) => addButton(command));
  if (!grid.children.length) grid.innerHTML = '<div class="empty-state">No hay comandos disponibles en el catálogo.</div>';
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

export const elements = { joystick: $('#joystick'), knob: $('#joystick-knob'), stop: $('#stop-button'), demoSelect: $('#demo-select'), demoStart: $('#demo-start'), demoCancel: $('#demo-cancel') };
