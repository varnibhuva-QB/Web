const apiBase = "http://127.0.0.1:5000";
let sessionToken = null;
let currentUser = null;

function getAuthHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (sessionToken) {
        headers["Authorization"] = `Bearer ${sessionToken}`;
    }
    return headers;
}

function showMessage(message, isError = false) {
    const authMessage = document.getElementById('authMessage');
    if (!authMessage) return;
    authMessage.style.color = isError ? '#c53030' : '#2f855a';
    authMessage.innerText = message;
}

function setAppVisible(visible) {
    const authContainer = document.getElementById('authContainer');
    const mainApp = document.getElementById('mainApp');
    if (authContainer) authContainer.style.display = visible ? 'none' : 'block';
    if (mainApp) mainApp.style.display = visible ? 'block' : 'none';
}

function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connectionStatus');
    if (!statusEl) return;
    statusEl.className = connected ? 'status-badge status-online' : 'status-badge status-offline';
    statusEl.innerHTML = connected ? '<i class="fas fa-circle"></i> Connected' : '<i class="fas fa-circle"></i> Not Connected';
}

function logoutUser() {
    sessionToken = null;
    currentUser = null;
    showMessage('Logged out. Please sign in again.');
    setAppVisible(false);
    updateConnectionStatus(false);
}

async function loginUser() {
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value.trim();
    if (!email || !password) {
        showMessage('Please enter both email and password.', true);
        return;
    }

    showMessage('Logging in...');

    try {
        const response = await fetch(`${apiBase}/auth/login`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        if (!response.ok) {
            showMessage(data.error || data.message || 'Login failed.', true);
            return;
        }

        sessionToken = data.token;
        currentUser = { email: data.email || email, is_superadmin: data.is_superadmin };
        showMessage('Login successful! Loading dashboard...');
        setAppVisible(true);
        updateConnectionStatus(true);
        loadAdminStats();
    } catch (error) {
        showMessage(error.message || 'Login failed.', true);
    }
}

async function startScraping() {
    const source = document.getElementById('source').value;
    const sector = document.getElementById('sector').value;
    const city = document.getElementById('city').value;
    const dataAmount = parseInt(document.getElementById('dataAmount').value);
    const dbServer = document.getElementById('dbServer').value || 'ADMIN\\SQLEXPRESS';
    const dbName = document.getElementById('dbName').value || 'leads_db';

    if (!sector || !city || !dataAmount || !dbServer || !dbName) {
        alert('Please fill all fields');
        return;
    }

    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = 'Scraping in progress...';

    try {
        const response = await fetch(`${apiBase}/scrape`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({
                source: source,
                keyword: sector,
                location: city,
                max_results: dataAmount,
                db_server: dbServer,
                db_name: dbName
            })
        });

        const data = await response.json();

        if (data.error) {
            resultsDiv.innerHTML = '<strong style="color: red;">Error:</strong> ' + data.error;
            return;
        }

        const rows = data.data || [];
        if (!rows.length) {
            resultsDiv.innerHTML = '<h3>Scraping Results:</h3><p>No results found</p>';
            return;
        }

        let html = '<h3>Scraping Results</h3>';
        html += '<table><tr><th>Name</th><th>Address</th><th>Phone</th><th>Website</th></tr>';
        rows.forEach(row => {
            html += `<tr><td>${row.business_name || ''}</td><td>${row.address || ''}</td><td>${row.phone || ''}</td><td>${row.website ? `<a href="${row.website}" target="_blank">${row.website}</a>` : ''}</td></tr>`;
        });
        html += '</table>';
        resultsDiv.innerHTML = html;
    } catch (error) {
        resultsDiv.innerHTML = 'Error: ' + error.message;
    }
}

