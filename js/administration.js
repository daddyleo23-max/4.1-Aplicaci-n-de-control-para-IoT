import { config, selectVehicle } from './config.js';
import { request } from './api-client.js';
import { currentUser, currentToken, setAccountSession } from './account-session.js';
import { reserveGuestTrial, closeGuestTrial, guestTrialActive } from './guest-control.js';

const $ = (selector) => document.querySelector(selector);
const workspace = $('#account-workspace');
let screenVersion = 0;
let currentSection = '';

function markSection(title) {
  currentSection = title;
  if ($('#public-catalog').hidden) $('#account-location').textContent = title;
  let parent = title;
  if (title.startsWith('Capacidades')) parent = 'Modelos';
  else if (title.startsWith('Comandos') || title.startsWith('Prueba de Invitado')) parent = 'Unidades';
  else if (title.startsWith('Demos') || title.includes('secuencia') || title.includes('demo')) parent = currentUser()?.rol === 'ADMINISTRADOR' ? 'Demos de empresa' : 'Mis vehículos';
  else if (title.startsWith('Autorizar soporte')) parent = 'Mis vehículos';
  for (const item of $('#account-menu').children) {
    if (item.textContent === parent) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  }
  if ($('#account-section-select')) $('#account-section-select').value = parent;
}


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

// Follow the API's pagination for both tables and complete model/customer selectors.
async function fetchCollection(path, key) {
  const token = currentToken();
  const rows = [];
  for (let offset = 0; ; offset += 100) {
    if (token !== currentToken()) throw new Error('La sesión cambió; vuelve a abrir la lista.');
    const data = await fetchData(path + '?limite=100&offset=' + offset);
    if (token !== currentToken()) throw new Error('La sesión cambió; vuelve a abrir la lista.');
    rows.push(...data[key]);
    if (data[key].length < 100) return { [key]: rows };
  }
}

function panel(title) {
  const result = node('section', undefined, 'panel account-panel');
  markSection(title);
  result.append(node('p', currentUser()?.rol === 'ADMINISTRADOR' ? 'ADMINISTRACIÓN / ' + title : 'MI CUENTA / ' + title, 'account-eyebrow'));
  result.append(node('h3', title));
  workspace.querySelector('.account-loading')?.remove();
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
  result.append(body);
  const searchLabel = node('label', 'Buscar en esta lista', 'account-search');
  const search = node('input');
  search.type = 'search';
  searchLabel.append(search);
  const navigation = node('div', undefined, 'account-pagination');
  const count = node('span');
  count.setAttribute('role', 'status');
  let page = 0;
  const previous = button('Anterior', () => { page--; renderRows(); });
  const next = button('Siguiente', () => { page++; renderRows(); });
  function renderRows() {
    const term = search.value.trim().toLocaleLowerCase('es');
    const filtered = records.filter(record => columns.some(([key]) => String(record[key] ?? '').toLocaleLowerCase('es').includes(term)));
    page = Math.max(0, Math.min(page, Math.ceil(filtered.length / 20) - 1));
    body.replaceChildren();
    for (const record of filtered.slice(page * 20, (page + 1) * 20)) {
      const row = node('tr');
      for (const [key, label] of columns) {
        const cell = node('td', record[key] ?? '—');
        cell.dataset.label = label;
        row.append(cell);
      }
      if (actions) {
        const cell = node('td', undefined, 'account-row-actions');
        cell.dataset.label = 'Acciones';
        const group = node('div', undefined, 'account-actions');
        actions(record, group);
        cell.append(group);
        row.append(cell);
      }
      body.append(row);
    }
    previous.disabled = page === 0;
    next.disabled = (page + 1) * 20 >= filtered.length;
    previous.hidden = next.hidden = filtered.length <= 20;
    count.textContent = filtered.length ? `${page * 20 + 1}–${Math.min((page + 1) * 20, filtered.length)} de ${filtered.length}` : 'Sin registros disponibles.';
  }
  search.addEventListener('input', () => { page = 0; renderRows(); });
  navigation.append(previous, count, next);
  wrap.append(result);
  container.append(searchLabel, wrap, navigation);
  renderRows();
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
    if (field.min !== undefined) input.min = field.min;
    if (field.max !== undefined) input.max = field.max;
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
  workspace.replaceChildren(node('p', 'Cargando sección…', 'account-loading'));
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
    unidades_prueba_libres: 'Disponibles para prueba', demos_empresa_activas: 'Demos de empresa activas',
  };
  for (const [key, label] of Object.entries(labels)) {
    const card = node('div');
    card.append(node('strong', data[key] ?? 'Sin datos'), node('span', label));
    metrics.append(card);
  }
  section.append(metrics);
  section.append(node('p', data.pruebas_habilitadas ? 'Pruebas habilitadas; disponibilidad consultada al cargar. Cada reserva se valida de nuevo.' : 'Pruebas temporales no disponibles mientras se recupera el servicio.'));
  const actions = node('div', undefined, 'account-actions');
  for (const [label, action] of [['Modelos', showModels], ['Unidades', showUnits], ['Compradores', showClients], ['Demos de empresa', showCompanyDemos]]) actions.append(button(label, action));
  section.append(actions);
  const units = await fetchCollection('/admin/unidades', 'unidades');
  if (version !== screenVersion) return;
  section.append(node('h4', 'Inventario resumido'));
  table(section, [['identificador_unidad', 'Identificador'], ['nombre', 'Unidad'], ['nombre_modelo', 'Modelo'], ['estado_comercial', 'Estado']], units.unidades);

}

