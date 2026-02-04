/**
 * Who Woulda Won? - Frontend JavaScript
 */

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

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        // Update active tab button
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Show corresponding tab content
        const tabId = btn.dataset.tab + '-tab';
        document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
    });
});

// URL form submission
urlForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

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
    results.forEach(result => {
        const th = document.createElement('th');
        th.textContent = result.system_name;
        resultsHeader.appendChild(th);
    });

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
                if (placement < rpPlacement) {
                    const arrow = document.createElement('span');
                    arrow.className = 'placement-up';
                    arrow.textContent = ' \u25B2';
                    td.appendChild(arrow);
                } else if (placement > rpPlacement) {
                    const arrow = document.createElement('span');
                    arrow.className = 'placement-down';
                    arrow.textContent = ' \u25BC';
                    td.appendChild(arrow);
                }
            }

            // Highlight winners
            if (placement === 1) {
                td.classList.add('winner');
            }

            tr.appendChild(td);
        });

        resultsBody.appendChild(tr);
    });

    // Render expandable detail blocks for each voting system
    renderVotingDetails(results, data);

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
 * Build a map of competitor -> [placement for each system]
 */
function buildRankingsMap(results, competitors) {
    const rankings = {};

    competitors.forEach(competitor => {
        rankings[competitor] = results.map(result => {
            const idx = result.final_ranking.indexOf(competitor);
            return idx >= 0 ? idx + 1 : null;
        });
    });

    return rankings;
}

/**
 * Format placement as ordinal (1st, 2nd, etc.)
 */
