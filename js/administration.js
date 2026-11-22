import { config, selectVehicle } from './config.js';
import { request } from './api-client.js';
import { currentUser, setAccountSession } from './account-session.js';
import { reserveGuestTrial } from './guest-control.js';

const $ = (selector) => document.querySelector(selector);
const workspace = $('#account-workspace');
let screenVersion = 0;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function button(text, action) {
  const result = node('button', text);
  result.type = 'button';
  result.addEventListener('click', () => run(action));
  return result;
}

async function run(action) {
  $('#account-message').textContent = '';
  try { await action(); }
  catch (error) {
    $('#account-message').textContent = error.message;
    if (error.status === 401) {
      setAccountSession(null);
      showIdentity();
    }
  }
}

async function fetchData(path, options) {
  return (await request(path, options)).data;
}

function panel(title) {
  const result = node('section', undefined, 'panel account-panel');
  result.append(node('h3', title));
  workspace.append(result);
  return result;
}

function table(container, columns, records, actions) {
  const wrap = node('div', undefined, 'account-table-wrap');
  const result = node('table', undefined, 'account-table');
  const head = node('thead');
  const labels = node('tr');
  for (const [, label] of columns) {
    const cell = node('th', label);
    cell.scope = 'col';
    labels.append(cell);
  }
  if (actions) labels.append(node('th', 'Acciones'));
  head.append(labels);
  result.append(head);
  const body = node('tbody');
  for (const record of records) {
    const row = node('tr');
    for (const [key] of columns) row.append(node('td', record[key] ?? '—'));
    if (actions) {
      const cell = node('td', undefined, 'account-actions');
      actions(record, cell);
      row.append(cell);
    }
    body.append(row);
  }
  result.append(body);
  wrap.append(result);
  container.append(wrap);
  if (!records.length) container.append(node('p', 'Sin registros disponibles.'));
}

function form(container, fields, submitText, save) {
  const result = node('form', undefined, 'account-form');
  for (const field of fields) {
    const label = node('label', field.label);
    let input;
    if (field.options) {
      input = node('select');
      for (const [value, text] of field.options) {
        const option = node('option', text);
        option.value = String(value);
        input.append(option);
      }
    } else {
      input = node('input');
      input.type = field.type || 'text';
      if (input.type === 'password') input.autocomplete = 'new-password';
    }
    input.name = field.name;
    input.required = field.required !== false;
    input.value = String(field.value ?? '');
    if (field.maxLength) input.maxLength = field.maxLength;
    if (field.minLength) input.minLength = field.minLength;
    label.append(input);
    result.append(label);
  }
  const submit = node('button', submitText);
  submit.type = 'submit';
  result.append(submit);
  result.addEventListener('submit', (event) => {
    event.preventDefault();
    run(async () => {
      submit.disabled = true;
      try { await save(Object.fromEntries(new FormData(result))); }
      finally { submit.disabled = false; }
    });
  });
  container.append(result);
  return result;
}

function beginScreen() {
  workspace.replaceChildren();
  return ++screenVersion;
}

function selectForControl(unit) {
  selectVehicle(unit.id_vehiculo);
  $('#tab-control').click();
}

async function showSummary() {
  const version = beginScreen();
  const data = await fetchData('/admin/resumen');
  if (version !== screenVersion) return;
  const section = panel('Resumen');
  const metrics = node('div', undefined, 'account-metrics');
  const labels = {
    modelos_activos: 'Modelos activos', unidades_activas: 'Unidades activas',
    clientes_activos: 'Compradores activos', unidades_asignadas: 'Unidades asignadas',
    unidades_exhibicion: 'Unidades de exhibición',
  };
  for (const [key, label] of Object.entries(labels)) {
    const card = node('div');
    card.append(node('strong', data[key] ?? 'Sin datos'), node('span', label));
    metrics.append(card);
  }
  section.append(metrics);
}

