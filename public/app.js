/**
 * Who Woulda Won? - Frontend JavaScript
 */

// Quickstart URLs — curated scoresheets for first-time users
const QUICKSTART_URLS = [
    'https://scoring.dance/enCA/events/362/results/5126.html', // Trinity 2026 Novice
    'https://scoring.dance/enCA/events/349/results/5040.html', // SwingVester 2025-26 Novice
    'https://scoring.dance/enCA/events/354/results/4996.html', // Budafest 2025 Novice
    'https://scoring.dance/enCA/events/352/results/4943.html', // Westie Gala 2025-26 Advanced
    'https://scoring.dance/enCA/events/272/results/4906.html', // Monterey 2026 All-Star
    'https://scoring.dance/enCA/events/328/results/4866.html', // Santa Swing 2025 Newcomer
    'https://scoring.dance/enCA/events/324/results/4734.html', // Warsaw Halloween 2025 Intermediate
    'https://scoring.dance/enCA/events/312/results/4639.html', // SNOW 2025 Sophisticated
    'https://scoring.dance/enCA/events/280/results/4208.html', // German Open 2025 All-Star
    'https://scoring.dance/enCA/events/280/results/4201.html', // German Open 2025 Novice
    'https://danceconvention.net/eventdirector/en/roundscores/301146763.pdf', // TAP 2025 Advanced
    'https://danceconvention.net/eventdirector/en/roundscores/301006101.pdf', // NZO 2025 Novice
    'https://danceconvention.net/eventdirector/en/roundscores/300946391.pdf', // BOTB 2025 Novice
    'https://danceconvention.net/eventdirector/en/roundscores/300863133.pdf', // Shakedown 2025 Advanced
    'https://danceconvention.net/eventdirector/en/roundscores/300732280.pdf', // Mania 2025 Intermediate
    'https://danceconvention.net/eventdirector/en/roundscores/300732124.pdf', // Mania 2025 Novice
    'https://danceconvention.net/eventdirector/en/roundscores/7260141.pdf', // NZO 2022 Intermediate
];

// DOM elements
const urlForm = document.getElementById('url-form');
const fileForm = document.getElementById('file-form');
const urlInput = document.getElementById('url-input');
const fileInput = document.getElementById('file-input');
const loadingSection = document.getElementById('loading');
const errorSection = document.getElementById('error');
const errorMessage = document.getElementById('error-message');
const resultsSection = document.getElementById('results');
const competitionName = document.getElementById('competition-name');
const numCompetitors = document.getElementById('num-competitors');
const numJudges = document.getElementById('num-judges');
const resultsHeader = document.getElementById('results-header');
const resultsBody = document.getElementById('results-body');
const votingDetailsContainer = document.getElementById('voting-details-container');
const shareIcons = document.getElementById('share-icons');
const shareCopyBtn = document.getElementById('share-copy');
const shareCopiedMsg = document.getElementById('share-copied-msg');
const shareFacebookLink = document.getElementById('share-facebook');
const shareWhatsappLink = document.getElementById('share-whatsapp');

// Tab switching via inline mode toggle links
const quickstartContainer = document.getElementById('quickstart-container');
let quickstartUsed = false;
let lastAnalysisUrl = null;

document.querySelectorAll('.mode-toggle').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetTab = link.dataset.switchTo;
        document.querySelectorAll('.tab-content').forEach(tc => {
            tc.classList.toggle('active', tc.dataset.tab === targetTab || tc.id === targetTab + '-tab');
        });

        // Hide quickstart on file tab, show on URL tab (if not yet used)
        if (targetTab === 'file') {
            quickstartContainer.classList.add('hidden');
        } else if (!quickstartUsed) {
            quickstartContainer.classList.remove('hidden');
        }
    });
});

// Quickstart link handler
document.getElementById('quickstart-link').addEventListener('click', (e) => {
    e.preventDefault();
    if (QUICKSTART_URLS.length === 0) return;
    const url = QUICKSTART_URLS[Math.floor(Math.random() * QUICKSTART_URLS.length)];
    urlInput.value = url;
    quickstartUsed = true;
    quickstartContainer.classList.add('hidden');
    urlForm.requestSubmit();
});

// URL form submission
urlForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

    quickstartUsed = true;
    quickstartContainer.classList.add('hidden');

    lastAnalysisUrl = url;
    await analyzeScoresheet({ url });
});

// File form submission
fileForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('filename', file.name);

    lastAnalysisUrl = null;
    await analyzeScoresheet(formData);
});

/**
 * Send scoresheet to API for analysis
 * @param {Object|FormData} data - Either {url: string} or FormData with file
 */
async function analyzeScoresheet(data) {
    showLoading();
    hideError();
    hideResults();

    try {
        const isFormData = data instanceof FormData;
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: isFormData ? {} : { 'Content-Type': 'application/json' },
            body: isFormData ? data : JSON.stringify(data),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || `HTTP ${response.status}`);
        }

        displayResults(result);
    } catch (err) {
        showError(err.message);
    } finally {
        hideLoading();
    }
}

/**
 * Display analysis results
 * @param {Object} data - API response with scoresheet and voting results
 */