async function showModels() {
  const version = beginScreen();
  const data = await fetchCollection('/admin/modelos', 'modelos');
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
      cell.append(button('Editar', () => edit(record)), button('Capacidades', () => showCapabilities(record)));
      if (record.activo || record.publico) cell.append(button(record.publico ? 'Retirar del catálogo' : 'Publicar en catálogo', async () => {
        await fetchData('/admin/modelos/' + record.id_modelo + '/publicacion',
          { method: 'POST', body: { publico: !record.publico } });
        await showModels();
      }));
    });
}

async function showCapabilities(model) {
  const version = beginScreen();
  const data = await fetchData(`/admin/modelos/${model.id_modelo}/capacidades`);
  if (version !== screenVersion) return;
  const section = panel('Capacidades · ' + model.nombre);
  section.append(node('p', 'Configura únicamente funciones comprobadas en el hardware. Registrar una capacidad no añade esa función al firmware. Los nombres y códigos usados se conservan.'));
  const editor = node('div');
  const edit = (record = {}) => {
    editor.replaceChildren();
    form(editor, [
      { name: 'nombre', label: 'Nombre de función (MAYÚSCULAS)', value: record.nombre, maxLength: 60 },
      { name: 'codigo', label: 'Código del comando', type: 'number', value: record.codigo, min: 1, max: 65535 },
      { name: 'descripcion', label: 'Descripción', value: record.descripcion, required: false, maxLength: 255 },
      { name: 'activo', label: 'Estado de la capacidad', value: record.activo === 0 ? '0' : '1', options: [['1', 'Habilitada'], ['0', 'Deshabilitada']] },
    ], record.id_capacidad ? 'Guardar capacidad' : 'Crear capacidad', async values => {
      values.codigo = Number(values.codigo);
      values.activo = values.activo === '1';
      await fetchData(`/admin/modelos/${model.id_modelo}/capacidades` + (record.id_capacidad ? `/${record.id_capacidad}/actualizar` : ''),
        { method: 'POST', body: values });
      await showCapabilities(model);
    });
    editor.append(button('Cancelar edición', () => editor.replaceChildren()));
  };
  if (model.activo) section.append(button('Nueva capacidad', () => edit()));
  else section.append(node('p', 'Modelo inactivo. Reactívalo desde Modelos para editar sus capacidades.'));
  section.append(editor);
  table(section, [['nombre', 'Función'], ['codigo', 'Código'], ['descripcion', 'Descripción'], ['activo', 'Habilitada']], data.capacidades,
    (record, cell) => { if (model.activo) cell.append(button('Editar capacidad', () => edit(record))); });
  section.append(button('Volver a modelos', showModels));
}

