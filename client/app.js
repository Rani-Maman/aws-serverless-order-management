// API base URL: set this to your API Gateway invoke URL after deploying (see docs/DEPLOY.md).
const apiBase = "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod";

// === Tab switching ===
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

// === API helper ===
async function call(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(apiBase + path, opts);
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = text; }
  return { status: res.status, data };
}

// === Orders ===
document.getElementById("create-order-form").addEventListener("submit", async e => {
  e.preventDefault();
  const description = document.getElementById("o-description").value;
  const price = parseFloat(document.getElementById("o-price").value);
  await call("POST", "/orders", { description, price });
  e.target.reset();
  loadOrders();
});

document.getElementById("refresh-orders").addEventListener("click", loadOrders);

async function loadOrders() {
  const { data } = await call("GET", "/orders");
  const tbody = document.querySelector("#orders-table tbody");
  tbody.innerHTML = "";
  (data.orders || []).forEach(o => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${o.order_id}</td>
      <td>${o.description}</td>
      <td>${o.price}</td>
      <td>${o.creation_date}</td>
      <td>${o.last_modified}</td>
      <td><button class="del-btn" data-id="${o.order_id}">Delete</button></td>
    `;
    tbody.appendChild(tr);
  });
  document.querySelectorAll(".del-btn").forEach(btn => {
    btn.addEventListener("click", () => deleteOrder(btn.dataset.id));
  });
}

async function deleteOrder(id) {
  if (!confirm(`Delete order ${id}?`)) return;
  await call("DELETE", `/orders/${id}`);
  loadOrders();
}

document.getElementById("update-order-form").addEventListener("submit", async e => {
  e.preventDefault();
  const id = document.getElementById("u-id").value;
  const description = document.getElementById("u-description").value;
  const price = document.getElementById("u-price").value;
  const body = {};
  if (description) body.description = description;
  if (price) body.price = parseFloat(price);
  await call("PUT", `/orders/${id}`, body);
  e.target.reset();
  loadOrders();
});

// === Notifications ===
document.getElementById("subscribe-form").addEventListener("submit", async e => {
  e.preventDefault();
  const email = document.getElementById("sub-email").value;
  const { data } = await call("POST", "/subscriptions", { email });
  alert(data.message || "Subscribe request sent.");
  e.target.reset();
});

document.getElementById("unsubscribe-form").addEventListener("submit", async e => {
  e.preventDefault();
  const email = document.getElementById("unsub-email").value;
  const { data } = await call("DELETE", "/subscriptions", { email });
  alert(data.message || data.error || "Unsubscribe request sent.");
  e.target.reset();
});

// === PDF Report ===
document.getElementById("gen-pdf").addEventListener("click", async () => {
  const { data } = await call("GET", "/reports/deleted-pdf");
  const out = document.getElementById("pdf-result");
  if (data.url) {
    out.innerHTML = `<p>PDF generated from <b>${data.count}</b> deleted-order TXT files.</p>
      <a href="${data.url}" target="_blank">⬇ Download PDF</a>`;
  } else {
    out.textContent = data.error || "Failed to generate PDF.";
  }
});

// === Scheduled Reports (EventBridge freestyle) ===
const PAGE_SIZE = 10;
let scheduledReports = [];
let visibleCount = 0;

document.getElementById("refresh-scheduled").addEventListener("click", loadScheduled);
document.getElementById("show-more-scheduled").addEventListener("click", renderMoreScheduled);

async function loadScheduled() {
  const { data } = await call("GET", "/reports/scheduled");
  scheduledReports = data.reports || [];
  visibleCount = 0;
  document.querySelector("#scheduled-table tbody").innerHTML = "";
  renderMoreScheduled();
}

function renderMoreScheduled() {
  const tbody = document.querySelector("#scheduled-table tbody");
  const slice = scheduledReports.slice(visibleCount, visibleCount + PAGE_SIZE);
  slice.forEach(r => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.key}</td>
      <td>${r.last_modified}</td>
      <td>${(r.size_bytes / 1024).toFixed(1)} KB</td>
      <td><a href="${r.url}" target="_blank">Download</a></td>
    `;
    tbody.appendChild(tr);
  });
  visibleCount += slice.length;

  const moreBtn = document.getElementById("show-more-scheduled");
  const counter = document.getElementById("scheduled-counter");
  counter.textContent = `Showing ${visibleCount} of ${scheduledReports.length}`;
  moreBtn.style.display = visibleCount < scheduledReports.length ? "inline-block" : "none";
}

// Auto-load on first visit
loadOrders();