function displayResults(data) {
    // Set metadata
    competitionName.textContent = data.competition_name;
    numCompetitors.textContent = data.num_competitors;
    numJudges.textContent = data.num_judges;

    // Reorder results so Relative Placement is first
    const results = reorderResults(data.results);

    // Build header row
    resultsHeader.innerHTML = '<th>Competitor</th>';
    const SYSTEM_ABBREVIATIONS = {
        'Relative Placement': 'RP',
        'Borda Count': 'Bor',
        'Schulze Method': 'Sch',
        'Sequential IRV': 'IRV',
    };
    results.forEach(result => {
        const th = document.createElement('th');
        const abbrev = SYSTEM_ABBREVIATIONS[result.system_name] || result.system_name;
        th.innerHTML = `<span class="header-full">${result.system_name}</span><span class="header-abbrev" aria-label="${result.system_name}">${abbrev}</span>`;
        th.setAttribute('title', result.system_name);
        resultsHeader.appendChild(th);
    });

    // Add colgroup so ranking columns share space equally (table-layout: fixed)
    const table = document.getElementById('results-table');
    const existingCg = table.querySelector('colgroup');
    if (existingCg) existingCg.remove();
    const colgroup = document.createElement('colgroup');
    const nameCol = document.createElement('col');
    nameCol.style.width = '40%';
    colgroup.appendChild(nameCol);
    results.forEach(() => colgroup.appendChild(document.createElement('col')));
    table.prepend(colgroup);

    // Get all rankings by competitor
    const competitors = data.competitors;
    const rankings = buildRankingsMap(results, competitors);

    // Build data rows
    resultsBody.innerHTML = '';
    competitors.forEach(competitor => {
        const tr = document.createElement('tr');

        // Competitor name cell
        const nameTd = document.createElement('td');
        nameTd.textContent = competitor;
        tr.appendChild(nameTd);

        // Placement cells for each voting system
        const placements = rankings[competitor];
        const rpPlacement = placements[0]; // Relative Placement is first

        placements.forEach((placement, i) => {
            const td = document.createElement('td');
            td.textContent = formatPlacement(placement);

            // For non-RP columns, show triangle relative to RP placement
            if (i > 0 && placement !== null && rpPlacement !== null) {
                if (placement.rank < rpPlacement.rank) {
                    const arrow = document.createElement('span');
                    arrow.className = 'placement-up';
                    arrow.textContent = ' \u25B2';
                    td.appendChild(arrow);
                } else if (placement.rank > rpPlacement.rank) {
                    const arrow = document.createElement('span');
                    arrow.className = 'placement-down';
                    arrow.textContent = ' \u25BC';
                    td.appendChild(arrow);
                }
            }

            // Highlight winners
            if (placement !== null && placement.rank === 1) {
                td.classList.add('winner');
            }

            tr.appendChild(td);
        });

        resultsBody.appendChild(tr);
    });

    // Render expandable detail blocks for each voting system
    renderVotingDetails(results, data);

    updateShareUrl();
    showResults();
}

/**
 * Reorder results so Relative Placement comes first.
 */
function reorderResults(results) {
    const rpIndex = results.findIndex(r => r.system_name === 'Relative Placement');
    if (rpIndex <= 0) return results; // already first or not found
    const reordered = [results[rpIndex], ...results.slice(0, rpIndex), ...results.slice(rpIndex + 1)];
    return reordered;
}

/**
 * Build a map of competitor -> [{rank, tied} for each system]
 */
function buildRankingsMap(results, competitors) {
    const rankings = {};

    competitors.forEach(competitor => {
        rankings[competitor] = results.map(result => {
            const entry = result.final_ranking.find(e => e.name === competitor);
            return entry ? { rank: entry.rank, tied: entry.tied } : null;
        });
    });

    return rankings;
}

/**
 * Format placement as ordinal (1st, 2nd, etc.), with "=" suffix when tied.
 * Accepts either a number or a {rank, tied} object.
 */
function formatPlacement(placement) {
    if (placement === null || placement === undefined) return '\u2014';

    let n, tied;
    if (typeof placement === 'object') {
        n = placement.rank;
        tied = placement.tied;
    } else {
        n = placement;
        tied = false;
    }

    if (n === null || n === undefined) return '\u2014';

    const suffixes = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return n + (suffixes[(v - 20) % 10] || suffixes[v] || suffixes[0]) + (tied ? '=' : '');
}

/**
 * Escape HTML entities to prevent XSS.
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Create a <th> element with text content.
 */
function createTh(text) {
    const th = document.createElement('th');
    th.textContent = text;
    return th;
}

// ─── Initials utilities ─────────────────────────────────────────────

/**
 * Generate initials for a judge name. If the name looks like it's
 * already initials (2-4 uppercase letters), return as-is.
 * Otherwise, take the first letter of each word.
 */
function judgeInitial(name) {
    if (/^[A-Z]{2,4}$/.test(name.trim())) return name.trim();
    return name.split(/\s+/).map(w => w[0] || '').join('').toUpperCase();
}

/**
 * Build a list of {name, initials} for judges, deduplicating with
 * numeric suffixes when necessary.
 */
function buildJudgeInitials(judges) {
    const raw = judges.map(judgeInitial);

    // Count occurrences of each initial
    const counts = {};
    raw.forEach(init => { counts[init] = (counts[init] || 0) + 1; });

    // Assign suffixes where needed
    const used = {};
    return judges.map((judge, i) => {
        const init = raw[i];
        if (counts[init] > 1) {
            used[init] = (used[init] || 0) + 1;
            return { name: judge, initials: init + used[init] };
        }
        return { name: judge, initials: init };
    });
}

/**
 * Generate a short form for a competitor name:
 * - "Kevin Rocher & Alexandra Pasti" → "KR-AP"
 * - "Alvaro Hilario Garcia & Charlie Fournier" → "AG-CF"
 * - "Kevin Rocher" → "KR"
 *
 * For pairs: first + last initial of each person, joined by hyphen.
 * For singles: all initials.
 */
function competitorInitial(name) {
    if (name.includes('&')) {
        const parts = name.split('&').map(s => s.trim());
        return parts.map(p => {
            const words = p.split(/\s+/);
            const first = (words[0] || '')[0] || '';
            const last = words.length > 1 ? (words[words.length - 1] || '')[0] || '' : '';
            return (first + last).toUpperCase();
        }).join('-');
    }
    return name.split(/\s+/).map(w => (w[0] || '')).join('').toUpperCase();
}

