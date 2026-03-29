const userList = document.getElementById("userList");
const reportView = document.getElementById("reportView");
const metaText = document.getElementById("metaText");
const refreshButton = document.getElementById("refreshButton");
const humanReportButton = document.getElementById("humanReportButton");
const deleteUserButton = document.getElementById("deleteUserButton");

let selectedKey = null;
let selectedReportRef = null;

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function createUserItem(report) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "user-item";
  const key = report.username || report.user_id;
  if (key === selectedKey) {
    button.classList.add("active");
  }

  const statusClass = report.status === "ended" ? "ended" : "active";
  button.innerHTML = `
    <p class="user-id">${key}<span class="status-tag ${statusClass}">${report.status}</span></p>
    <p class="user-meta">Turns: ${report.turn_count} | Last seen: ${formatDate(report.last_seen)}</p>
  `;

  button.addEventListener("click", () => {
    selectedKey = key;
    selectedReportRef = report;
    renderUserList(window.__reportsCache || []);
    loadUserReport(report);
  });

  return button;
}

function renderUserList(reports) {
  userList.innerHTML = "";
  if (reports.length === 0) {
    userList.textContent = "No reports yet.";
    reportView.textContent = "Start a conversation on the chat site to generate a report.";
    return;
  }

  reports.forEach((report) => {
    userList.appendChild(createUserItem(report));
  });
}

async function loadReports() {
  const response = await fetch("/backend/api/reports");
  if (!response.ok) {
    throw new Error("Could not load reports.");
  }

  const data = await response.json();
  const reports = data.reports || [];
  window.__reportsCache = reports;
  metaText.textContent = `${data.count} users | Inactive ends in ${data.inactivity_minutes}m`;

  if (!selectedKey && reports.length > 0) {
    selectedKey = reports[0].username || reports[0].user_id;
    selectedReportRef = reports[0];
  }

  renderUserList(reports);

  if (selectedKey) {
    const selected = reports.find((item) => (item.username || item.user_id) === selectedKey);
    if (selected) {
      selectedReportRef = selected;
      await loadUserReport(selected);
    }
  }
}

async function loadUserReport(reportRef) {
  reportView.textContent = "Loading report...";
  const username = reportRef.username;
  const userId = reportRef.user_id;

  const endpoints = username
    ? {
        raw: `/backend/api/reports/username/${encodeURIComponent(username)}`,
        detailed: `/backend/api/reports/username/${encodeURIComponent(username)}/detailed`,
      }
    : {
        raw: `/backend/api/reports/${encodeURIComponent(userId)}`,
        detailed: `/backend/api/reports/${encodeURIComponent(userId)}/detailed`,
      };

  const [rawResponse, detailedResponse] = await Promise.all([
    fetch(endpoints.raw),
    fetch(endpoints.detailed),
  ]);

  if (!rawResponse.ok || !detailedResponse.ok) {
    reportView.textContent = "Could not load selected report.";
    return;
  }

  const raw = await rawResponse.json();
  const detailed = await detailedResponse.json();

  reportView.textContent = JSON.stringify(
    {
      username,
      longitudinal_conversation_report: raw,
      detailed_mental_health_progress_report: detailed.detailed_report,
    },
    null,
    2
  );
}

async function generateHumanReadableReport() {
  if (!selectedReportRef) {
    reportView.textContent = "Select a user first.";
    return;
  }

  if (!selectedReportRef.username) {
    reportView.textContent = "Human-readable Dedalus report requires a username-based record.";
    return;
  }

  reportView.textContent = "Generating human-readable report with Dedalus...";
  const response = await fetch(
    `/backend/api/reports/username/${encodeURIComponent(selectedReportRef.username)}/detailed/dedalus`,
    { method: "POST" }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    reportView.textContent = `Could not generate human-readable report: ${error.detail}`;
    return;
  }

  const data = await response.json();
  reportView.textContent = data.human_readable_report || "No report text returned.";
}

async function deleteSelectedUser() {
  if (!selectedReportRef) {
    reportView.textContent = "Select a user first.";
    return;
  }

  if (!selectedReportRef.username) {
    reportView.textContent = "Delete by username is available only for username-based records.";
    return;
  }

  const confirmed = window.confirm(
    `Delete user ${selectedReportRef.username} and all stored conversations/reports? This cannot be undone.`
  );
  if (!confirmed) {
    return;
  }

  const response = await fetch(
    `/backend/api/reports/username/${encodeURIComponent(selectedReportRef.username)}`,
    { method: "DELETE" }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    reportView.textContent = `Could not delete user: ${error.detail}`;
    return;
  }

  selectedKey = null;
  selectedReportRef = null;
  await refresh();
}

async function refresh() {
  try {
    await loadReports();
  } catch (error) {
    reportView.textContent = `Error: ${error.message}`;
  }
}

refreshButton.addEventListener("click", refresh);
humanReportButton.addEventListener("click", () => {
  generateHumanReadableReport().catch((error) => {
    reportView.textContent = `Error: ${error.message}`;
  });
});
deleteUserButton.addEventListener("click", () => {
  deleteSelectedUser().catch((error) => {
    reportView.textContent = `Error: ${error.message}`;
  });
});
refresh();