async function showUnitCommands(unit) {
  const version = beginScreen();
  const data = await fetchData(`/admin/unidades/${unit.id_vehiculo}/comandos`);
  if (version !== screenVersion) return;
  const section = panel('Comandos · ' + unit.nombre);
  section.append(node('p', 'Cada comando usa una capacidad del modelo. La edición conserva su ID, nombre y código. DETENER debe permanecer habilitado mientras la unidad esté activa. Finaliza las reservas antes de editar.'));
  const editor = node('div');
  const edit = (record = {}) => {
    editor.replaceChildren();
    const existing = !!record.id_comando;
    if (existing) editor.append(node('p', record.nombre + ' · código ' + record.codigo));
    form(editor, [
      ...(!existing ? [{ name: 'id_capacidad', label: 'Capacidad del modelo', options: data.capacidades.filter(c => c.activo).map(c => [c.id_capacidad, c.nombre + ' · ' + c.codigo]) }] : []),
      { name: 'descripcion', label: 'Descripción del comando', value: record.descripcion, required: false, maxLength: 255 },
      { name: 'activo', label: 'Estado del comando', value: record.activo === 0 ? '0' : '1', options: [['1', 'Habilitado'], ['0', 'Deshabilitado']] },
    ], existing ? 'Guardar comando' : 'Agregar comando', async values => {
      values.id_capacidad = existing ? record.id_capacidad : Number(values.id_capacidad);
      values.activo = values.activo === '1';
      await fetchData(`/admin/unidades/${unit.id_vehiculo}/comandos` + (existing ? `/${record.id_comando}/actualizar` : ''),
        { method: 'POST', body: values });
      await showUnitCommands(unit);
    });
    editor.append(button('Cancelar edición', () => editor.replaceChildren()));
  };
  if (data.capacidades.some(c => c.activo)) section.append(button('Nuevo comando', () => edit()));
  else section.append(node('p', 'Configura primero las capacidades del modelo en Administración → Modelos.'));
  section.append(editor);
  table(section, [['id_comando', 'ID'], ['nombre', 'Función'], ['codigo', 'Código'], ['descripcion', 'Descripción'], ['activo', 'Habilitado'], ['compatible', 'Compatible']], data.comandos,
    (record, cell) => { if (record.id_capacidad) cell.append(button('Editar comando', () => edit(record))); });
  section.append(button('Volver a unidades', showUnits));
}

async function showClients() {
  const version = beginScreen();
  const data = await fetchCollection('/admin/clientes', 'clientes');
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
    fetchCollection('/admin/unidades', 'unidades'), fetchCollection('/admin/modelos', 'modelos'),
    fetchCollection('/admin/clientes', 'clientes'),
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
  table(section, [['id_vehiculo', 'ID'], ['nombre', 'Unidad'], ['identificador_unidad', 'Identificador'],
    ['nombre_modelo', 'Modelo'], ['estado_comercial', 'Estado'], ['propietario', 'Propietario']],
  units.unidades, (unit, cell) => {
    cell.append(button('Editar', () => editUnit(unit)), button('Comandos', () => showUnitCommands(unit)));
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

}

async function showAudit() {
  const version = beginScreen();
  const data = await fetchCollection('/admin/auditoria', 'eventos');
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
    button('Demos', () => showDemos(unit.id_vehiculo)),
    button('Autorizar soporte', () => showSupport(unit))));
}

function supportDate(value) {
  if (!value) return '—';
  const date = new Date(/[zZ]$|[+-]\d{2}:\d{2}$/.test(value) ? value : value + 'Z');
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : date.toLocaleString('es-MX', { timeZone: 'America/Mexico_City' }) + ' · CDMX';
}

