(function () {
  const KEY = 'fieldnotes.supabase.access-token';
  const REFRESH_KEY = 'fieldnotes.supabase.refresh-token';
  const nativeFetch = window.fetch.bind(window);
  const state = { enabled: false, config: null };
  const token = () => localStorage.getItem(KEY);
  const refreshToken = () => localStorage.getItem(REFRESH_KEY);
  const tokenExpiresSoon = value => {
    try {
      const payload = JSON.parse(atob(value.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
      return !payload.exp || payload.exp * 1000 < Date.now() + 60_000;
    } catch (_) { return true; }
  };
  function saveSession(data) {
    if (data.access_token) localStorage.setItem(KEY, data.access_token);
    if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
  }
  async function refreshSession() {
    if (!state.config || !refreshToken()) return false;
    try {
      const response = await nativeFetch(`${state.config.url}/auth/v1/token?grant_type=refresh_token`, {
        method: 'POST',
        headers: { apikey: state.config.publishable_key, 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken() })
      });
      const data = await response.json();
      if (!response.ok || !data.access_token) return false;
      saveSession(data);
      return true;
    } catch (_) { return false; }
  }
  async function ensureSession() {
    if (!state.enabled || !token() || !tokenExpiresSoon(token())) return Boolean(token());
    return refreshSession();
  }
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input.url;
    const isApiRequest = url.includes('/api/') && !url.includes('/api/auth/config');
    if (isApiRequest) await ensureSession();
    if (isApiRequest && token()) {
      const headers = new Headers(init.headers || {}); headers.set('Authorization', `Bearer ${token()}`); init = { ...init, headers };
    }
    let response = await nativeFetch(input, init);
    if (isApiRequest && response.status === 401 && await refreshSession()) {
      const headers = new Headers(init.headers || {}); headers.set('Authorization', `Bearer ${token()}`);
      response = await nativeFetch(input, { ...init, headers });
    }
    return response;
  };
  function showLogin(error = '') {
    document.getElementById('app').innerHTML = `<main class="main detail" style="padding-top:12vh"><section class="detail-card" style="max-width:440px;margin:auto"><div class="eyebrow">Fieldnotes</div><h1>Sign in to your journal</h1><p style="color:var(--muted)">Your notes and investment calls are private to your account.</p><input id="auth-email" type="email" placeholder="Email address" style="width:100%;padding:11px;border:1px solid var(--line);border-radius:6px;margin:8px 0"/><input id="auth-password" type="password" placeholder="Password" style="width:100%;padding:11px;border:1px solid var(--line);border-radius:6px;margin:8px 0"/><p id="auth-error" style="color:var(--red);min-height:18px">${error}</p><button class="btn btn-primary" id="auth-submit">Sign in</button><button class="btn btn-quiet" id="auth-signup">Create account</button></section></main>`;
    document.getElementById('auth-submit').onclick = () => signIn(false);
    document.getElementById('auth-signup').onclick = () => signIn(true);
  }
  async function signIn(signUp) {
    const email = document.getElementById('auth-email').value, password = document.getElementById('auth-password').value;
    const endpoint = signUp ? '/auth/v1/signup' : '/auth/v1/token?grant_type=password';
    const response = await nativeFetch(`${state.config.url}${endpoint}`, { method: 'POST', headers: { apikey: state.config.publishable_key, 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
    const data = await response.json();
    if (!response.ok || !data.access_token) return showLogin(data.msg || data.error_description || 'Could not sign in.');
    saveSession(data); location.reload();
  }
  window.fieldnotesAuth = { token, showLogin, ready: nativeFetch('/api/auth/config').then(r => r.json()).then(async config => { state.config = config; state.enabled = config.enabled; await ensureSession(); return state; }).catch(() => state) };
})();