async function showModels() {
  const version = beginScreen();
  const data = await fetchData('/admin/modelos?limite=100');
  if (version !== screenVersion) return;
  const section = panel('Modelos');
  const editor = node('div');
  const edit = (record = {}) => {
    editor.replaceChildren();
    form(editor, [
      { name: 'nombre', label: 'Nombre', value: record.nombre, maxLength: 100 },
      { name: 'descripcion', label: 'Descripción', value: record.descripcion, required: false, maxLength: 500 },
      ...(record.id_modelo ? [{ name: 'activo', label: 'Estado', value: record.activo ? '1' : '0', options: [['1', 'Activo'], ['0', 'Inactivo']] }] : []),
    ], record.id_modelo ? 'Guardar cambios' : 'Crear modelo', async (values) => {
      const path = record.id_modelo ? '/admin/modelos/' + record.id_modelo + '/actualizar' : '/admin/modelos';
      if (record.id_modelo) values.activo = values.activo === '1';
      await fetchData(path, { method: 'POST', body: values });
      await showModels();
    });
  };
  section.append(button('Nuevo modelo', () => edit()), editor);
  table(section, [['id_modelo', 'ID'], ['nombre', 'Modelo'], ['descripcion', 'Descripción'], ['activo', 'Activo'], ['publico', 'Público']],
    data.modelos, (record, cell) => {
      cell.append(button('Editar', () => edit(record)));
      if (record.activo || record.publico) cell.append(button(record.publico ? 'Retirar del catálogo' : 'Publicar en catálogo', async () => {
        await fetchData('/admin/modelos/' + record.id_modelo + '/publicacion',
          { method: 'POST', body: { publico: !record.publico } });
        await showModels();
      }));
    });
}

async function showClients() {
  const version = beginScreen();
  const data = await fetchData('/admin/clientes?limite=100');
  if (version !== screenVersion) return;
  const section = panel('Compradores');
  const editor = node('div');
  const edit = (record = {}) => {
    editor.replaceChildren();
    form(editor, [
      { name: 'nombre', label: 'Nombre', value: record.nombre, maxLength: 120 },
      { name: 'correo', label: 'Correo', type: 'email', value: record.correo, maxLength: 254 },
      ...(record.id_usuario
        ? [{ name: 'activo', label: 'Estado', value: record.activo ? '1' : '0', options: [['1', 'Activo'], ['0', 'Inactivo']] }]
        : [{ name: 'password', label: 'Contraseña inicial', type: 'password', minLength: 12, maxLength: 256 }]),
    ], record.id_usuario ? 'Guardar cambios' : 'Crear comprador', async (values) => {
      const path = record.id_usuario ? '/admin/clientes/' + record.id_usuario + '/actualizar' : '/admin/clientes';
      if (record.id_usuario) values.activo = values.activo === '1';
      await fetchData(path, { method: 'POST', body: values });
      await showClients();
    });
  };
  section.append(button('Nuevo comprador', () => edit()), editor);
  table(section, [['id_usuario', 'ID'], ['nombre', 'Comprador'], ['correo', 'Correo'], ['activo', 'Activo']],
    data.clientes, (record, cell) => cell.append(button('Editar', () => edit(record))));
}

