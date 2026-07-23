(function () {
  const KEY = 'fieldnotes.supabase.access-token';
  const nativeFetch = window.fetch.bind(window);
  const state = { enabled: false, config: null };
  const token = () => localStorage.getItem(KEY);
  window.fetch = (input, init = {}) => {
    const url = typeof input === 'string' ? input : input.url;
    if (url.includes('/api/') && !url.includes('/api/auth/config') && token()) {
      const headers = new Headers(init.headers || {}); headers.set('Authorization', `Bearer ${token()}`); init = { ...init, headers };
    }
    return nativeFetch(input, init);
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
    localStorage.setItem(KEY, data.access_token); location.reload();
  }
  window.fieldnotesAuth = { token, showLogin, ready: nativeFetch('/api/auth/config').then(r => r.json()).then(config => { state.config = config; state.enabled = config.enabled; return state; }).catch(() => state) };
})();