async function showSupport(unit) {
  const version = beginScreen();
  const [targets, data] = await Promise.all([
    fetchData('/soporte/administradores'), fetchData(`/vehiculos/${unit.id_vehiculo}/soporte`),
  ]);
  if (version !== screenVersion) return;
  const section = panel('Autorizar soporte · ' + unit.nombre);
  section.append(node('p', 'Elige al administrador y el alcance. Soporte operativo permite movimientos manuales mediante reserva exclusiva; no permite demos privadas. Puedes revocar el permiso en cualquier momento.'));
  if (targets.administradores.length) {
    form(section, [
      { name: 'id_administrador', label: 'Administrador autorizado', options: targets.administradores.map(a => [a.id_administrador, a.nombre]) },
      { name: 'operativo', label: 'Alcance del permiso', value: '0', options: [['0', 'Sólo monitoreo'], ['1', 'Soporte operativo: movimientos manuales']] },
      { name: 'minutos', label: 'Duración del permiso (minutos)', type: 'number', value: 5, min: 1, max: 30 },
    ], 'Conceder permiso', async values => {
      await fetchData(`/vehiculos/${unit.id_vehiculo}/soporte`, { method: 'POST', body: {
        id_administrador: Number(values.id_administrador), minutos: Number(values.minutos), operativo: values.operativo === '1',
      } });
      await showSupport(unit);
    });
  } else section.append(node('p', 'No hay administradores activos disponibles.'));
  const rows = data.permisos.map(p => ({ ...p, alcance: p.operativo ? 'OPERATIVO' : 'MONITOREO',
    vencimiento: supportDate(p.expira_utc), estado: p.vigente ? 'Vigente' : 'Finalizado' }));
  table(section, [['administrador', 'Administrador'], ['alcance', 'Alcance'], ['vencimiento', 'Vencimiento'], ['estado', 'Estado']], rows,
    (permission, cell) => {
      if (permission.vigente) cell.append(button('Revocar permiso', async () => {
        await fetchData(`/vehiculos/${unit.id_vehiculo}/soporte/${permission.id_permiso}/revocar`, { method: 'POST' });
        await showSupport(unit);
      }));
    });
  section.append(button('Actualizar permisos', () => showSupport(unit)), button('Volver a mis vehículos', showMyVehicles));
}

async function showAuthorizedSupport() {
  const version = beginScreen();
  const data = await fetchData('/admin/soporte');
  if (version !== screenVersion) return;
  const section = panel('Soporte autorizado');
  section.append(node('p', 'Sólo aparecen permisos vigentes concedidos a tu cuenta. El control operativo requiere adquirir la reserva; el comprador puede revocarlo.'));
  const rows = data.permisos.map(p => ({ ...p, alcance: p.operativo ? 'OPERATIVO' : 'MONITOREO', vencimiento: supportDate(p.expira_utc) }));
  table(section, [['identificador_unidad', 'Identificador'], ['nombre', 'Unidad'], ['alcance', 'Alcance'], ['vencimiento', 'Vencimiento']], rows,
    (permission, cell) => {
      const open = monitor => {
        selectVehicle(permission.id_vehiculo, { support: permission.operativo ? 'OPERATIVO' : 'MONITOREO' });
        $(monitor ? '#tab-monitor' : '#tab-control').click();
      };
      cell.append(button('Monitorear', () => open(true)));
      if (permission.operativo) cell.append(button('Control de soporte', () => open(false)));
    });
  section.append(button('Actualizar permisos', showAuthorizedSupport));
}

async function showCompanyDemos() {
  const version = beginScreen();
  const data = await fetchCollection('/admin/unidades', 'unidades');
  if (version !== screenVersion) return;
  const section = panel('Demos de empresa');
  section.append(node('p', 'Prepara las secuencias de fábrica en unidades activas sin comprador. Al asignarlas, el comprador podrá consultarlas y ejecutarlas; sus demos privadas se mantienen separadas.'));
  table(section, [['identificador_unidad', 'Identificador'], ['nombre', 'Unidad'], ['nombre_modelo', 'Modelo']],
    data.unidades.filter(unit => unit.activo && !unit.id_propietario),
    (unit, cell) => cell.append(button('Administrar demos de empresa', () => showDemos(unit.id_vehiculo))));
  section.append(button('Actualizar unidades', showCompanyDemos));
}

