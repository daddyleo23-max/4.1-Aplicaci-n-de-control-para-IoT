let selectedVehicleId = 1;
let vehicleSelected = false;
let supportScope = null;
export function selectedSupportScope() { return supportScope; }
export function hasSelectedVehicle() { return vehicleSelected; }
export function clearVehicleSelection() { vehicleSelected = false; supportScope = null; }
export function selectVehicle(id, { support = null } = {}) {
  if (!Number.isInteger(Number(id)) || Number(id) <= 0) throw new Error('Vehículo inválido.');
  selectedVehicleId = Number(id);
  vehicleSelected = true;
  supportScope = support;
  document.dispatchEvent(new CustomEvent('iot:select-vehicle'));
}

export const config = Object.freeze({
  sessionAuth: false,
  apiBaseUrl: 'https://34.194.45.28',
  get vehicleId() { return selectedVehicleId; },
  apiHealthPath: '/',
  databaseHealthPath: '/health/db',
  get websocketUrl() { return this.apiBaseUrl.replace(/^http/, 'ws') + '/ws/vehiculos/' + selectedVehicleId; },
  healthIntervalMs: 60_000,
  requestTimeoutMs: 8_000,
  // No se coloca una API key aquí: este archivo se publica en GitHub Pages.
});
