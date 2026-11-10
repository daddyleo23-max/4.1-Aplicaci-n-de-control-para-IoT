export const config = Object.freeze({
  apiBaseUrl: 'https://34.194.45.28',
  vehicleId: 1,
  apiHealthPath: '/',
  databaseHealthPath: '/health/db',
  websocketUrl: 'wss://34.194.45.28/ws/vehiculos/1',
  healthIntervalMs: 60_000,
  requestTimeoutMs: 8_000,
  // No se coloca una API key aquí: este archivo se publica en GitHub Pages.
});
