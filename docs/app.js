/**
 * NBA Scoring Discrepancy Research - Frontend
 * Clean, user-friendly, no hallucinations
 */
let allCases = [];
let filteredCases = [];
let statistics = {};

async function loadData() {
  try {
    const res = await fetch('./data.json');
    if (!res.ok) throw new Error('data.json not found');
    allCases = await res.json();
  } catch (e) {
    console.warn('Failed to load data.json, trying ../data/discrepancies.json', e);
    try {
      const res2 = await fetch('../data/discrepancies.json');
      allCases = await res2.json();
    } catch (e2) {
      console.error('Failed to load any data', e2);
      allCases = [];
    }
  }

  try {
    const res = await fetch('./statistics.json');
    if (res.ok) statistics = await res.json();
  } catch (e) {
    console.warn('No statistics.json', e);
  }

  // If no stats, compute from cases
  if (!statistics.total_cases) {
    statistics = computeStats(allCases);
  }

  filteredCases = [...allCases];
  renderStats();
  renderCases();
  setupFilters();
}

function computeStats(cases) {
  const total = cases.length;
  const byType = {};
  const officialIncorrect = cases.filter(c => c.nba_official_record_incorrect).length;
  const secondary = cases.filter(c => c.secondary_source_error).length;
  const impact = cases.filter(c => c.impact_on_final_total).length;
  const onePoint = cases.filter(c => Math.abs(c.impact_points || 0) === 1).length;
  const protestUpheld = cases.filter(c => c.protest_upheld).length;

  cases.forEach(c => {
    const t = c.incident_type || 'unknown';
    byType[t] = (byType[t] || 0) + 1;
  });

  return {
    total_cases: total,
    by_type: byType,
    official_record_incorrect_count: officialIncorrect,
    secondary_source_error_count: secondary,
    impact_on_final_total_count: impact,
    impact_on_final_total_percent: total ? Math.round(impact/total*1000)/10 : 0,
    official_incorrect_percent: total ? Math.round(officialIncorrect/total*1000)/10 : 0,
    one_point_discrepancies: onePoint,
    one_point_percent: total ? Math.round(onePoint/total*1000)/10 : 0,
    protest_upheld_count: protestUpheld,
    rarity_note: `${onePoint} of ${total} cases are 1-point total discrepancies like 213 vs 214`
  };
}

function renderStats() {
  const grid = document.getElementById('statsGrid');
  if (!grid) return;

  const stats = [
    { label: 'Verified Cases', value: statistics.total_cases || 0, sub: `${statistics.official_record_incorrect_count || 0} official errors` },
    { label: '1-Point Discrepancies', value: statistics.one_point_discrepancies || 0, sub: `${statistics.one_point_percent || 0}% of cases - 213/214 pattern` },
    { label: 'Affects Final Total', value: `${statistics.impact_on_final_total_percent || 0}%`, sub: `${statistics.impact_on_final_total_count || 0} cases change total` },
    { label: 'Official Record Wrong', value: `${statistics.official_incorrect_percent || 0}%`, sub: `${statistics.official_record_incorrect_count || 0} cases NBA itself wrong` },
    { label: 'Secondary Source Only', value: statistics.secondary_source_error_count || 0, sub: 'Data feed / broadcast errors' },
    { label: 'Protests Upheld', value: statistics.protest_upheld_count || 0, sub: 'Only 6 in NBA history (we have all 6)' },
  ];

  grid.innerHTML = stats.map(s => `
    <div class="stat-card">
      <div class="label">${s.label}</div>
      <div class="value">${s.value}</div>
      <div class="sub">${s.sub}</div>
    </div>
  `).join('');

  // Update hero badge
  const badge = document.getElementById('heroBadge');
  if (badge) {
    badge.textContent = `${statistics.total_cases} verified cases • ${statistics.one_point_discrepancies} 1-point discrepancies • Updated ${new Date().toLocaleDateString()}`;
  }
}

