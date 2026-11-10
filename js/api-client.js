import { config } from './config.js';
import { getWriteHeaders } from './auth-session.js';

export class ApiError extends Error {
  constructor(message, status = 0, details = '') { super(message); this.name = 'ApiError'; this.status = status; this.details = details; }
}

async function request(path, { method = 'GET', body, headers = {}, timeout = config.requestTimeoutMs } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(new URL(path, config.apiBaseUrl), {
      method,
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}), ...headers },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const raw = await response.text();
    let data = null;
    if (raw) { try { data = JSON.parse(raw); } catch { throw new ApiError('La API devolvió una respuesta no válida.', response.status); } }
    if (!response.ok) {
      const reason = typeof data?.detail === 'string' ? data.detail : `La solicitud respondió HTTP ${response.status}.`;
      throw new ApiError(reason, response.status);
    }
    return { status: response.status, data };
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === 'AbortError') throw new ApiError('La solicitud agotó el tiempo de espera.');
    throw new ApiError('No se pudo conectar con la API. Revisa red, CORS y certificado HTTPS.');
  } finally { clearTimeout(timer); }
}

function writeHeaders() {
  try { return getWriteHeaders(); }
  catch (error) { throw new ApiError(error.message); }
}

export const api = {
  async root() { return (await request(config.apiHealthPath)).data; },
  async databaseHealth() { return (await request(config.databaseHealthPath)).data; },
  async vehicle() { return (await request(`/vehiculos/${config.vehicleId}`)).data; },
  async commands() { return (await request(`/vehiculos/${config.vehicleId}/comandos`)).data; },
  async demos() { return (await request(`/vehiculos/${config.vehicleId}/demos`)).data; },
  async move(idCommand) {
    const headers = writeHeaders();
    return request(`/vehiculos/${config.vehicleId}/movimientos`, { method: 'POST', headers, body: { id_comando: idCommand } });
  },
  async startDemo(idDemo) {
    const headers = writeHeaders();
    return request(`/vehiculos/${config.vehicleId}/demos/${idDemo}/iniciar`, { method: 'POST', headers });
  },
  async cancelDemo() {
    const headers = writeHeaders();
    return request(`/vehiculos/${config.vehicleId}/demos/cancelar`, { method: 'POST', headers });
  },
};
