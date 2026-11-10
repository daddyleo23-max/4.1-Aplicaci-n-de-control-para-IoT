import { config } from './config.js';
import { api } from './api-client.js';
import { setStatus } from './ui.js';

export async function refreshConnectionStatus() {
  setStatus('status-api', 'checking', 'Comprobando', 'Servicio de salud');
  setStatus('status-db', 'checking', 'Comprobando', 'Diagnóstico de base de datos');

  const apiCheck = api.root()
    .then(() => setStatus('status-api', 'available', 'Disponible', 'API respondió al servicio raíz'))
    .catch((error) => setStatus('status-api', 'unavailable', 'No disponible', error.message));
  const dbCheck = api.databaseHealth()
    .then((result) => {
      if (result?.conectado === true) setStatus('status-db', 'available', 'Disponible', `${result.base_datos || 'RDS'} · ${result.version_mysql || 'conectado'}`);
      else setStatus('status-db', 'unavailable', 'No disponible', 'El backend reporta desconexión de MySQL');
    })
    .catch((error) => setStatus('status-db', 'unknown', 'Sin verificar', error.message));
  await Promise.allSettled([apiCheck, dbCheck]);
}

export function startHealthPolling() { refreshConnectionStatus(); return setInterval(refreshConnectionStatus, config.healthIntervalMs); }
