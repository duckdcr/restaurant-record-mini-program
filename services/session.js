const SESSION_KEY = 'a2_session';
let memorySession = null;

function storageApi() {
  return typeof wx !== 'undefined' ? wx : null;
}

function getSession() {
  const api = storageApi();
  if (api && typeof api.getStorageSync === 'function') {
    return api.getStorageSync(SESSION_KEY) || null;
  }
  return memorySession;
}

function setSession(session) {
  memorySession = session || null;
  const api = storageApi();
  if (api && typeof api.setStorageSync === 'function') {
    api.setStorageSync(SESSION_KEY, memorySession);
  }
}

function clearSession() {
  memorySession = null;
  const api = storageApi();
  if (api && typeof api.removeStorageSync === 'function') {
    api.removeStorageSync(SESSION_KEY);
  }
}

function getToken() {
  const current = getSession();
  return current && current.access_token ? current.access_token : '';
}

module.exports = { getSession, setSession, clearSession, getToken };