/**
 * Build a list of {name, initials} for competitors, deduplicating with
 * numeric suffixes when necessary.
 */
function buildCompetitorInitials(competitors) {
    const raw = competitors.map(competitorInitial);

    const counts = {};
    raw.forEach(init => { counts[init] = (counts[init] || 0) + 1; });

    const used = {};
    return competitors.map((comp, i) => {
        const init = raw[i];
        if (counts[init] > 1) {
            used[init] = (used[init] || 0) + 1;
            return { name: comp, initials: init + used[init] };
        }
        return { name: comp, initials: init };
    });
}

/**
 * Create a <th> with initials text and an instant tooltip showing the
 * full name on hover. Uses data-tooltip attribute styled via CSS.
 */
function createThWithTooltip(initials, fullName) {
    const th = document.createElement('th');
    th.textContent = initials;
    th.setAttribute('data-tooltip', fullName);
    th.className = 'has-tooltip';
    return th;
}

/**
 * Create a <td> with initials text and an instant tooltip showing the
 * full name on hover.
 */
function createTdWithTooltip(initials, fullName) {
    const td = document.createElement('td');
    td.textContent = initials;
    td.setAttribute('data-tooltip', fullName);
    td.className = 'has-tooltip';
    return td;
}

/**
 * Equalize column widths within groups for a table.
 * For each group class, finds the max header width and applies it to all
 * headers in that group, making like columns the same width.
 */
function equalizeColumnWidths(table, groupClasses) {
    for (const cls of groupClasses) {
        const headers = table.querySelectorAll('thead .' + cls);
        if (headers.length === 0) continue;
        headers.forEach(th => { th.style.minWidth = ''; });
        let maxW = 0;
        headers.forEach(th => { maxW = Math.max(maxW, th.offsetWidth); });
        headers.forEach(th => { th.style.minWidth = maxW + 'px'; });
    }
}

// ─── Voting system detail renderers ──────────────────────────────────

const SYSTEM_RENDERERS = {
    'Relative Placement': renderRPDetails,
    'Borda Count':        renderBordaDetails,
    'Schulze Method':     renderSchulzeDetails,
    'Sequential IRV':     renderIRVDetails,
};

const SYSTEM_BLOCK_IDS = {
    'Relative Placement': 'detail-relative-placement',
    'Borda Count':        'detail-borda-count',
    'Schulze Method':     'detail-schulze-method',
    'Sequential IRV':     'detail-sequential-irv',
};

// Attach column-equalization toggle listeners once (since blocks are now static HTML)
for (const blockId of Object.values(SYSTEM_BLOCK_IDS)) {
    const block = document.getElementById(blockId);
    if (!block) continue;
    block.addEventListener('toggle', () => {
        if (block.open) {
            block.querySelectorAll('.detail-table').forEach(t =>
                equalizeColumnWidths(t, ['col-judge', 'col-cumulative', 'col-matrix'])
            );
            // Cross-table equalization: ensure matching columns across
            // related tables (e.g. Borda main + tiebreak tables)
            equalizeColumnWidths(block, ['col-judge']);
        }
    });
}

/**
 * Render dynamic content into the static voting detail blocks.
 */
function renderVotingDetails(results, data) {
    // Clear all dynamic content areas first
    votingDetailsContainer.querySelectorAll('.detail-dynamic-content').forEach(
        el => { el.innerHTML = ''; }
    );

    for (const result of results) {
        const blockId = SYSTEM_BLOCK_IDS[result.system_name];
        if (!blockId) continue;

        const block = document.getElementById(blockId);
        if (!block) continue;

        const dynamicContent = block.querySelector('.detail-dynamic-content');
        if (!dynamicContent) continue;

        const renderer = SYSTEM_RENDERERS[result.system_name];
        if (renderer) {
            renderer(dynamicContent, result, data);
        }
    }
}

// ─── Relative Placement ──────────────────────────────────────────────

/**
 * Render the Relative Placement working table (danceconvention.net style).
 *
 * Columns: Competitor | J1 | J2 | \u2026 | Jm | 1\u20131 | 1\u20132 | \u2026 | 1\u2013N | Result
 */
