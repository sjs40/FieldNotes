/* Safe, dependency-free Markdown subset for research notes. Raw HTML is text. */
(function (root) {
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const safeUrl = value => {
    try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : null; }
    catch { return null; }
  };
  const inline = value => {
    const links = [];
    const token = html => `\u0000${links.push(html) - 1}\u0000`;
    let text = String(value ?? '').replace(/\[([^\]]+)]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) => {
      const safe = safeUrl(url); return safe ? token(`<a href="${escapeHtml(safe)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`) : label;
    });
    text = text.replace(/https?:\/\/[^\s<]+/g, raw => {
      const url = raw.replace(/[.,;:!?]+$/, ''), suffix = raw.slice(url.length), safe = safeUrl(url);
      return safe ? token(`<a href="${escapeHtml(safe)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>`) + suffix : raw;
    });
    text = escapeHtml(text)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/__([^_]+)__/g, '<strong>$1</strong>')
      .replace(/~~([^~]+)~~/g, '<del>$1</del>')
      .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
      .replace(/(^|[^_])_([^_]+)_/g, '$1<em>$2</em>');
    return text.replace(/\u0000(\d+)\u0000/g, (_, index) => links[Number(index)] || '');
  };
  const cells = line => line.trim().replace(/^\||\|$/g, '').split('|').map(cell => inline(cell.trim()));
  const isTableDivider = line => /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
  const isBlockStart = line => /^(#{1,6}\s|```|>\s?|[-*+]\s+|\d+\.\s+|\|)|^\s*$/.test(line) || /^---+$/.test(line);
  function render(markdown) {
    const lines = String(markdown ?? '').replace(/\r\n?/g, '\n').split('\n'), output = [];
    for (let index = 0; index < lines.length;) {
      const line = lines[index];
      if (!line.trim()) { index++; continue; }
      if (/^```/.test(line)) { const code = []; index++; while (index < lines.length && !/^```/.test(lines[index])) code.push(lines[index++]); if (index < lines.length) index++; output.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`); continue; }
      const heading = line.match(/^(#{1,6})\s+(.+)$/); if (heading) { const level = heading[1].length; output.push(`<h${level}>${inline(heading[2])}</h${level}>`); index++; continue; }
      if (/^---+$/.test(line)) { output.push('<hr>'); index++; continue; }
      if (line.startsWith('>')) { const quote = []; while (index < lines.length && lines[index].startsWith('>')) quote.push(lines[index++].replace(/^>\s?/, '')); output.push(`<blockquote>${inline(quote.join('\n')).replace(/\n/g, '<br>')}</blockquote>`); continue; }
      if (line.includes('|') && index + 1 < lines.length && isTableDivider(lines[index + 1])) { const headers = cells(line), rows = []; index += 2; while (index < lines.length && lines[index].includes('|') && lines[index].trim()) rows.push(cells(lines[index++])); output.push(`<div class="markdown-table-wrap"><table><thead><tr>${headers.map(cell => `<th>${cell}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`); continue; }
      const unordered = line.match(/^\s*[-*+]\s+(?:\[([ xX])]\s+)?(.*)$/); const ordered = line.match(/^\s*\d+\.\s+(.*)$/);
      if (unordered || ordered) { const items = [], taskList = Boolean(unordered && unordered[1] !== undefined), orderedList = Boolean(ordered); while (index < lines.length) { const match = orderedList ? lines[index].match(/^\s*\d+\.\s+(.*)$/) : lines[index].match(/^\s*[-*+]\s+(?:\[([ xX])]\s+)?(.*)$/); if (!match) break; const content = orderedList ? match[1] : match[2]; const checkbox = taskList ? `<input type="checkbox" disabled ${match[1]?.toLowerCase() === 'x' ? 'checked' : ''}>` : ''; items.push(`<li>${checkbox}${inline(content)}</li>`); index++; } output.push(`<${orderedList ? 'ol' : 'ul'}${taskList ? ' class="task-list"' : ''}>${items.join('')}</${orderedList ? 'ol' : 'ul'}>`); continue; }
      const paragraph = [line]; index++; while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index])) paragraph.push(lines[index++]); output.push(`<p>${inline(paragraph.join('\n')).replace(/\n/g, '<br>')}</p>`);
    }
    return output.join('') || '<p></p>';
  }
  const api = { render, escapeHtml };
  root.fieldnotesMarkdown = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