async function showUnits() {
  const version = beginScreen();
  const [units, models, clients] = await Promise.all([
    fetchData('/admin/unidades?limite=100'), fetchData('/admin/modelos?limite=100'),
    fetchData('/admin/clientes?limite=100'),
  ]);
  if (version !== screenVersion) return;
  const section = panel('Unidades');
  const editor = node('div');
  const editUnit = (unit = {}) => {
    editor.replaceChildren();
    form(editor, [
      { name: 'nombre', label: 'Nombre de la unidad', value: unit.nombre, maxLength: 80 },
      { name: 'id_modelo', label: 'Modelo comercial', value: unit.id_modelo,
        options: models.modelos.filter(m => m.activo).map(m => [m.id_modelo, m.nombre]) },
      { name: 'identificador_unidad', label: 'Identificador único', value: unit.identificador_unidad, maxLength: 80 },
      { name: 'descripcion', label: 'Descripción', value: unit.descripcion, required: false, maxLength: 255 },
      { name: 'microcontrolador', label: 'Microcontrolador', value: unit.microcontrolador, required: false, maxLength: 50 },
      ...(unit.id_vehiculo ? [{ name: 'activo', label: 'Estado', value: unit.activo ? '1' : '0',
        options: [['1', 'Activa'], ['0', 'Inactiva']] }] : []),
    ], unit.id_vehiculo ? 'Guardar unidad' : 'Registrar unidad', async values => {
      values.id_modelo = Number(values.id_modelo);
      if (unit.id_vehiculo) values.activo = values.activo === '1';
      await fetchData(unit.id_vehiculo ? '/admin/unidades/' + unit.id_vehiculo + '/actualizar' : '/admin/unidades',
        { method: 'POST', body: values });
      await showUnits();
    });
    editor.append(button('Cancelar edición', () => editor.replaceChildren()));
  };
  section.append(button('Nueva unidad', () => editUnit()), editor);
  const searchLabel = node('label', 'Buscar en las unidades cargadas');
  const search = node('input');
  search.type = 'search';
  searchLabel.append(search);
  section.append(searchLabel);
  table(section, [['id_vehiculo', 'ID'], ['nombre', 'Unidad'], ['identificador_unidad', 'Identificador'],
    ['nombre_modelo', 'Modelo'], ['estado_comercial', 'Estado'], ['propietario', 'Propietario']],
  units.unidades, (unit, cell) => {
    cell.append(button('Editar', () => editUnit(unit)));
    if (unit.activo && !unit.id_propietario && unit.estado_comercial === 'EXHIBICION') {
      cell.append(button('Configurar Invitado', () => showGuestConfiguration(unit)));
    }
    if (unit.activo) cell.append(button('Asignar', () => {
      editor.replaceChildren();
      form(editor, [{ name: 'id_usuario', label: 'Comprador', value: unit.id_propietario,
        options: clients.clientes.filter(c => c.activo).map(c => [c.id_usuario, c.nombre + ' · ' + c.correo]) }],
      'Confirmar asignación', async values => {
        await fetchData('/admin/unidades/' + unit.id_vehiculo + '/asignar',
          { method: 'POST', body: { id_usuario: Number(values.id_usuario) } });
        await showUnits();
      });
    }));
    if (!unit.id_propietario && unit.activo) cell.append(button('Controlar', () => selectForControl(unit)),
      button('Demos', () => showDemos(unit.id_vehiculo)),
      button(unit.estado_comercial === 'EXHIBICION' ? 'Retirar exhibición' : 'Usar en exhibición', async () => {
        await fetchData('/admin/unidades/' + unit.id_vehiculo + '/exhibicion',
          { method: 'POST', body: { habilitada: unit.estado_comercial !== 'EXHIBICION' } });
        await showUnits();
      }));
  });
  search.addEventListener('input', () => {
    const term = search.value.trim().toLocaleLowerCase('es');
    for (const row of section.querySelectorAll('tbody tr')) {
      row.hidden = !row.textContent.toLocaleLowerCase('es').includes(term);
    }
  });
}

async function showAudit() {
  const version = beginScreen();
  const data = await fetchData('/admin/auditoria?limite=100');
  if (version !== screenVersion) return;
  table(panel('Auditoría'), [['fecha_utc', 'Fecha UTC'], ['id_actor', 'Actor'], ['accion', 'Acción'],
    ['tipo_recurso', 'Recurso'], ['id_recurso', 'ID'], ['resultado', 'Resultado']], data.eventos);
}

async function showMyVehicles() {
  const version = beginScreen();
  const data = await fetchData('/mis-vehiculos');
  if (version !== screenVersion) return;
  table(panel('Mis vehículos'), [['identificador_unidad', 'Identificador'], ['nombre', 'Vehículo'],
    ['nombre_modelo', 'Modelo'], ['estado_comercial', 'Estado']], data.vehiculos,
  (unit, cell) => cell.append(button('Controlar', () => selectForControl(unit)),
    button('Demos', () => showDemos(unit.id_vehiculo))));
}