async function showDemos(vehicleId = config.vehicleId) {
  const version = beginScreen();
  const [data, catalog] = await Promise.all([
    fetchData('/mis-demos?id_vehiculo=' + vehicleId), fetchData('/vehiculos/' + vehicleId + '/comandos'),
  ]);
  if (version !== screenVersion) return;
  const company = currentUser()?.rol === 'ADMINISTRADOR';
  const section = panel(company ? 'Demos de empresa' : 'Demos privadas y de empresa');
  section.append(node('p', company ? 'Las secuencias guardadas aquí pertenecen a la empresa. Usa sólo comandos y duraciones comprobados para esta unidad.' : 'Puedes crear y editar tus demos privadas. Las secuencias de empresa son de sólo lectura.'));
  if (catalog.comandos.some(c => c.activo && !['DEMO', 'AUTO_DEMO', 'AUTO DEMO'].includes(c.nombre.toUpperCase()))) {
    section.append(button(company ? 'Nueva demo de empresa' : 'Nueva demo privada', () => demoEditor(vehicleId, catalog.comandos)));
  } else section.append(node('p', 'No hay comandos compatibles habilitados para crear una demo. Configura primero el catálogo de la unidad.'));
  table(section, [['nombre', 'Nombre'], ['tipo', 'Tipo'], ['revision', 'Revisión'], ['activo', 'Activa']],
    data.demos, (demo, cell) => {
      const editable = demo.tipo === 'PRIVADA' || currentUser()?.rol === 'ADMINISTRADOR';
      if (editable) cell.append(button('Editar pasos', async () => {
        const detail = await fetchData('/mis-demos/' + demo.id_demo);
        demoEditor(vehicleId, catalog.comandos, detail);
      }));
      if (demo.activo) cell.append(button('Seleccionar en control', async () => {
        selectVehicle(vehicleId);
        $('#tab-control').click();
        document.dispatchEvent(new CustomEvent('iot:choose-demo', { detail: { id: demo.id_demo } }));
      }));
    });
}

function demoEditor(vehicleId, commands, detail) {
  beginScreen();
  const section = panel(detail ? 'Editar secuencia' : currentUser()?.rol === 'ADMINISTRADOR' ? 'Nueva demo de empresa' : 'Nueva demo privada');
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
  syncAccountLayout();
  host.replaceChildren(node('p', 'Consultando catálogo…'));
  const data = await fetchData('/catalogo?limite=20&offset=' + offset);
  if (version !== catalogVersion) return;
  host.replaceChildren(node('h3', 'Prueba nuestros vehículos IoT'));
  host.append(node('p', 'Consulta las unidades configuradas para una prueba temporal y exclusiva.'));
  const grid = node('div', undefined, 'catalog-grid');
  for (const model of data.modelos) {
    const card = node('article', undefined, 'catalog-model');
    const image = node('img');
    image.src = './assets/modelo-iot.svg';
    image.alt = 'Ilustración genérica de vehículo IoT.';
    image.width = 160; image.height = 96; image.loading = 'lazy';
    card.append(image, node('h4', model.nombre), node('p', model.descripcion),
      node('p', 'Funciones: ' + (model.capacidades.map(c => c.nombre.replaceAll('_', ' ')).join(', ') || 'Sin capacidades publicadas.')),
      node('p', model.unidades_exhibicion + ' unidades de exhibición'),
      button('Ver pruebas disponibles', () => showGuestUnits(model)));
    grid.append(card);
  }
  if (!data.modelos.length) grid.append(node('p', 'No hay modelos publicados por el momento.'));
  host.append(grid);
  const navigation = node('div', undefined, 'account-actions');
  if (offset > 0) navigation.append(button('Página anterior', () => showPublicCatalog(Math.max(0, offset - 20))));
  if (data.modelos.length === 20) navigation.append(button('Página siguiente', () => showPublicCatalog(offset + 20)));
  navigation.append(button('Cerrar catálogo', closeCatalog));
  host.append(navigation);
}

