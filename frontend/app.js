const API_BASE = '';
const TID = new URLSearchParams(window.location.search).get('tid') || 'demo';

function showView(name) {
  document.querySelectorAll('.view').forEach(v => {
    if (v.id === `view-${name}`) {
      v.classList.remove('hidden');
    } else {
      v.classList.add('hidden');
    }
  });
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) throw new Error('Request failed');
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

// Navigation
const navButtons = document.querySelectorAll('nav button');
navButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    const view = btn.dataset.view;
    showView(view);
    if (view === 'bracket') loadBracket();
    if (view === 'schedule') loadSchedule();
    if (view === 'nownext') loadNowNext();
    if (view === 'rules') loadRules();
  });
});

showView('register');

// Create team
const createForm = document.getElementById('create-team-form');
createForm.addEventListener('submit', async e => {
  e.preventDefault();
  const data = {
    team_name: createForm.team_name.value,
    players: [{ name: createForm.player1.value }, { name: createForm.player2.value }],
    captain_contact: createForm.contact.value
  };
  try {
    const json = await apiFetch(`/t/${TID}/teams`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    document.getElementById('register-result').textContent = JSON.stringify(json);
    createForm.reset();
  } catch (err) {
    document.getElementById('register-result').textContent = 'Error creating team';
  }
});

// Join team
const joinForm = document.getElementById('join-team-form');
joinForm.addEventListener('submit', async e => {
  e.preventDefault();
  const data = {
    team_code: joinForm.team_code.value,
    player: joinForm.player.value
  };
  try {
    const json = await apiFetch(`/t/${TID}/teams/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    document.getElementById('join-result').textContent = JSON.stringify(json);
    joinForm.reset();
  } catch (err) {
    document.getElementById('join-result').textContent = 'Error joining team';
  }
});

// Load bracket
async function loadBracket() {
  const el = document.getElementById('bracket-container');
  el.textContent = 'Loading...';
  try {
    const json = await apiFetch(`/t/${TID}/bracket`);
    el.textContent = JSON.stringify(json, null, 2);
  } catch (err) {
    el.textContent = 'Failed to load bracket';
  }
}

// Load schedule
async function loadSchedule() {
  const table = document.getElementById('schedule-table');
  table.innerHTML = '<tr><td>Loading...</td></tr>';
  try {
    const json = await apiFetch(`/t/${TID}/schedule`);
    const matches = json.matches || [];
    if (matches.length) {
      table.innerHTML = '<tr><th>Match</th><th>Court</th><th>Start</th></tr>';
      matches.forEach(m => {
        const row = document.createElement('tr');
        row.innerHTML = `<td>${m.matchId}</td><td>${m.court || ''}</td><td>${m.start_slot || ''}</td>`;
        table.appendChild(row);
      });
    } else {
      table.innerHTML = '<tr><td>No schedule data</td></tr>';
    }
  } catch (err) {
    table.innerHTML = '<tr><td>Failed to load schedule</td></tr>';
  }
}

// Load now/next
async function loadNowNext() {
  const el = document.getElementById('nownext-container');
  el.textContent = 'Loading...';
  try {
    const json = await apiFetch(`/t/${TID}/nownext`);
    el.textContent = JSON.stringify(json, null, 2);
  } catch (err) {
    el.textContent = 'Failed to load now/next';
  }
}

// Load rules
async function loadRules() {
  const el = document.getElementById('rules-container');
  el.textContent = 'Loading...';
  try {
    const text = await apiFetch(`/t/${TID}/rules`);
    el.innerHTML = text;
  } catch (err) {
    el.textContent = 'Failed to load rules';
  }
}

// Submit score
const scoreForm = document.getElementById('score-form');
scoreForm.addEventListener('submit', async e => {
  e.preventDefault();
  const data = { score: { a: parseInt(scoreForm.scoreA.value, 10), b: parseInt(scoreForm.scoreB.value, 10) } };
  try {
    const json = await apiFetch(`/t/${TID}/matches/${scoreForm.matchId.value}/score`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Event-PIN': scoreForm.pin.value
      },
      body: JSON.stringify(data)
    });
    document.getElementById('score-result').textContent = JSON.stringify(json);
    scoreForm.reset();
    loadBracket();
  } catch (err) {
    document.getElementById('score-result').textContent = 'Error submitting score';
  }
});