async function showDemos(vehicleId = config.vehicleId) {
  const version = beginScreen();
  const [data, catalog] = await Promise.all([
    fetchData('/mis-demos?id_vehiculo=' + vehicleId), fetchData('/vehiculos/' + vehicleId + '/comandos'),
  ]);
  if (version !== screenVersion) return;
  const section = panel('Secuencias DEMO');
  section.append(button('Nueva demo', () => demoEditor(vehicleId, catalog.comandos)));
  table(section, [['nombre', 'Nombre'], ['tipo', 'Tipo'], ['revision', 'Revisión'], ['activo', 'Activa']],
    data.demos, (demo, cell) => {
      const editable = demo.tipo === 'PRIVADA' || currentUser()?.rol === 'ADMINISTRADOR';
      if (editable) cell.append(button('Editar pasos', async () => {
        const detail = await fetchData('/mis-demos/' + demo.id_demo);
        demoEditor(vehicleId, catalog.comandos, detail);
      }));
      cell.append(button('Seleccionar en control', async () => {
        selectVehicle(vehicleId);
        $('#tab-control').click();
        document.dispatchEvent(new CustomEvent('iot:choose-demo', { detail: { id: demo.id_demo } }));
      }));
    });
}

function demoEditor(vehicleId, commands, detail) {
  beginScreen();
  const section = panel(detail ? 'Editar secuencia' : 'Nueva secuencia');
  const demo = detail?.demo || {};
  const allowed = commands.filter(command => command.activo && !['DEMO', 'AUTO_DEMO', 'AUTO DEMO'].includes(command.nombre.toUpperCase()));
  const editor = form(section, [
    { name: 'nombre', label: 'Nombre', value: demo.nombre, maxLength: 80 },
    { name: 'descripcion', label: 'Descripción', value: demo.descripcion, maxLength: 255, required: false },
    { name: 'activo', label: 'Estado', value: demo.activo === 0 ? '0' : '1', options: [['1', 'Activa'], ['0', 'Inactiva']] },
  ], 'Guardar secuencia', async values => {
    const steps = Array.from(rows.children, row => ({
      id_comando: Number(row.querySelector('select').value),
      duracion_ms: Number(row.querySelector('[data-duration]').value),
      pausa_ms: Number(row.querySelector('[data-pause]').value),
    }));
    if (!steps.length || steps.length > 100) throw new Error('Agrega entre 1 y 100 pasos.');
    if (totalDuration() > 120000) throw new Error('La secuencia supera dos minutos.');
    const body = { ...values, activo: values.activo === '1', id_vehiculo: vehicleId, pasos: steps };
    if (demo.id_demo) body.revision = demo.revision;
    await fetchData(demo.id_demo ? '/mis-demos/' + demo.id_demo + '/guardar' : '/mis-demos',
      { method: 'POST', body });
    await showDemos(vehicleId);
  });
  const rows = node('div', undefined, 'demo-editor-rows');
  const duration = node('p');
  function totalDuration() {
    return Array.from(rows.querySelectorAll('input')).reduce((sum, input) => sum + Number(input.value || 0), 0);
  }
  function refreshDuration() { duration.textContent = 'Duración total ' + (totalDuration() / 1000).toFixed(1) + ' s · máximo 120 s'; }
  function addStep(step = {}) {
    const row = node('div', undefined, 'demo-editor-row');
    const select = node('select');
    select.required = true;
    select.setAttribute('aria-label', 'Comando del paso');
    for (const command of allowed) {
      const option = node('option', command.nombre);
      option.value = command.id_comando;
      select.append(option);
    }
    if (step.id_comando) select.value = step.id_comando;
    row.append(select);
    for (const [attribute, labelText, value, min, max] of [
      ['duration', 'Duración en ms', step.duracion_ms ?? 500, 1, 10000],
      ['pause', 'Pausa en ms', step.pausa_ms ?? 0, 0, 5000],
    ]) {
      const label = node('label', labelText);
      const input = node('input');
      input.type = 'number'; input.value = value; input.min = min; input.max = max;
      input.required = true;
      input.dataset[attribute] = '';
      input.addEventListener('input', refreshDuration);
      label.append(input); row.append(label);
    }
    row.append(button('Subir paso', () => { if (row.previousElementSibling) rows.insertBefore(row, row.previousElementSibling); }),
      button('Bajar paso', () => { if (row.nextElementSibling) rows.insertBefore(row.nextElementSibling, row); }),
      button('Quitar', () => { row.remove(); refreshDuration(); }));
    rows.append(row); refreshDuration();
  }
  editor.insertBefore(rows, editor.lastElementChild);
  editor.insertBefore(duration, editor.lastElementChild);
  editor.insertBefore(button('Agregar paso', () => {
    if (rows.children.length >= 100) throw new Error('Máximo 100 pasos.');
    addStep();
  }), editor.lastElementChild);
  section.append(button('Cancelar edición', () => showDemos(vehicleId)));
  for (const step of detail?.pasos || [{}]) addStep(step);
}

