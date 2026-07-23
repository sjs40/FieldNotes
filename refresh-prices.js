/* UI adapter for the FastAPI market-data endpoint. */
(function () {
  const STORE = 'fieldnotes-v1';
  function notice(message, error) {
    document.querySelector('.price-refresh-toast')?.remove();
    const item = document.createElement('div');
    item.className = 'toast price-refresh-toast';
    item.style.background = error ? '#85463d' : '#26392f';
    item.textContent = message;
    document.body.append(item);
    setTimeout(() => item.remove(), 4200);
  }
  function addButton() {
    const heading = document.querySelector('.topbar');
    if (!heading || document.querySelector('#refresh-prices')) return;
    const target = heading.querySelector('.today') || heading.lastElementChild;
    const button = document.createElement('button');
    button.id = 'refresh-prices'; button.className = 'btn btn-outline'; button.type = 'button';
    button.textContent = 'Update stock prices'; target.replaceWith(button);
  }
  async function refresh(button) {
    const notes = JSON.parse(localStorage.getItem(STORE) || '[]');
    const symbols = [...new Set(notes.flatMap(note => note.tickers || []))];
    button.disabled = true; button.textContent = 'Updating prices…';
    try {
      const response = await fetch('/api/market-data/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbols }) });
      if (!response.ok) throw new Error('The quote provider did not return data.');
      const { quotes, failures } = await response.json();
      notes.forEach(note => {
        const call = note.call;
        if (!call || call.status !== 'open') return;
        if (call.type === 'long_short') { call.long.current = quotes[call.long.symbol]?.price ?? call.long.current; call.short.current = quotes[call.short.symbol]?.price ?? call.short.current; }
        else { call.current = quotes[call.symbol]?.price ?? call.current; call.spyCurrent = quotes.SPY?.price ?? call.spyCurrent; }
        call.lastRefreshedAt = new Date().toISOString();
      });
      localStorage.setItem(STORE, JSON.stringify(notes));
      const failed = Object.keys(failures).length;
      const activePage = document.querySelector('[data-page].active')?.dataset.page;
      if (activePage) sessionStorage.setItem('fieldnotes-active-page', activePage);
      notice(`Updated ${Object.keys(quotes).length} symbols${failed ? `; ${failed} unavailable` : ''}. Reloading…`);
      setTimeout(() => location.reload(), 650);
    } catch (error) {
      console.error(error); notice('Could not update prices. Existing saved prices were not changed.', true);
      button.disabled = false; button.textContent = 'Update stock prices';
    }
  }
  document.addEventListener('click', event => { if (event.target?.id === 'refresh-prices') refresh(event.target); });
  new MutationObserver(addButton).observe(document.documentElement, { childList: true, subtree: true }); addButton();
})();
