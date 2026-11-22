let selectedVehicleId = 1;
let vehicleSelected = false;
export function hasSelectedVehicle() { return vehicleSelected; }
export function clearVehicleSelection() { vehicleSelected = false; }
export function selectVehicle(id) {
  if (!Number.isInteger(Number(id)) || Number(id) <= 0) throw new Error('Vehículo inválido.');
  selectedVehicleId = Number(id);
  vehicleSelected = true;
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