async function showGuestConfiguration(unit) {
  const version = beginScreen();
  const [settings, catalog] = await Promise.all([
    fetchData('/admin/unidades/' + unit.id_vehiculo + '/invitados'),
    fetchData('/vehiculos/' + unit.id_vehiculo + '/comandos'),
  ]);
  if (version !== screenVersion) return;
  const section = panel('Prueba de Invitado · ' + unit.nombre);
  section.append(node('p', 'Selecciona sólo funciones comprobadas en esta unidad. DETENER es obligatorio.'));
  const choices = new Set(['ADELANTE', 'ATRAS', 'GIRAR_IZQUIERDA', 'GIRAR_DERECHA',
    'SUBIR_HORQUILLA', 'BAJAR_HORQUILLA', 'LUCES', 'SONIDO', 'VELOCIDAD', 'DETENER']);
  const available = catalog.comandos.filter(command => command.activo && choices.has(command.nombre));
  const selected = new Set(settings.comandos || []);
  const editor = form(section, [
    { name: 'habilitada', label: 'Prueba', value: settings.habilitada ? '1' : '0', options: [['0', 'Deshabilitada'], ['1', 'Habilitada']] },
    { name: 'duracion_s', label: 'Duración de sesión (15–120 s)', type: 'number', value: settings.duracion_s ?? 60 },
    { name: 'pulso_ms', label: 'Pulso máximo (50–500 ms)', type: 'number', value: settings.pulso_ms ?? 300 },
  ], 'Guardar prueba', async values => {
    const commands = Array.from(fieldset.querySelectorAll('input:checked'), input => Number(input.value));
    if (!commands.some(id => available.find(command => command.id_comando === id)?.nombre === 'DETENER')) {
      throw new Error('Selecciona DETENER antes de guardar.');
    }
    await fetchData('/admin/unidades/' + unit.id_vehiculo + '/invitados', { method: 'POST',
      body: { habilitada: values.habilitada === '1', duracion_s: Number(values.duracion_s),
        pulso_ms: Number(values.pulso_ms), comandos: commands } });
    await showUnits();
  });
  for (const [name, min, max] of [['duracion_s', 15, 120], ['pulso_ms', 50, 500]]) {
    const input = editor.elements.namedItem(name);
    input.min = min; input.max = max; input.step = 1;
  }
  const fieldset = node('fieldset', undefined, 'guest-capabilities');
  fieldset.append(node('legend', 'Comandos permitidos'));
  for (const command of available) {
    const label = node('label');
    const input = node('input');
    input.type = 'checkbox'; input.value = command.id_comando;
    input.checked = selected.has(command.id_comando) || (!settings.configurada && command.nombre === 'DETENER');
    label.append(input, document.createTextNode(command.nombre.replaceAll('_', ' ')));
    fieldset.append(label);
  }
  if (!available.some(command => command.nombre === 'DETENER')) {
    section.append(node('p', 'Falta un comando DETENER activo. La prueba no puede habilitarse.'));
    editor.querySelector('button[type=submit]').disabled = true;
  }
  editor.insertBefore(fieldset, editor.lastElementChild);
  section.append(button('Finalizar reserva actual', async () => {
    await fetchData('/admin/unidades/' + unit.id_vehiculo + '/invitados/cerrar', { method: 'POST' });
    $('#account-message').textContent = 'El servidor procesó el cierre de la reserva de Invitado.';
  }), button('Volver a Unidades', showUnits));
}

