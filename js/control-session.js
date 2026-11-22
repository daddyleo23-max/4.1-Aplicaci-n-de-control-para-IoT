import { config } from './config.js';
import { currentUser, currentToken } from './account-session.js';
let granted = null;
export function setControlGrant(value) { granted = value; }
export function requireControlGrant() {
  if (config.sessionAuth && currentUser()?.rol === 'USUARIO' &&
      (!granted || granted.token !== currentToken() || granted.unit !== config.vehicleId)) {
    throw new Error('Pulsa «Adquirir control» y espera la autorización del canal antes de operar.');
  }
}
