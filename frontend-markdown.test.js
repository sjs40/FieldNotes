const assert = require('assert');
const { render } = require('./fieldnotes-markdown.js');

assert.match(render('# Heading\n\n**strong** and _emphasis_'), /<h1>Heading<\/h1>/);
assert.match(render('- [x] Done\n- [ ] Next'), /class="task-list"/);
assert.match(render('| Metric | Value |\n| --- | --- |\n| Revenue | 10 |'), /<table>/);
assert.match(render('[Source](https://example.com)'), /rel="noopener noreferrer"/);
assert.doesNotMatch(render('<script>alert(1)</script>'), /<script>/);
assert.match(render('<script>alert(1)</script>'), /&lt;script&gt;/);
console.log('Markdown renderer tests passed.');