let catalogVersion = 0;
async function showPublicCatalog(offset = 0) {
  const version = ++catalogVersion;
  const host = $('#public-catalog');
  host.hidden = false;
  host.replaceChildren(node('p', 'Consultando catálogo…'));
  const data = await fetchData('/catalogo?limite=20&offset=' + offset);
  if (version !== catalogVersion) return;
  host.replaceChildren(node('h3', 'Prueba nuestros vehículos IoT'));
  host.append(node('p', 'Consulta las unidades configuradas para una prueba temporal y exclusiva.'));
  table(host, [['nombre', 'Modelo'], ['descripcion', 'Descripción'], ['unidades_exhibicion', 'Unidades de exhibición']], data.modelos,
    (model, cell) => cell.append(button('Ver pruebas disponibles', () => showGuestUnits(model))));
  const navigation = node('div', undefined, 'account-actions');
  if (offset > 0) navigation.append(button('Página anterior', () => showPublicCatalog(Math.max(0, offset - 20))));
  if (data.modelos.length === 20) navigation.append(button('Página siguiente', () => showPublicCatalog(offset + 20)));
  navigation.append(button('Cerrar catálogo', () => { catalogVersion++; host.hidden = true; }));
  host.append(navigation);
}

async function showGuestUnits(model) {
  const version = ++catalogVersion;
  const host = $('#public-catalog');
  host.hidden = false;
  host.replaceChildren(node('p', 'Consultando unidades…'));
  const data = await fetchData('/catalogo/' + model.id_modelo + '/unidades');
  if (version !== catalogVersion) return;
  host.replaceChildren(node('h3', model.nombre));
  const units = data.unidades.map(unit => ({ ...unit,
    estado_prueba: unit.ocupada ? 'Ocupada · actualiza para comprobar' : unit.disponible ? 'Disponible para reservar' : 'No disponible' }));
  table(host, [['nombre', 'Unidad'], ['duracion_s', 'Duración (s)'], ['pulso_ms', 'Pulso (ms)'], ['estado_prueba', 'Estado']], units,
    (unit, cell) => {
      const reserve = button('Reservar prueba', async () => {
        reserve.disabled = true;
        try { await reserveGuestTrial(unit); }
        finally { if (reserve.isConnected) reserve.disabled = !unit.disponible; }
      });
      reserve.disabled = !unit.disponible;
      cell.append(reserve);
    });
  host.append(button('Actualizar disponibilidad', () => showGuestUnits(model)), button('Volver al catálogo', () => showPublicCatalog()));
}

function showIdentity() {
  screenVersion++;
  workspace.replaceChildren();
  const user = currentUser();
  $('#account-login').hidden = Boolean(user);
  $('#account-content').hidden = !user;
  $('#account-logout').hidden = !user;
  $('#account-user').textContent = user ? user.nombre + ' · ' + user.rol : 'Inicia sesión para administrar tus vehículos.';
  $('#account-title').textContent = user?.rol === 'ADMINISTRADOR' ? 'Administración' : 'Mi cuenta';
  const menu = $('#account-menu');
  menu.replaceChildren();
  if (!user) return;
  const choices = user.rol === 'ADMINISTRADOR'
    ? [['Resumen', showSummary], ['Modelos', showModels], ['Unidades', showUnits], ['Compradores', showClients], ['Auditoría', showAudit]]
    : [['Mis vehículos', showMyVehicles]];
  for (const [label, action] of choices) menu.append(button(label, action));
  run(choices[0][1]);
}

if (config.sessionAuth) {
  $('#account-catalog').hidden = false;
  $('#account-catalog').addEventListener('click', () => run(() => showPublicCatalog()));
  $('#control-account').hidden = false;
  $('#control-account').addEventListener('click', () => $('#tab-admin').click());
  $('#tab-admin').hidden = false;
  $('#account-login').addEventListener('submit', event => {
    event.preventDefault();
    run(async () => {
      const submit = event.currentTarget.querySelector('button');
      submit.disabled = true;
      const values = Object.fromEntries(new FormData($('#account-login')));
      try {
        const data = await fetchData('/auth/login', { method: 'POST', body: values });
        $('#account-login').reset();
        setAccountSession(data);
        showIdentity();
      } finally { submit.disabled = false; }
    });
  });
  $('#account-logout').addEventListener('click', () => run(async () => {
    try { await fetchData('/auth/logout', { method: 'POST' }); }
    finally { setAccountSession(null); showIdentity(); }
  }));
  showIdentity();
  if (!location.hash || location.hash === '#control') $('#tab-admin').click();
}