function renderRPDetails(container, result, data) {
    const details = result.details;
    const judges = data.judges;
    const rankings = data.rankings;
    const n = data.num_competitors;
    const judgeInfos = buildJudgeInitials(judges);

    // Determine which cumulative cells to display
    const cellDisplay = buildRPCellDisplay(details, n);

    // Sort competitors by final ranking
    const sorted = result.final_ranking.map(e => e.name);

    const wrapper = document.createElement('div');
    wrapper.className = 'detail-table-wrapper';

    const table = document.createElement('table');
    table.className = 'detail-table';

    // Header row
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.appendChild(createTh('Competitor'));
    judgeInfos.forEach(j => {
        const th = createThWithTooltip(j.initials, j.name);
        th.classList.add('col-judge');
        headerRow.appendChild(th);
    });
    for (let p = 1; p <= n; p++) {
        const th = createTh('1\u2013' + p);
        th.classList.add('col-cumulative');
        if (p === 1) th.classList.add('rp-separator');
        headerRow.appendChild(th);
    }
    const resultTh = createTh('Result');
    resultTh.classList.add('rp-result');
    headerRow.appendChild(resultTh);
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body
    const tbody = document.createElement('tbody');

    // Competitor rows
    const rpPlacements = result.final_ranking;
    sorted.forEach((competitor, idx) => {
        const tr = document.createElement('tr');

        // Competitor name
        const nameTd = document.createElement('td');
        nameTd.textContent = competitor;
        tr.appendChild(nameTd);

        // Judge placements
        judges.forEach(judge => {
            const td = document.createElement('td');
            td.textContent = rankings[judge][competitor];
            td.classList.add('rp-judge-cell', 'col-judge');
            tr.appendChild(td);
        });

        // Cumulative count columns
        for (let p = 1; p <= n; p++) {
            const td = document.createElement('td');
            td.classList.add('col-cumulative');
            const key = competitor + '|' + p;
            const display = cellDisplay[key];

            if (display !== undefined) {
                if (display.quality !== undefined) {
                    const countStr = display.count === 0 ? '\u2013' : String(display.count);
                    td.innerHTML = escapeHtml(countStr)
                        + ' <span class="rp-quality">('
                        + escapeHtml(String(display.quality)) + ')</span>';
                } else {
                    td.textContent = display.count === 0 ? '\u2013' : String(display.count);
                }

                if (display.first_majority) {
                    td.classList.add('rp-first-majority');
                }
            } else {
                td.textContent = '\u2013';
            }
            if (p === 1) td.classList.add('rp-separator');

            // Highlight relevant judge cells on hover
            td.addEventListener('mouseenter', function() {
                if (!isNaN(parseInt(this.textContent)) && parseInt(this.textContent) > 0) {
                    this.parentElement.querySelectorAll('.rp-judge-cell').forEach(cell => {
                        if (parseInt(cell.textContent) <= p) {
                            cell.classList.add('rp-highlight');
                        }
                    });
                }
            });
            td.addEventListener('mouseleave', function() {
                this.parentElement.querySelectorAll('.rp-judge-cell').forEach(cell => {
                    cell.classList.remove('rp-highlight');
                });
            });

            tr.appendChild(td);
        }

        // Result column
        const resultTd = document.createElement('td');
        resultTd.textContent = formatPlacement(rpPlacements[idx]);
        resultTd.classList.add('rp-result');
        tr.appendChild(resultTd);

        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    wrapper.appendChild(table);

    container.appendChild(wrapper);
}

/**
 * Determine which RP cumulative cells to display.
 *
 * For each placed competitor, shows cumulative counts from cutoff 1
 * through the cutoff at which they were placed (final_cutoff). Zeros
 * are rendered as dashes by the caller. Quality-of-majority scores
 * are recorded for ALL tiebreak participants (not just the winner),
 * so that the loser's quality is visible when they are placed in a
 * subsequent round.
 *
 * @returns {Object} Map of "competitor|cutoff" -> {count, quality?, first_majority?}
 */
function buildRPCellDisplay(details, n) {
    const display = {};
    const cumCounts = details.cumulative_counts;

    for (const round of details.rounds) {
        const resolution = round.resolution;
        if (!resolution) continue;

        // Record cumulative counts and quality-of-majority scores for
        // ALL candidates in tiebreak progressions (winners and losers
        // alike), so that losers' values are visible when they are
        // placed in a subsequent round.
        const progression = resolution.cutoff_progression;
        if (progression) {
            for (const [index, step] of progression.entries()) {
                for (const [competitor, count] of Object.entries(step.counts || {})) {
                    const key = competitor + '|' + step.cutoff;
                    if (display[key] !== undefined) continue;

                    if (step.quality_scores && step.quality_scores[competitor] !== undefined) {
                        display[key] = {
                            count: count,
                            quality: step.quality_scores[competitor],
                        };
                    } else {
                        display[key] = { count: count };
                    }

                    if (index === 0 && display[key] !== undefined) {
                        display[key].first_majority = true;
                    }
                }
            }
        }

        // Fill in cumulative counts from cutoff 1 through final_cutoff
        // for the competitor(s) placed in this round.
        const finalCutoff = resolution.final_cutoff;
        if (finalCutoff === undefined) continue;

        const winners = round.tied ? (round.winners || []) : [round.winner];
        for (const competitor of winners) {
            for (let cutoff = 1; cutoff <= finalCutoff; cutoff++) {
                const key = competitor + '|' + cutoff;
                if (display[key] !== undefined) continue;
                display[key] = { count: cumCounts[competitor][cutoff] };
            }
        }
    }

    return display;
}

// ─── Borda Count ─────────────────────────────────────────────────────

/**
 * Append a Borda header row (Competitor | J1 | J2 | … | Total) to a tbody.
 */
function appendBordaHeaderRow(tbody, judgeInfos, numCols) {
    const tr = document.createElement('tr');
    const compTh = createTh('Competitor');
    tr.appendChild(compTh);
    judgeInfos.forEach(j => {
        const th = createThWithTooltip(j.initials, j.name);
        th.classList.add('col-judge');
        tr.appendChild(th);
    });
    tr.appendChild(createTh('Total'));
    tbody.appendChild(tr);
}

/**
 * Append Borda data rows to a tbody.
 */
function appendBordaDataRows(tbody, competitors, breakdowns, scores) {
    competitors.forEach(competitor => {
        const tr = document.createElement('tr');

        const nameTd = document.createElement('td');
        nameTd.textContent = competitor;
        tr.appendChild(nameTd);

        const breakdown = breakdowns[competitor];
        breakdown.points.forEach(pts => {
            const td = document.createElement('td');
            td.textContent = pts;
            td.classList.add('col-judge');
            tr.appendChild(td);
        });

        const totalTd = document.createElement('td');
        totalTd.textContent = scores[competitor];
        totalTd.style.fontWeight = '600';
        tr.appendChild(totalTd);

        tbody.appendChild(tr);
    });
}

/**
 * Render the Borda Count as a single unified table.
 * Tiebreak sections appear as spanning header rows within the same table,
 * so all columns share the same widths.
 *
 * Columns: Competitor | J1 pts | J2 pts | \u2026 | Total
 */
function renderBordaDetails(container, result, data) {
    const details = result.details;
    const judges = data.judges;
    const sorted = result.final_ranking.map(e => e.name);
    const judgeInfos = buildJudgeInitials(judges);
    const numCols = 1 + judges.length + 1; // Competitor + judges + Total

    const wrapper = document.createElement('div');
    wrapper.className = 'detail-table-wrapper';

    const table = document.createElement('table');
    table.className = 'detail-table';

    // thead with main header row
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.appendChild(createTh('Competitor'));
    judgeInfos.forEach(j => {
        const th = createThWithTooltip(j.initials, j.name);
        th.classList.add('col-judge');
        headerRow.appendChild(th);
    });
    headerRow.appendChild(createTh('Total'));
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // tbody: main data rows
    const tbody = document.createElement('tbody');
    appendBordaDataRows(tbody, sorted, details.breakdowns, details.scores);

    // Tiebreak sections within the same tbody
    if (details.tiebreakers && details.tiebreakers.length > 0) {
        details.tiebreakers.forEach(tb => {
            const level = tb.level || 1;
            let label;
            if (level === 1) {
                label = `Tiebreak at ${tb.score} points`;
            } else {
                const ord = level === 2 ? '2nd' : level === 3 ? '3rd' : `${level}th`;
                label = `Tiebreak (${ord} level) at ${tb.score} points`;
            }

            // Spanning section header row
            const sectionRow = document.createElement('tr');
            const sectionTd = document.createElement('td');
            sectionTd.colSpan = numCols;
            sectionTd.textContent = label;
            sectionTd.className = 'borda-section-header';
            sectionRow.appendChild(sectionTd);
            tbody.appendChild(sectionRow);

            if (tb.resolution.method === 'recursive-borda') {
                const tbDetails = tb.resolution.details;
                const tbJudgeInfos = buildJudgeInitials(tbDetails.breakdowns[tb.tied_competitors[0]].judges);

                // Repeat column headers for the tiebreak section
                appendBordaHeaderRow(tbody, tbJudgeInfos, numCols);

                // Tiebreak data rows
                const tbSorted = [...tb.tied_competitors].sort(
                    (a, b) => tbDetails.relative_scores[b] - tbDetails.relative_scores[a]
                );
                appendBordaDataRows(tbody, tbSorted, tbDetails.breakdowns, tbDetails.relative_scores);
            } else if (tb.resolution.method === 'unresolved') {
                const msgRow = document.createElement('tr');
                const msgTd = document.createElement('td');
                msgTd.colSpan = numCols;
                msgTd.textContent = 'Tie could not be resolved';
                msgTd.style.fontStyle = 'italic';
                msgTd.style.color = '#666';
                msgTd.style.textAlign = 'center';
                msgRow.appendChild(msgTd);
                tbody.appendChild(msgRow);
            }
        });
    }

    table.appendChild(tbody);
    wrapper.appendChild(table);
    container.appendChild(wrapper);
}

// ─── Schulze Method ──────────────────────────────────────────────────

/**
 * Render Schulze Method details: pairwise preference matrix + path
 * strength matrix with Schulze wins column.
 */
function renderSchulzeDetails(container, result, data) {
    const details = result.details;
    const competitors = result.final_ranking.map(e => e.name);
    const compInfos = buildCompetitorInitials(competitors);
    const compInitialsMap = {};
    compInfos.forEach(c => { compInitialsMap[c.name] = c.initials; });

    // Pairwise Preferences
    const h4a = document.createElement('h4');
    h4a.textContent = 'Pairwise Preferences';
    container.appendChild(h4a);

    const pDesc = document.createElement('p');
    pDesc.className = 'detail-description';
    pDesc.textContent = 'Cell (row, column) = number of judges who prefer row over column.';
    container.appendChild(pDesc);

    const pairwiseTable = buildSchulzeMatrix(competitors, compInitialsMap, details.pairwise_preferences, null);
    container.appendChild(pairwiseTable);

    // Strongest Beatpath Strengths
    const h4b = document.createElement('h4');
    h4b.textContent = 'Strongest Beatpath Strengths';
    container.appendChild(h4b);

    const sDesc = document.createElement('p');
    sDesc.className = 'detail-description';
    const sDescLines = [
        'Cell (row, column) = strength of strongest beatpath from row to column.',
        '\u201cWins\u201d = number of Schulze wins (ties count as half).',
    ];
    const extraCols = [];
    if (details.tiebreak_used === 'winning') {
        // Show Win Str only for competitors whose win count matches another's
        const winCounts = Object.values(details.schulze_wins);
        const winStrRelevant = new Set(Object.keys(details.schulze_wins).filter(c => {
            const myWins = details.schulze_wins[c];
            return winCounts.filter(w => w === myWins).length > 1;
        }));
        extraCols.push({header: 'Win Str', values: details.winning_beatpath_sums, relevant: winStrRelevant});
        sDescLines.push('\u201cWin Str\u201d = sum of winning beatpath strengths (tiebreaker).');
    }
    sDescLines.forEach((line, i) => {
        if (i > 0) sDesc.appendChild(document.createElement('br'));
        sDesc.appendChild(document.createTextNode(line));
    });
    container.appendChild(sDesc);

    container.appendChild(
        buildSchulzeMatrix(competitors, compInitialsMap, details.path_strengths, details.schulze_wins, extraCols, details.beatpaths, pairwiseTable)
    );
}

/**
 * Build a Schulze matrix table (pairwise or path strengths).
 * Cells are coloured green (row beats column) or red (column beats row).
 */
function buildSchulzeMatrix(competitors, compInitialsMap, matrix, winsCol, extraCols, beatpaths, pairwiseTable) {
    extraCols = extraCols || [];
    const wrapper = document.createElement('div');
    wrapper.className = 'detail-table-wrapper';

    const table = document.createElement('table');
    table.className = 'detail-table';

    // Header: blank | blank (initials col) | competitor initials... | Wins?
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.appendChild(createTh(''));    // name column
    headerRow.appendChild(createTh(''));    // initials column
    competitors.forEach(c => {
        const th = createTh(compInitialsMap[c]);
        th.classList.add('col-matrix');
        headerRow.appendChild(th);
    });
    if (winsCol) {
        const winsTh = createTh('Wins');
        winsTh.classList.add('schulze-wins-col');
        headerRow.appendChild(winsTh);
    }
    extraCols.forEach(col => {
        const th = createTh(col.header);
        th.classList.add('schulze-wins-col');
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body
    const tbody = document.createElement('tbody');
    competitors.forEach(rowComp => {
        const tr = document.createElement('tr');

        // Name column
        const labelTd = document.createElement('td');
        labelTd.textContent = rowComp;
        tr.appendChild(labelTd);

        // Initials column
        const initialsTh = document.createElement('th');
        initialsTh.textContent = compInitialsMap[rowComp];
        initialsTh.style.fontWeight = '600';
        tr.appendChild(initialsTh);

        competitors.forEach(colComp => {
            const td = document.createElement('td');
            td.classList.add('col-matrix');
            td.setAttribute('data-row', rowComp);
            td.setAttribute('data-col', colComp);
            if (rowComp === colComp) {
                td.textContent = '\u2014';
                td.classList.add('cell-diagonal');
            } else {
                const value = matrix[rowComp][colComp];
                const opposite = matrix[colComp][rowComp];
                td.textContent = value;
                if (value > opposite) {
                    td.classList.add('cell-wins');
                } else if (value < opposite) {
                    td.classList.add('cell-loses');
                } else if (value == opposite) {
                    td.classList.add('cell-ties');
                }
                if (beatpaths && beatpaths[rowComp] && beatpaths[rowComp][colComp]) {
                    const path = beatpaths[rowComp][colComp];
                    const parts = path.map((step, idx) => {
                        const initials = compInitialsMap[step.node] || step.node;
                        if (step.strength != null) {
                            return initials + ' \u2500[' + step.strength + ']\u2192 ';
                        }
                        return initials;
                    });
                    td.setAttribute('data-tooltip', parts.join(''));
                    td.classList.add('has-tooltip');

                    if (pairwiseTable) {
                        // Build list of (row, col) pairs along the beatpath
                        const steps = [];
                        for (let s = 0; s < path.length - 1; s++) {
                            steps.push([path[s].node, path[s + 1].node]);
                        }
                        td.addEventListener('mouseenter', () => {
                            steps.forEach(([r, c]) => {
                                const cell = pairwiseTable.querySelector(
                                    `td[data-row="${r}"][data-col="${c}"]`
                                );
                                if (cell) cell.classList.add('cell-beatpath-highlight');
                            });
                        });
                        td.addEventListener('mouseleave', () => {
                            pairwiseTable.querySelectorAll('.cell-beatpath-highlight')
                                .forEach(el => el.classList.remove('cell-beatpath-highlight'));
                        });
                    }
                }
            }
            tr.appendChild(td);
        });

        if (winsCol) {
            const winsTd = document.createElement('td');
            winsTd.textContent = winsCol[rowComp];
            winsTd.classList.add('schulze-wins-col');
            tr.appendChild(winsTd);
        }
        extraCols.forEach(col => {
            const td = document.createElement('td');
            td.textContent = (col.relevant && !col.relevant.has(rowComp)) ? '\u2014' : col.values[rowComp];
            td.classList.add('schulze-wins-col');
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });

    table.appendChild(tbody);

    // Column highlighting on hover for matrix cells
    table.querySelectorAll('td.col-matrix').forEach(cell => {
        cell.addEventListener('mouseenter', () => {
            const col = cell.getAttribute('data-col');
            table.querySelectorAll(`td[data-col="${col}"]`).forEach(el => el.classList.add('col-highlight'));
            table.querySelectorAll(`th.col-matrix`).forEach(th => {
                if (th.textContent === compInitialsMap[col]) th.classList.add('col-highlight');
            });
        });
        cell.addEventListener('mouseleave', () => {
            table.querySelectorAll('.col-highlight').forEach(el => el.classList.remove('col-highlight'));
        });
    });

    wrapper.appendChild(table);
    return wrapper;
}

// ─── Sequential IRV ──────────────────────────────────────────────────

/**
 * Render Sequential IRV details: ballot reference table + step-by-step
 * narrative for each placement round.
 */
function renderIRVDetails(container, result, data) {
    const details = result.details;
    const judges = data.judges;
    const rankings = data.rankings;
    const competitors = data.competitors;

    const compInfos = buildCompetitorInitials(competitors);
    const compInitialsMap = {};
    compInfos.forEach(c => { compInitialsMap[c.name] = c.initials; });
    const judgeInfos = buildJudgeInitials(judges);

    // Name-to-initials reference table
    const refH4 = document.createElement('h4');
    refH4.textContent = 'Competitor Key';
    container.appendChild(refH4);

    container.appendChild(buildInitialsRefTable(compInfos));

    // Ballot reference table
    const ballotH4 = document.createElement('h4');
    ballotH4.textContent = 'Judge Ballots';
    container.appendChild(ballotH4);

    container.appendChild(buildBallotTable(judgeInfos, rankings, competitors, compInitialsMap));

    // Placement rounds
    const roundsH4 = document.createElement('h4');
    roundsH4.textContent = 'Placement Rounds';
    container.appendChild(roundsH4);

    for (const placementRound of details.placement_rounds) {
        const roundDiv = document.createElement('div');
        roundDiv.className = 'irv-placement-round';

        const heading = document.createElement('strong');
        heading.textContent = formatPlacement(placementRound.place) + ' place';
        roundDiv.appendChild(heading);

        if (placementRound.method === 'last_remaining') {
            const p = document.createElement('p');
            p.className = 'irv-round-step';
            const winner = placementRound.winner;
            const winnerInit = compInitialsMap[winner] || winner;
            p.innerHTML = '<span class="irv-winner">'
                + escapeHtml(winnerInit)
                + '</span> \u2014 last remaining competitor.';
            roundDiv.appendChild(p);
        } else {
            renderIRVRounds(roundDiv, placementRound, compInitialsMap);
        }

        container.appendChild(roundDiv);
    }
}

/**
 * Build a compact name-to-initials reference table.
 */
function buildInitialsRefTable(compInfos) {
    const wrapper = document.createElement('div');
    wrapper.className = 'detail-table-wrapper';

    const table = document.createElement('table');
    table.className = 'detail-table';

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.appendChild(createTh('Initials'));
    headerRow.appendChild(createTh('Competitor'));
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    compInfos.forEach(c => {
        const tr = document.createElement('tr');
        const initTd = document.createElement('td');
        initTd.textContent = c.initials;
        initTd.style.fontWeight = '600';
        tr.appendChild(initTd);
        const nameTd = document.createElement('td');
        nameTd.textContent = c.name;
        tr.appendChild(nameTd);
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    wrapper.appendChild(table);
    return wrapper;
}

/**
 * Build the ballot reference table for IRV.
 * Rows = rank positions, Columns = judges (initials with tooltips),
 * Cells = competitor initials.
 */
function buildBallotTable(judgeInfos, rankings, competitors, compInitialsMap) {
    const wrapper = document.createElement('div');
    wrapper.className = 'detail-table-wrapper';

    const table = document.createElement('table');
    table.className = 'detail-table';

    // Header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.appendChild(createTh('Rank'));
    judgeInfos.forEach(j => {
        const th = createThWithTooltip(j.initials, j.name);
        th.classList.add('col-judge');
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Invert rankings: for each judge, build position -> competitor
    const judges = judgeInfos.map(j => j.name);
    const ballots = {};
    for (const judge of judges) {
        ballots[judge] = {};
        for (const comp of competitors) {
            ballots[judge][rankings[judge][comp]] = comp;
        }
    }

    // Body
    const tbody = document.createElement('tbody');
    for (let rank = 1; rank <= competitors.length; rank++) {
        const tr = document.createElement('tr');

        const rankTd = document.createElement('td');
        rankTd.textContent = formatPlacement(rank);
        tr.appendChild(rankTd);

        judges.forEach(judge => {
            const td = document.createElement('td');
            td.classList.add('col-judge');
            const fullName = ballots[judge][rank] || '';
            td.textContent = fullName ? (compInitialsMap[fullName] || fullName) : '\u2014';
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    }

    table.appendChild(tbody);
    wrapper.appendChild(table);
    return wrapper;
}

/**
 * Build a vote count string from a votes dict, sorted descending by count.
 */
function buildVoteStr(votes, compInitialsMap) {
    return Object.entries(votes)
        .sort((a, b) => b[1] - a[1])
        .map(([comp, count]) => escapeHtml(compInitialsMap[comp] || comp) + ':\u00a0' + count)
        .join(', ');
}

/**
 * Map a list of competitor names to initials.
 */
function initialsFor(names, compInitialsMap) {
    return names.map(c => escapeHtml(compInitialsMap[c] || c)).join(', ');
}

/**
 * Return the ordinal suffix for a number (1st, 2nd, 3rd, 4th, ...).
 */
function ordinal(n) {
    const s = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

/**
 * Render IRV elimination rounds for one placement position.
 */
function renderIRVRounds(container, placementRound, compInitialsMap) {
    // Show note about excluded zero-vote candidates if applicable
    if (placementRound.irv_rounds.length > 0) {
        const firstRound = placementRound.irv_rounds[0];
        if (firstRound.excluded_zero_vote && firstRound.excluded_zero_vote.length > 0) {
            const note = document.createElement('p');
            note.className = 'irv-round-step irv-note';
            const names = firstRound.excluded_zero_vote
                .map(c => compInitialsMap[c] || c)
                .join(', ');
            note.textContent = 'Excluded (no first-choice votes): ' + names;
            container.appendChild(note);
        }
    }

    for (const round of placementRound.irv_rounds) {
        const step = document.createElement('p');
        step.className = 'irv-round-step';

        const voteStr = buildVoteStr(round.votes, compInitialsMap);

        if (round.method === 'all_tied_equal') {
            const winnerNames = Array.isArray(round.winner) ? round.winner : [round.winner];
            const winnerStr = initialsFor(winnerNames, compInitialsMap);
            step.innerHTML = 'Round ' + round.round + ' \u2014 '
                + voteStr + ' \u2014 all tied. '
                + winnerStr + ' declared equal.';
        } else if (round.winner) {
            const winnerNames = Array.isArray(round.winner) ? round.winner : [round.winner];
            const winnerStr = initialsFor(winnerNames, compInitialsMap);
            step.innerHTML = 'Round ' + round.round + ' \u2014 '
                + voteStr + ' \u2014 '
                + '<span class="irv-winner">' + winnerStr
                + ' wins</span> (majority: ' + round.majority_needed + ').';
        } else if (round.eliminated) {
            const elimInit = compInitialsMap[round.eliminated] || round.eliminated;
            let reason = 'fewest votes';
            if (round.tiebreak_choice) {
                reason = 'fewest ' + ordinal(round.tiebreak_choice) + '-choice votes';
            } else if (round.tiebreak) {
                reason = 'tiebreak';
            }
            step.innerHTML = 'Round ' + round.round + ' \u2014 '
                + voteStr + ' \u2014 '
                + '<span class="irv-eliminated">'
                + escapeHtml(elimInit)
                + ' eliminated</span> (' + reason + ').';
        }

        container.appendChild(step);

        // Render tiebreak details if present
        if (round.tiebreak) {
            const tbDiv = renderTiebreakDetails(round.tiebreak, compInitialsMap);
            container.appendChild(tbDiv);
        }
    }
}

/**
 * Render tiebreak details as an indented block.
 */
function renderTiebreakDetails(tiebreak, compInitialsMap) {
    const wrapper = document.createElement('div');
    wrapper.className = 'irv-tiebreak';

    const tiedStr = initialsFor(tiebreak.tied_candidates, compInitialsMap);
    const header = document.createElement('div');
    header.className = 'irv-tiebreak-header';
    header.textContent = 'Tiebreak among: ' + tiedStr;
    wrapper.appendChild(header);

    for (const step of tiebreak.steps) {
        const stepEl = renderTiebreakStep(step, compInitialsMap);
        wrapper.appendChild(stepEl);
    }

    return wrapper;
}

/**
 * Render a single tiebreak step.
 */
function renderTiebreakStep(step, compInitialsMap) {
    const div = document.createElement('div');
    div.className = 'irv-tiebreak-step';

    if (step.method === 'restricted_vote') {
        renderRestrictedVoteStep(div, step, compInitialsMap);
    } else if (step.method === 'random') {
        renderRandomStep(div, step, compInitialsMap);
    }

    return div;
}


/**
 * Render a restricted-vote tiebreak step.
 */
function renderRestrictedVoteStep(container, step, compInitialsMap) {
    const p = document.createElement('p');
    p.className = 'irv-tiebreak-line';

    const voteStr = buildVoteStr(step.votes, compInitialsMap);
    let text = 'Restricted vote: ' + voteStr + '.';

    if (step.resolved) {
        const elimInit = escapeHtml(compInitialsMap[step.eliminated] || step.eliminated);
        text += ' \u2192 <span class="irv-eliminated">'
            + elimInit + ' eliminated</span> (fewest).';
    } else if (step.all_equal) {
        text += ' All still tied.';
    } else {
        const tiedStr = initialsFor(step.remaining_tied, compInitialsMap);
        text += ' Still tied for fewest: ' + tiedStr + '.';
    }

    p.innerHTML = text;
    container.appendChild(p);
}

/**
 * Render a random-choice tiebreak step (boldface to flag randomness).
 */
function renderRandomStep(container, step, compInitialsMap) {
    const p = document.createElement('p');
    p.className = 'irv-tiebreak-line';

    const names = initialsFor(step.remaining_tied, compInitialsMap);
    const elimInit = escapeHtml(compInitialsMap[step.eliminated] || step.eliminated);
    p.innerHTML = '<strong>Tie among ' + names
        + ' could not be resolved. '
        + '<span class="irv-eliminated">' + elimInit
        + ' eliminated</span> at random.</strong>';

    container.appendChild(p);
}

// ─── UI helpers ──────────────────────────────────────────────────────

function showLoading() {
    loadingSection.classList.remove('hidden');
}

function hideLoading() {
    loadingSection.classList.add('hidden');
}

function showError(message) {
    // Parse plain-text error into structured HTML.
    // Lines starting with "  - " become list items; others become paragraphs.
    const lines = message.split('\n').filter(l => l.trim() !== '');
    let html = '';
    let inList = false;

    lines.forEach(line => {
        const trimmed = line.replace(/^\s+-\s+/, '');
        if (line.match(/^\s+-\s+/)) {
            if (!inList) {
                html += '<ul>';
                inList = true;
            }
            html += '<li>' + escapeHtml(trimmed) + '</li>';
        } else {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            html += '<p>' + escapeHtml(line) + '</p>';
        }
    });

    if (inList) {
        html += '</ul>';
    }

    errorMessage.innerHTML = html;
    errorSection.classList.remove('hidden');
}

function hideError() {
    errorSection.classList.add('hidden');
}

function showResults() {
    resultsSection.classList.remove('hidden');
}

function hideResults() {
    resultsSection.classList.add('hidden');
    hideShareIcons();
    // Clear dynamic content but preserve static HTML structure
    votingDetailsContainer.querySelectorAll('.detail-dynamic-content').forEach(
        el => { el.innerHTML = ''; }
    );
    // Close any open detail blocks
    votingDetailsContainer.querySelectorAll('details[open]').forEach(
        el => { el.removeAttribute('open'); }
    );
}

// ─── Share icons ─────────────────────────────────────────────────────

function showShareIcons(shareUrl) {
    shareFacebookLink.href = 'https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(shareUrl);
    shareWhatsappLink.href = 'https://api.whatsapp.com/send?text=' + encodeURIComponent(shareUrl);
    shareCopyBtn.dataset.shareUrl = shareUrl;
    shareIcons.classList.remove('hidden');
}

function hideShareIcons() {
    shareIcons.classList.add('hidden');
}

function updateShareUrl() {
    if (lastAnalysisUrl) {
        const shareUrl = new URL(window.location.pathname, window.location.origin);
        shareUrl.searchParams.set('url', lastAnalysisUrl);
        const shareUrlStr = shareUrl.toString();
        history.replaceState(null, '', shareUrlStr);
        showShareIcons(shareUrlStr);
    } else {
        history.replaceState(null, '', window.location.pathname);
        hideShareIcons();
    }
}

shareCopyBtn.addEventListener('click', async () => {
    const url = shareCopyBtn.dataset.shareUrl;
    if (!url) return;
    try {
        await navigator.clipboard.writeText(url);
        shareCopiedMsg.classList.add('visible');
        setTimeout(() => shareCopiedMsg.classList.remove('visible'), 1500);
    } catch (err) {
        console.warn('Clipboard write failed:', err);
    }
});

// URL parameter auto-submit
(() => {
    const params = new URLSearchParams(window.location.search);
    const url = params.get('url');
    if (url) {
        urlInput.value = url;
        quickstartUsed = true;
        quickstartContainer.classList.add('hidden');
        urlForm.requestSubmit();
    }
})();
