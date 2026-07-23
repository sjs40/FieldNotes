/* Keeps the existing UI's local view responsive while the API owns durability. */
(function () {
  const KEY = 'fieldnotes-v1';
  const nativeSet = Storage.prototype.setItem;

  async function sync(notes) {
    const response = await fetch('/api/notes/sync', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ notes })
    });
    if (!response.ok) throw new Error('Note sync failed');
    return response.json();
  }

  Storage.prototype.setItem = function (key, value) {
    nativeSet.call(this, key, value);
    if (key !== KEY || !location.protocol.startsWith('http')) return;
    try { sync(JSON.parse(value)).catch(error => console.warn('Fieldnotes API sync unavailable', error)); }
    catch (_) { /* only the application data key is expected to be JSON */ }
  };

  async function hydrate() {
    if (!location.protocol.startsWith('http') || sessionStorage.getItem('fieldnotes-hydrated')) return;
    try {
      const response = await fetch('/api/notes');
      if (!response.ok) return;
      const remote = await response.json();
      const local = JSON.parse(localStorage.getItem(KEY) || '[]');
      if (remote.length) {
        if (JSON.stringify(remote) !== JSON.stringify(local)) {
          nativeSet.call(localStorage, KEY, JSON.stringify(remote));
          sessionStorage.setItem('fieldnotes-hydrated', 'true');
          location.reload();
        }
      } else if (local.length) {
        await sync(local);
      }
    } catch (error) {
      console.warn('Fieldnotes is running without API persistence', error);
    }
  }
  hydrate();
})();
