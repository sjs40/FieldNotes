/* UI adapter for the authenticated FastAPI market-data endpoint. */
(function () {
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
    button.disabled = true; button.textContent = 'Updating prices…';
    try {
      // The API derives symbols from the signed-in user's open calls; browser
      // storage is never a source of truth for price refreshes.
      const response = await fetch('/api/market-data/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!response.ok) throw new Error('The quote provider did not return data.');
      const { quotes, failures } = await response.json();
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
