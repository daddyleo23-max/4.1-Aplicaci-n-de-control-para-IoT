let localApiKey = '';
let sessionApiKey = '';
const localHosts = new Set(['localhost', '127.0.0.1', '::1']);

export async function initializeLocalAuth() {
  if (!localHosts.has(window.location.hostname)) return;
  try {
    const localConfig = await import('./auth.local.js');
    localApiKey = typeof localConfig.API_KEY === 'string' ? localConfig.API_KEY.trim() : '';
  } catch {
    localApiKey = '';
  }
}

export function getWriteHeaders() {
  if (localHosts.has(window.location.hostname)) {
    if (!localApiKey) {
      throw new Error('Falta la clave local. Copia js/auth.local.example.js a js/auth.local.js y configúrala solo en tu equipo.');
    }
    return { 'X-API-Key': localApiKey };
  }

  if (window.location.protocol !== 'https:' || !window.isSecureContext) {
    throw new Error('Para enviar órdenes desde el teléfono, abre la página con HTTPS.');
  }
  if (!sessionApiKey) {
    throw new Error('Autoriza los comandos con tu API key. La clave no se guarda en el sitio.');
  }
  return { 'X-API-Key': sessionApiKey };
}

export function setSessionApiKey(value) {
  const key = typeof value === 'string' ? value.trim() : '';
  if (!key) return false;
  sessionApiKey = key;
  return true;
}

export function clearSessionApiKey() {
  sessionApiKey = '';
}

export function isLocalHost() {
  return localHosts.has(window.location.hostname);
}