function formatPlacement(n) {
    if (n === null || n === undefined) return '\u2014';

    const suffixes = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return n + (suffixes[(v - 20) % 10] || suffixes[v] || suffixes[0]);
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

// ─── Voting system detail renderers ──────────────────────────────────

const SYSTEM_DESCRIPTIONS = {
    'Relative Placement':
        'The official WCS system. A competitor places when a majority of judges rank them at that place or better.',
    'Borda Count':
        'Points-based: 1st place = n\u22121 points, 2nd = n\u22122, \u2026, last = 0. Sum across all judges.',
    'Schulze Method':
        'A Condorcet method using beatpath strengths. Handles cyclic preferences gracefully.',
    'Sequential IRV':
        'Run Instant Runoff Voting repeatedly: find winner, remove them, repeat for 2nd place, etc.',
};

const SYSTEM_RENDERERS = {
    'Relative Placement': renderRPDetails,
    'Borda Count':        renderBordaDetails,
    'Schulze Method':     renderSchulzeDetails,
    'Sequential IRV':     renderIRVDetails,
};

/**
 * Render expandable detail blocks for each voting system.
 */
function renderVotingDetails(results, data) {
    votingDetailsContainer.innerHTML = '';
    const wrapper = document.createElement('div');
    wrapper.className = 'voting-details';

    for (const result of results) {
        const block = document.createElement('details');
        block.className = 'voting-detail-block';

        const summary = document.createElement('summary');
        summary.textContent = result.system_name;
        block.appendChild(summary);

        const content = document.createElement('div');
        content.className = 'detail-content';

        const desc = document.createElement('p');
        desc.className = 'detail-description';
        desc.textContent = SYSTEM_DESCRIPTIONS[result.system_name] || '';
        content.appendChild(desc);

        const renderer = SYSTEM_RENDERERS[result.system_name];
        if (renderer) {
            renderer(content, result, data);
        }

        block.appendChild(content);
        wrapper.appendChild(block);
    }

    votingDetailsContainer.appendChild(wrapper);
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
    const majority = details.majority_threshold;

    // Determine which cumulative cells to display
    const cellDisplay = buildRPCellDisplay(details, n);

    // Sort competitors by final ranking
    const sorted = [...result.final_ranking];

    const wrapper = document.createElement('div');
    wrapper.className = 'detail-table-wrapper';

    const table = document.createElement('table');
    table.className = 'detail-table';

    // Header row
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.appendChild(createTh('Competitor'));
    judges.forEach(j => headerRow.appendChild(createTh(j)));
    for (let p = 1; p <= n; p++) {
        const th = createTh('1\u2013' + p);
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

    // Majority threshold row
    const majRow = document.createElement('tr');
    const majLabel = document.createElement('td');
    majLabel.colSpan = 1 + judges.length;
    majLabel.style.textAlign = 'right';
    majLabel.style.fontStyle = 'italic';
    majLabel.style.color = '#888';
    majLabel.textContent = 'Majority';
    majRow.appendChild(majLabel);
    for (let p = 1; p <= n; p++) {
        const td = document.createElement('td');
        td.textContent = majority;
        td.style.fontStyle = 'italic';
        td.style.color = '#888';
        if (p === 1) td.classList.add('rp-separator');
        majRow.appendChild(td);
    }
    const majEmpty = document.createElement('td');
    majEmpty.classList.add('rp-result');
    majRow.appendChild(majEmpty);
    tbody.appendChild(majRow);

    // Competitor rows
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
            tr.appendChild(td);
        });

        // Cumulative count columns
        for (let p = 1; p <= n; p++) {
            const td = document.createElement('td');
            const key = competitor + '|' + p;
            const display = cellDisplay[key];

            if (display !== undefined) {
                if (typeof display === 'object' && display.quality !== undefined) {
                    td.innerHTML = escapeHtml(String(display.count))
                        + ' <span class="rp-quality">('
                        + escapeHtml(String(display.quality)) + ')</span>';
                } else {
                    td.textContent = display;
                }
            } else {
                td.textContent = '\u2014';
            }
            if (p === 1) td.classList.add('rp-separator');
            tr.appendChild(td);
        }

        // Result column
        const resultTd = document.createElement('td');
        resultTd.textContent = formatPlacement(idx + 1);
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
 * Walks cutoff_progression for each round. A cell is shown if that
 * competitor was examined at that cutoff. Quality-of-majority
 * tiebreaks show count (quality).
 *
 * @returns {Object} Map of "competitor|cutoff" -> number | {count, quality}
 */
function buildRPCellDisplay(details, n) {
    const display = {};
    const cumCounts = details.cumulative_counts;

    for (const round of details.rounds) {
        const progression = round.resolution.cutoff_progression;
        if (!progression) continue;

        for (const step of progression) {
            const cutoff = step.cutoff;
            const candidates = Object.keys(step.counts);

            for (const competitor of candidates) {
                const key = competitor + '|' + cutoff;
                const count = cumCounts[competitor][cutoff];

                if (step.quality_scores && step.quality_scores[competitor] !== undefined) {
                    display[key] = {
                        count: count,
                        quality: step.quality_scores[competitor],
                    };
                } else {
                    display[key] = count;
                }
            }
        }
    }

    return display;
}

// ─── Borda Count ─────────────────────────────────────────────────────

/**
 * Render the Borda Count working table.
 *
 * Columns: Competitor | J1 pts | J2 pts | \u2026 | Total
 */
function renderBordaDetails(container, result, data) {
    const details = result.details;
    const judges = data.judges;
    const sorted = [...result.final_ranking];

    const wrapper = document.createElement('div');
    wrapper.className = 'detail-table-wrapper';

    const table = document.createElement('table');
    table.className = 'detail-table';

    // Header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.appendChild(createTh('Competitor'));
    judges.forEach(j => headerRow.appendChild(createTh(j)));
    headerRow.appendChild(createTh('Total'));
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body
    const tbody = document.createElement('tbody');
    sorted.forEach(competitor => {
        const tr = document.createElement('tr');

        const nameTd = document.createElement('td');
        nameTd.textContent = competitor;
        tr.appendChild(nameTd);

        const breakdown = details.breakdowns[competitor];
        breakdown.points.forEach(pts => {
            const td = document.createElement('td');
            td.textContent = pts;
            tr.appendChild(td);
        });

        const totalTd = document.createElement('td');
        totalTd.textContent = details.scores[competitor];
        totalTd.style.fontWeight = '600';
        tr.appendChild(totalTd);

        tbody.appendChild(tr);
    });

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
    const competitors = result.final_ranking;

    // Pairwise Preferences
    const h4a = document.createElement('h4');
    h4a.textContent = 'Pairwise Preferences';
    container.appendChild(h4a);

    const pDesc = document.createElement('p');
    pDesc.className = 'detail-description';
    pDesc.textContent = 'Cell (row, column) = number of judges who prefer row over column.';
    container.appendChild(pDesc);

    container.appendChild(
        buildSchulzeMatrix(competitors, details.pairwise_preferences, null)
    );

    // Strongest Path Strengths
    const h4b = document.createElement('h4');
    h4b.textContent = 'Strongest Path Strengths';
    container.appendChild(h4b);

    const sDesc = document.createElement('p');
    sDesc.className = 'detail-description';
    sDesc.textContent = 'Cell (row, column) = strength of strongest path from row to column. Rightmost column = number of Schulze wins.';
    container.appendChild(sDesc);

    container.appendChild(
        buildSchulzeMatrix(competitors, details.path_strengths, details.schulze_wins)
    );
}

/**
 * Build a Schulze matrix table (pairwise or path strengths).
 * Cells are coloured green (row beats column) or red (column beats row).
 */
function buildSchulzeMatrix(competitors, matrix, winsCol) {
    const wrapper = document.createElement('div');
    wrapper.className = 'detail-table-wrapper';

    const table = document.createElement('table');
    table.className = 'detail-table';

    // Header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.appendChild(createTh(''));
    competitors.forEach(c => headerRow.appendChild(createTh(c)));
    if (winsCol) {
        const winsTh = createTh('Wins');
        winsTh.classList.add('schulze-wins-col');
        headerRow.appendChild(winsTh);
    }
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body
    const tbody = document.createElement('tbody');
    competitors.forEach(rowComp => {
        const tr = document.createElement('tr');

        const labelTd = document.createElement('td');
        labelTd.textContent = rowComp;
        tr.appendChild(labelTd);

        competitors.forEach(colComp => {
            const td = document.createElement('td');
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

        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
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

    // Ballot reference table
    const ballotH4 = document.createElement('h4');
    ballotH4.textContent = 'Judge Ballots';
    container.appendChild(ballotH4);

    container.appendChild(buildBallotTable(judges, rankings, competitors));

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
            p.innerHTML = '<span class="irv-winner">'
                + escapeHtml(winner)
                + '</span> \u2014 last remaining competitor.';
            roundDiv.appendChild(p);
        } else {
            renderIRVRounds(roundDiv, placementRound);
        }

        container.appendChild(roundDiv);
    }
}

/**
 * Build the ballot reference table for IRV.
 * Rows = rank positions, Columns = judges, Cells = competitor at that rank.
 */
function buildBallotTable(judges, rankings, competitors) {
    const wrapper = document.createElement('div');
    wrapper.className = 'detail-table-wrapper';

    const table = document.createElement('table');
    table.className = 'detail-table';

    // Header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.appendChild(createTh('Rank'));
    judges.forEach(j => headerRow.appendChild(createTh(j)));
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Invert rankings: for each judge, build position -> competitor
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
            td.textContent = ballots[judge][rank] || '\u2014';
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    }

    table.appendChild(tbody);
    wrapper.appendChild(table);
    return wrapper;
}

/**
 * Render IRV elimination rounds for one placement position.
 */
function renderIRVRounds(container, placementRound) {
    for (const round of placementRound.irv_rounds) {
        const step = document.createElement('p');
        step.className = 'irv-round-step';

        // Build vote count string sorted descending
        const voteParts = Object.entries(round.votes)
            .sort((a, b) => b[1] - a[1])
            .map(([comp, count]) => escapeHtml(comp) + ': ' + count);
        const voteStr = voteParts.join(', ');

        if (round.winner) {
            const winnerStr = Array.isArray(round.winner)
                ? round.winner.map(escapeHtml).join(', ')
                : escapeHtml(round.winner);
            step.innerHTML = 'Round ' + round.round + ' \u2014 '
                + voteStr + ' \u2014 '
                + '<span class="irv-winner">' + winnerStr
                + ' wins</span> (majority: ' + round.majority_needed + ').';
        } else if (round.eliminated) {
            step.innerHTML = 'Round ' + round.round + ' \u2014 '
                + voteStr + ' \u2014 '
                + '<span class="irv-eliminated">'
                + escapeHtml(round.eliminated)
                + ' eliminated</span> (fewest votes).';
        }

        container.appendChild(step);
    }
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
    votingDetailsContainer.innerHTML = '';
}