async function testDbConnection() {
    const dbStatusDiv = document.getElementById('dbStatus');
    const dbServer = document.getElementById('dbServer').value || 'ADMIN\\SQLEXPRESS';
    const dbName = document.getElementById('dbName').value || 'leads_db';
    dbStatusDiv.innerHTML = 'Testing DB connection...';

    try {
        const response = await fetch(`${apiBase}/db-test`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ db_server: dbServer, db_name: dbName })
        });
        const data = await response.json();
        if (response.ok) {
            dbStatusDiv.innerHTML = '<strong style="color: green;">DB connection OK</strong>';
        } else {
            dbStatusDiv.innerHTML = '<strong style="color: red;">DB connection failed:</strong> ' + data.message;
        }
    } catch (error) {
        dbStatusDiv.innerHTML = '<strong style="color: red;">DB connection error:</strong> ' + error.message;
    }
}

async function viewLeads() {
    const leadsDiv = document.getElementById('leads');
    const dbServer = document.getElementById('dbServer').value || 'ADMIN\\SQLEXPRESS';
    const dbName = document.getElementById('dbName').value || 'leads_db';
    leadsDiv.innerHTML = 'Loading leads...';

    try {
        const response = await fetch(`${apiBase}/leads?db_server=${encodeURIComponent(dbServer)}&db_name=${encodeURIComponent(dbName)}`, {
            headers: getAuthHeaders()
        });
        const leads = await response.json();

        if (!Array.isArray(leads) || leads.length === 0) {
            leadsDiv.innerHTML = '<h3>Stored Leads</h3><p>No leads found</p>';
            return;
        }

        let html = '<h3>Stored Leads</h3><table><tr><th>ID</th><th>Business Name</th><th>Phone</th><th>Address</th><th>Website</th><th>Source</th></tr>';
        leads.forEach(lead => {
            const website = lead.website || (lead.data && lead.data.website) || '';
            const websiteLink = website ? `<a href="${website}" target="_blank">${website}</a>` : '';
            html += `<tr><td>${lead.id}</td><td>${lead.business_name || ''}</td><td>${lead.phone || ''}</td><td>${lead.address || ''}</td><td>${websiteLink}</td><td>${lead.source || ''}</td></tr>`;
        });
        html += '</table>';
        leadsDiv.innerHTML = html;
    } catch (error) {
        leadsDiv.innerHTML = 'Error loading leads: ' + error.message;
    }
}

async function loadAdminStats() {
    const adminStatsDiv = document.getElementById('adminStats');
    if (!adminStatsDiv) {
        return;
    }

    adminStatsDiv.innerHTML = 'Loading admin stats...';
    try {
        const response = await fetch(`${apiBase}/admin/stats`, {
            headers: getAuthHeaders()
        });
        const stats = await response.json();

        if (!response.ok) {
            adminStatsDiv.innerHTML = '<strong style="color: red;">Unable to load admin stats.</strong>';
            return;
        }

        let html = '<h3>Admin Dashboard</h3>';
        html += `<p><strong>Total Users:</strong> ${stats.user_count || 0}</p>`;
        html += `<p><strong>Total Leads Scraped:</strong> ${stats.lead_count || 0}</p>`;
        html += `<p><strong>Total Scrape Events:</strong> ${stats.scrape_count || 0}</p>`;
        if (Array.isArray(stats.recent_activity) && stats.recent_activity.length) {
            html += '<h4>Recent Activity</h4><table><tr><th>User</th><th>Action</th><th>Count</th><th>When</th></tr>';
            stats.recent_activity.forEach(item => {
                html += `<tr><td>${item.user_email || item.user_id}</td><td>${item.action || ''}</td><td>${item.count || 0}</td><td>${item.last_activity || ''}</td></tr>`;
            });
            html += '</table>';
        }
        adminStatsDiv.innerHTML = html;
    } catch (error) {
        adminStatsDiv.innerHTML = '<strong style="color: red;">Admin stats error:</strong> ' + error.message;
    }
}

function exportTableToCSV(filename) {
    const table = document.querySelector('table');
    if (!table) return;

    const rows = Array.from(table.querySelectorAll('tr'));
    const csv = rows.map(row => {
        return Array.from(row.querySelectorAll('th, td')).map(cell => `"${cell.innerText.replace(/"/g, '""')}"`).join(',');
    }).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
}

function exportCsv() {
    exportTableToCSV('leads.csv');
}

function exportExcel() {
    exportTableToCSV('leads.csv');
}
