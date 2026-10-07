const $ = id => document.getElementById(id);
const text = (node, value) => { node.textContent = String(value); return node; };
const el = (tag, value) => text(document.createElement(tag), value);
const link = (url, label) => { const a = el('a', label); if (url && /^https:\/\/(cdn\.nba\.com|site\.api\.espn\.com|github\.com)\//.test(url)) { a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; } return a; };
function render(data) {
  const cases = data.investigations || [], observations = data.observations || [];
  text($('candidate-count'), cases.length); text($('observation-count'), observations.length);
  text($('last-run'), data.runs?.[0]?.fetched_at || 'Not yet run');
  function showCases() {
    const query = $('search').value.toLowerCase(); $('cases').replaceChildren();
    const matches = cases.filter(c => c.id.toLowerCase().includes(query));
    if (!matches.length) $('cases').append(el('p', cases.length ? 'No matching candidates.' : 'No candidate disagreements recorded yet. This does not prove none exist.'));
    for (const c of matches) {
      const card = document.createElement('article'); card.className = 'card';
      card.append(el('h3', c.id), el('p', `${c.status} · Observed ${c.observed_at} UTC`));
      const scores = document.createElement('div'); scores.className = 'scores';
      for (const [name, source] of [['NBA CDN', c.nba], ['ESPN', c.espn]]) {
        const block = document.createElement('div'); block.append(link(source.source_url, name), el('strong', `${source.away_score}–${source.home_score} (away–home)`), el('small', `Game ID: ${source.source_id}`)); if (source.response_sha256) block.append(document.createTextNode(' · '), link(`https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/blob/main/data/raw/${source.response_sha256}.json.gz`, 'Archived bytes ↗')); scores.append(block);
      }
      card.append(scores, el('p', c.note)); $('cases').append(card);
    }
  }
  $('search').addEventListener('input', showCases); showCases();
  const body = $('observations');
  for (const row of [...observations].reverse().slice(0, 150)) {
    const tr = document.createElement('tr');
    for (const value of [row.fetched_at, `${row.date} · ${row.away} @ ${row.home}`, row.source, `${row.away_score}–${row.home_score}`, row.status]) tr.append(el('td', value));
    const source = document.createElement('td'); source.append(link(row.source_url, 'Open feed ↗')); tr.append(source); body.append(tr);
  }
  if (!observations.length) { const tr = document.createElement('tr'); const td = el('td', 'No observations collected yet.'); td.colSpan = 6; tr.append(td); body.append(tr); }
}
fetch('dataset.json').then(r => { if (!r.ok) throw Error('Dataset unavailable'); return r.json(); }).then(render).catch(() => { $('cases').append(el('p', 'Dataset unavailable. Check deployment or try again later.')); });
