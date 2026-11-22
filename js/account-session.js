let token = '';
let user = null;

export function sessionHeaders() {
  return token ? { Authorization: 'Bearer ' + token } : {};
}

export function currentUser() { return user; }
export function currentToken() { return token; }

export function setAccountSession(value) {
  token = value?.access_token || '';
  user = value?.usuario || null;
  document.dispatchEvent(new CustomEvent('iot:account-session', { detail: { user } }));
}