async function showGuestUnits(model) {
  const version = ++catalogVersion;
  const host = $('#public-catalog');
  host.hidden = false;
  syncAccountLayout();
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
        try { await reserveGuestTrial(unit); closeCatalog(); }
        finally { if (reserve.isConnected) reserve.disabled = !unit.disponible; }
      });
      reserve.disabled = !unit.disponible;
      cell.append(reserve);
    });
  const actions = node('div', undefined, 'account-actions');
  actions.append(button('Actualizar disponibilidad', () => showGuestUnits(model)), button('Volver al catálogo', () => showPublicCatalog()), button('Cerrar catálogo', closeCatalog));
  host.append(actions);
}

function syncAccountLayout() {
  const browsing = !$('#public-catalog').hidden;
  const trialVisible = !$('#guest-trial').hidden;
  const user = currentUser();
  $('#account-login').hidden = Boolean(user) || browsing || trialVisible;
  $('#account-content').hidden = !user || browsing || trialVisible;
  $('#account-signin').hidden = Boolean(user) || (!browsing && !trialVisible);
  $('#account-catalog').textContent = browsing ? 'Cerrar catálogo público' : 'Explorar catálogo público';
  $('#account-catalog').setAttribute('aria-expanded', String(browsing));
  $('#account-location').textContent = trialVisible ? 'Prueba de Invitado' : browsing ? 'Catálogo público' : user ? currentSection : 'Acceso a mi cuenta';
}

function closeCatalog() {
  catalogVersion++;
  $('#public-catalog').hidden = true;
  $('#public-catalog').replaceChildren();
  syncAccountLayout();
}

document.addEventListener('iot:guest-view', syncAccountLayout);

function showIdentity() {
  screenVersion++;
  workspace.replaceChildren();
  const user = currentUser();
  $('#account-login').hidden = Boolean(user);
  $('#account-content').hidden = !user;
  $('#account-logout').hidden = !user;
  $('#account-user').textContent = user ? user.nombre + ' · ' + user.rol : 'Inicia sesión para administrar tus vehículos.';
  $('#account-title').textContent = user?.rol === 'ADMINISTRADOR' ? 'Administración' : 'Mi cuenta';
  $('#tab-admin').textContent = user?.rol === 'ADMINISTRADOR' ? 'ADMINISTRACIÓN' : 'MI CUENTA';
  const menu = $('#account-menu');
  menu.replaceChildren();
  $('#account-section-picker')?.remove();
  closeCatalog();
  if (!user) return;
  const choices = user.rol === 'ADMINISTRADOR'
    ? [['Resumen', showSummary], ['Modelos', showModels], ['Unidades', showUnits], ['Compradores', showClients], ['Auditoría', showAudit], ['Demos de empresa', showCompanyDemos], ['Soporte autorizado', showAuthorizedSupport]]
    : [['Mis vehículos', showMyVehicles]];
  for (const [label, action] of choices) {
    const item = button(label, async () => { markSection(label); await action(); });
    menu.append(item);
  }
  const picker = node('label', 'Sección de la cuenta', 'account-section-picker');
  picker.id = 'account-section-picker';
  const select = node('select');
  select.id = 'account-section-select';
  for (const [label] of choices) {
    const option = node('option', label); option.value = label; select.append(option);
  }
  select.addEventListener('change', () => run(async () => {
    const [label, action] = choices.find(([label]) => label === select.value);
    markSection(label); await action();
  }));
  picker.append(select);
  menu.before(picker);
  markSection(choices[0][0]);
  run(choices[0][1]);
}

if (config.sessionAuth) {
  $('#account-catalog').hidden = false;
  $('#account-catalog').addEventListener('click', () => run(() => $('#public-catalog').hidden ? showPublicCatalog() : closeCatalog()));
  $('#account-signin').addEventListener('click', () => run(async () => {
    await closeGuestTrial();
    if (guestTrialActive()) return;
    $('#guest-trial').hidden = true;
    closeCatalog();
    $('#account-login').querySelector('input').focus();
  }));
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