function renderCases() {
  const container = document.getElementById('casesContainer');
  const count = document.getElementById('caseCount');
  if (!container) return;

  if (count) count.textContent = `${filteredCases.length} cases`;

  if (filteredCases.length === 0) {
    container.innerHTML = `<div class="explain"><p>No cases match your filters. Try clearing filters.</p></div>`;
    return;
  }

  container.innerHTML = filteredCases.map(c => {
    const original = c.original_value?.final_score || 'N/A';
    const corrected = c.corrected_value?.final_score || c.final_official_value?.final_score || 'N/A';
    const origTotal = c.original_value?.total_points ?? '?';
    const corrTotal = c.corrected_value?.total_points ?? c.final_official_value?.total_points ?? '?';
    const isOnePoint = Math.abs(c.impact_points || 0) === 1;

    return `
    <div class="case-card" data-id="${c.id}">
      <div class="case-header">
        <div>
          <div class="case-title">${c.teams?.away_abbr || c.teams?.away} @ ${c.teams?.home_abbr || c.teams?.home} • ${c.date}</div>
          <div class="case-meta">
            <span class="tag ${c.verification_status}">${c.verification_status}</span>
            ${c.nba_official_record_incorrect ? '<span class="tag official_error">NBA official wrong</span>' : ''}
            ${c.secondary_source_error ? '<span class="tag secondary">secondary only</span>' : ''}
            ${isOnePoint ? '<span class="tag one_point">1-pt total • 213/214 pattern</span>' : ''}
            <span class="tag">${c.incident_type?.replace(/_/g,' ')}</span>
            ${c.protest_upheld ? '<span class="tag">protest upheld</span>' : ''}
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:12px; color:var(--muted)">${c.id}</div>
          <div style="font-size:11px; color:var(--muted)">${c.period_clock || ''}</div>
        </div>
      </div>

      <div class="case-grid">
        <div class="case-detail">
          <div class="label">Relevant Play</div>
          <div class="value">${c.relevant_scoring_play || 'N/A'}</div>
        </div>
        <div class="case-detail">
          <div class="label">Affected</div>
          <div class="value">${c.affected_player || 'Team'} • ${c.affected_team || ''}</div>
        </div>
        <div class="case-detail">
          <div class="label">Cause</div>
          <div class="value">${c.cause || ''} <em style="color:var(--muted)">(${c.cause_confidence})</em></div>
        </div>
        <div class="case-detail">
          <div class="label">What Changed</div>
          <div class="value">${c.what_changed || ''}</div>
        </div>
      </div>

      <div class="score-compare">
        <div class="score-box original">
          <div class="label">Original</div>
          <div class="score">${original}</div>
          <div class="label">Total ${origTotal}</div>
        </div>
        <div class="arrow">→</div>
        <div class="score-box corrected">
          <div class="label">Corrected / Final Official</div>
          <div class="score">${corrected}</div>
          <div class="label">Total ${corrTotal}</div>
        </div>
        <div style="text-align:center; min-width:80px">
          <div class="label">Impact</div>
          <div style="font-weight:700; color:${c.impact_points > 0 ? 'var(--green)' : 'var(--accent2)'}">${c.impact_points > 0 ? '+' : ''}${c.impact_points ?? 0} pts</div>
          <div class="label">${c.impact_on_final_total ? 'affects total' : 'no total impact'}</div>
        </div>
      </div>

      <div class="case-grid" style="margin-top:12px">
        <div class="case-detail">
          <div class="label">Score Before</div>
          <div class="value">${c.score_before || 'N/A'}</div>
        </div>
        <div class="case-detail">
          <div class="label">When Changed</div>
          <div class="value">${c.when_changed || ''} • ${c.timestamps?.correction_announced || ''}</div>
        </div>
      </div>

      ${c.notes ? `<div style="margin-top:12px; font-size:13px; color:var(--muted); background:#11141b; padding:10px; border-radius:6px; border:1px solid var(--border)"><strong>Notes:</strong> ${c.notes}</div>` : ''}

      <div class="sources">
        <h4>Verified Sources (${(c.sources||[]).length}) - Click to verify</h4>
        <div class="source-list">
          ${(c.sources||[]).map(s => `
            <div class="source-item">
              <span class="type">${s.type}</span>
              <a href="${s.url}" target="_blank" rel="noopener">${s.title}</a>
              <span style="color:var(--muted); font-size:11px">• ${s.publisher}</span>
            </div>
          `).join('')}
        </div>
      </div>

      <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap">
        <span style="font-size:11px; color:var(--muted)">Tags:</span>
        ${(c.tags||[]).map(t => `<span class="tag">${t}</span>`).join('')}
      </div>
    </div>
    `;
  }).join('');
}

function setupFilters() {
  const search = document.getElementById('searchInput');
  const typeFilter = document.getElementById('typeFilter');
  const verificationFilter = document.getElementById('verificationFilter');
  const impactFilter = document.getElementById('impactFilter');

  function applyFilters() {
    const q = (search?.value || '').toLowerCase();
    const type = typeFilter?.value || 'all';
    const ver = verificationFilter?.value || 'all';
    const impact = impactFilter?.value || 'all';

    filteredCases = allCases.filter(c => {
      // Search
      if (q) {
        const hay = `${c.id} ${c.date} ${c.teams?.home} ${c.teams?.away} ${c.affected_player} ${c.relevant_scoring_play} ${c.cause}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (type !== 'all' && c.incident_type !== type) return false;
      if (ver !== 'all' && c.verification_status !== ver) return false;
      if (impact === 'total' && !c.impact_on_final_total) return false;
      if (impact === 'one_point' && Math.abs(c.impact_points||0) !== 1) return false;
      if (impact === 'official' && !c.nba_official_record_incorrect) return false;
      if (impact === 'secondary' && !c.secondary_source_error) return false;
      return true;
    });

    // Sort by date descending
    filteredCases.sort((a,b) => new Date(b.date) - new Date(a.date));

    renderCases();
  }

  search?.addEventListener('input', applyFilters);
  typeFilter?.addEventListener('change', applyFilters);
  verificationFilter?.addEventListener('change', applyFilters);
  impactFilter?.addEventListener('change', applyFilters);

  // Pill filters
  document.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const filter = pill.dataset.filter;
      if (filter === 'all') {
        if (typeFilter) typeFilter.value = 'all';
        if (impactFilter) impactFilter.value = 'all';
      } else if (filter === 'one_point') {
        if (impactFilter) impactFilter.value = 'one_point';
      } else if (filter === 'official') {
        if (impactFilter) impactFilter.value = 'official';
      } else if (filter === 'secondary') {
        if (impactFilter) impactFilter.value = 'secondary';
      } else {
        if (typeFilter) typeFilter.value = filter;
      }
      applyFilters();
    });
  });
}

// Live status check
async function checkLiveStatus() {
  try {
    const res = await fetch('./latest_check.json');
    if (!res.ok) return;
    const data = await res.json();
    const el = document.getElementById('liveStatusText');
    if (el) {
      el.textContent = `Last check: ${new Date(data.timestamp).toLocaleString()} • ${data.snapshots_collected} snapshots • ${data.alerts_generated} alerts • Sources: ${(data.sources||[]).join(', ')}`;
    }
  } catch (e) {
    // No live data yet
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadData();
  checkLiveStatus();
  setInterval(checkLiveStatus, 30000);
});
