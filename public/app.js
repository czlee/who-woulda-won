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

    // Build header row
    resultsHeader.innerHTML = '<th>Competitor</th>';
    data.results.forEach(result => {
        const th = document.createElement('th');
        th.textContent = result.system_name;
        resultsHeader.appendChild(th);
    });

    // Get all rankings by competitor
    const competitors = data.competitors;
    const rankings = buildRankingsMap(data.results, competitors);

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
        const allSame = placements.every(p => p === placements[0]);

        placements.forEach((placement, i) => {
            const td = document.createElement('td');
            td.textContent = formatPlacement(placement);

            // Highlight differences
            if (!allSame) {
                td.classList.add('different');
            }

            // Highlight winners
            if (placement === 1) {
                td.classList.add('winner');
            }

            tr.appendChild(td);
        });

        resultsBody.appendChild(tr);
    });

    showResults();
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
    if (n === null || n === undefined) return '-';

    const suffixes = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return n + (suffixes[(v - 20) % 10] || suffixes[v] || suffixes[0]);
}

// UI helpers
function showLoading() {
    loadingSection.classList.remove('hidden');
}

function hideLoading() {
    loadingSection.classList.add('hidden');
}

function showError(message) {
    errorMessage.textContent = message;
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
}
