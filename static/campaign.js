const campaignId = Number(window.location.pathname.split("/").filter(Boolean).pop());
const pageMessage = document.getElementById("page-message");
const streamsContainer = document.getElementById("streams");
const statsNote = document.getElementById("stats-note");
let campaign = null;
let stats = null;
let allOffers = null;

function renderCampaign() {
  document.title = `${campaign.name} streams`;
  document.getElementById("title").textContent = campaign.name;
  document.getElementById("crumb").textContent = campaign.name;
  document.getElementById("keitaro-link").href = campaign.keitaro_url;
  streamsContainer.innerHTML = "";
  if (!campaign.streams.length) {
    streamsContainer.innerHTML = '<p class="muted">This campaign has no streams.</p>';
  }
  campaign.streams.forEach((stream) => streamsContainer.append(renderStream(stream)));
  renderAllOffers();
}

function replaceStream(updated) {
  const index = campaign.streams.findIndex((stream) => stream.id === updated.id);
  campaign.streams[index] = updated;
  const oldNode = streamsContainer.querySelector(`[data-stream-id="${updated.id}"]`);
  oldNode.replaceWith(renderStream(updated));
  renderAllOffers();
}

async function streamAction(button, request) {
  clearMessage(pageMessage);
  button.disabled = true;
  try {
    replaceStream(await request());
  } catch (error) {
    showMessage(pageMessage, error.message, "error");
    button.disabled = false;
  }
}

function offerBadge(offer) {
  if (offer.published_state === null) return '<span class="badge new">new</span>';
  if (offer.state === "removed" && offer.published_state === "active") return '<span class="badge changed">will be removed</span>';
  if (offer.state === "active" && offer.published_state === "removed") return '<span class="badge changed">will be restored</span>';
  if (offer.state === "removed") return '<span class="badge">removed</span>';
  if (offer.dirty) return `<span class="badge changed">was ${offer.published_share}%</span>`;
  return "";
}

function offerIdLabel(offer) {
  return offer.name.includes(String(offer.offer_id)) ? "" : `<span class="muted">#${offer.offer_id}</span>`;
}

function previewLink(url) {
  return url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">(preview)</a>` : "";
}

function offerStats(stream, offerId) {
  if (!stats) return null;
  return stats.offers[`${stream.keitaro_id}:${offerId}`] || { clicks: 0, conversions: 0, revenue: 0, daily_clicks: stats.days.map(() => 0) };
}

function statsCell(entry) {
  if (!entry) return '<span class="muted">—</span>';
  return `
    <div class="stats">
      <span><b>${entry.clicks}</b> clicks</span>
      <span><b>${entry.conversions}</b> conv.</span>
      <span><b>$${entry.revenue.toFixed(2)}</b> revenue</span>
    </div>`;
}

function trendCell(entry) {
  if (!entry) return '<span class="muted">—</span>';
  const values = entry.daily_clicks;
  const max = Math.max(...values, 1);
  const barWidth = 10;
  const gap = 3;
  const height = 28;
  const bars = values
    .map((value, index) => {
      const barHeight = value === 0 ? 1 : Math.max(3, Math.round((value / max) * height));
      const x = index * (barWidth + gap);
      return `<rect x="${x}" y="${height - barHeight}" width="${barWidth}" height="${barHeight}" rx="1"><title>${stats.days[index]}: ${value} clicks</title></rect>`;
    })
    .join("");
  const width = values.length * (barWidth + gap) - gap;
  return `<svg class="trend" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="Clicks for the last ${values.length} days">${bars}</svg>`;
}

function renderOfferRow(stream, offer) {
  const row = document.createElement("tr");
  const isActive = offer.state === "active";
  row.className = [isActive ? "" : "removed", offer.dirty ? "pending" : ""].join(" ").trim();
  const entry = offerStats(stream, offer.offer_id);
  row.innerHTML = `
    <td>${escapeHtml(offer.name)} ${offerIdLabel(offer)} ${previewLink(offer.preview_url)} ${offerBadge(offer)}</td>
    <td class="nowrap">
      <button class="share" ${isActive ? "" : "disabled"} title="Click to set and pin a share">${offer.share}%</button>
      <button class="pin ${offer.pinned ? "on" : ""}" ${isActive ? "" : "disabled"} title="${offer.pinned ? "Unpin share" : "Pin share"}">📌</button>
    </td>
    <td>${statsCell(entry)}</td>
    <td>${trendCell(entry)}</td>
    <td class="actions"></td>`;

  const actionButton = document.createElement("button");
  actionButton.className = "small" + (isActive ? " danger" : "");
  setButton(actionButton, isActive ? "trash" : "undo", isActive ? "Remove" : "Bring back");
  const action = isActive ? "remove" : "bring-back";
  actionButton.addEventListener("click", () =>
    streamAction(actionButton, () => api("POST", `/api/streams/${stream.id}/offers/${offer.offer_id}/${action}`))
  );
  row.querySelector(".actions").append(actionButton);

  const pinButton = row.querySelector(".pin");
  pinButton.addEventListener("click", () =>
    streamAction(pinButton, () =>
      api("POST", `/api/streams/${stream.id}/offers/${offer.offer_id}/pin`, { pinned: !offer.pinned })
    )
  );

  const shareButton = row.querySelector(".share");
  shareButton.addEventListener("click", () => editShare(stream, offer, shareButton));
  return row;
}

function editShare(stream, offer, shareButton) {
  const input = document.createElement("input");
  input.type = "number";
  input.min = "0";
  input.max = "100";
  input.value = offer.share;
  input.className = "share-input";
  shareButton.replaceWith(input);
  input.focus();
  input.select();

  let finished = false;
  async function finish(save) {
    if (finished) return;
    finished = true;
    const value = Number(input.value);
    if (!save || input.value === "" || value === offer.share) {
      input.replaceWith(shareButton);
      return;
    }
    clearMessage(pageMessage);
    try {
      replaceStream(
        await api("POST", `/api/streams/${stream.id}/offers/${offer.offer_id}/pin`, { pinned: true, share: value })
      );
    } catch (error) {
      showMessage(pageMessage, error.message, "error");
      input.replaceWith(shareButton);
    }
  }

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") finish(true);
    if (event.key === "Escape") finish(false);
  });
  input.addEventListener("blur", () => finish(true));
}

function clicksToday(stream) {
  if (!stats) return "";
  const entry = stats.streams[String(stream.keitaro_id)];
  return `, clicks today: ${entry ? entry.clicks_today : 0}`;
}

function renderStream(stream) {
  const node = document.createElement("section");
  node.className = "stream" + (stream.dirty ? " dirty" : "");
  node.dataset.streamId = stream.id;

  const head = document.createElement("div");
  head.className = "stream-head";
  head.innerHTML = `
    <div>
      <strong>Stream: ${escapeHtml(stream.name)}</strong> <span class="muted">(#${stream.position})</span>
      <span class="meta">stream_id ${stream.keitaro_id}${clicksToday(stream)}</span>
      ${stream.dirty ? '<span class="badge changed">not published</span>' : ""}
    </div>
    <div class="toolbar" style="margin:0"></div>`;
  node.append(head);

  if (!stream.has_offers) {
    const empty = document.createElement("div");
    empty.className = "stream-empty";
    empty.textContent = "Stream without offers. The wrapper does not manage its settings.";
    node.append(empty);
    return node;
  }

  const buttons = head.querySelector(".toolbar");
  const publishButton = document.createElement("button");
  publishButton.className = "primary small";
  setButton(publishButton, "upload", "Push to KT");
  publishButton.disabled = !stream.dirty;
  publishButton.addEventListener("click", () =>
    streamAction(publishButton, () => api("POST", `/api/streams/${stream.id}/publish`))
  );
  const cancelButton = document.createElement("button");
  cancelButton.className = "small";
  setButton(cancelButton, "close", "Cancel");
  cancelButton.disabled = !stream.dirty;
  cancelButton.addEventListener("click", () =>
    streamAction(cancelButton, () => api("POST", `/api/streams/${stream.id}/cancel`))
  );
  buttons.append(publishButton, cancelButton);

  const table = document.createElement("table");
  table.className = "offers-table";
  table.innerHTML =
    "<thead><tr><th>Offer</th><th>Share</th><th>Stats (7 days)</th><th>Trends</th><th>Actions</th></tr></thead>";
  const body = document.createElement("tbody");
  stream.offers.forEach((offer) => body.append(renderOfferRow(stream, offer)));
  const totalRow = document.createElement("tr");
  const totalClass = stream.total_share === 100 ? "total" : "total bad";
  totalRow.innerHTML = `<td class="muted">Total of active offers</td><td class="${totalClass}">${stream.total_share}%</td><td></td><td></td><td></td>`;
  body.append(totalRow);
  table.append(body);
  const scroller = document.createElement("div");
  scroller.className = "table-scroll";
  scroller.append(table);
  node.append(scroller);

  const addRow = document.createElement("div");
  addRow.className = "add-row";
  const pickerHolder = document.createElement("div");
  const addButton = document.createElement("button");
  setButton(addButton, "plus", "Add");
  addButton.disabled = true;
  let picked = null;
  offerAutocomplete(pickerHolder, (offer) => {
    picked = offer;
    addButton.disabled = !offer;
  });
  addButton.addEventListener("click", () =>
    streamAction(addButton, () => api("POST", `/api/streams/${stream.id}/offers`, { offer_id: picked.id }))
  );
  addRow.append(pickerHolder, addButton);
  node.append(addRow);
  return node;
}

function offerUsage(offerId) {
  if (!campaign) return "";
  return campaign.streams
    .flatMap((stream) =>
      stream.offers
        .filter((offer) => offer.offer_id === offerId)
        .map((offer) => `${escapeHtml(stream.name)}: ${offer.state === "active" ? `${offer.share}%` : "removed"}`)
    )
    .join("<br>");
}

function renderAllOffers() {
  if (!allOffers) return;
  const query = document.getElementById("all-offers-filter").value.trim().toLowerCase();
  const rows = allOffers.filter(
    (offer) => !query || String(offer.id).includes(query) || offer.name.toLowerCase().includes(query)
  );
  const body = document.getElementById("all-offers-body");
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="4" class="muted">No offers found</td></tr>';
    return;
  }
  body.innerHTML = rows
    .map(
      (offer) => `
        <tr>
          <td>${offer.id}</td>
          <td>${escapeHtml(offer.name)} ${previewLink(offer.preview_url)}</td>
          <td>${escapeHtml(offer.country.join(", ")) || '<span class="muted">—</span>'}</td>
          <td>${offerUsage(offer.id) || '<span class="muted">not used</span>'}</td>
        </tr>`
    )
    .join("");
}

document.getElementById("all-offers-button").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const panel = document.getElementById("all-offers");
  if (!panel.hidden) {
    panel.hidden = true;
    setButton(button, "list", "Show all offers");
    return;
  }
  button.disabled = true;
  try {
    if (!allOffers) allOffers = await api("GET", "/api/offers/all");
    panel.hidden = false;
    setButton(button, "close", "Hide all offers");
    renderAllOffers();
  } catch (error) {
    showMessage(pageMessage, error.message, "error");
  } finally {
    button.disabled = false;
  }
});

document.getElementById("all-offers-filter").addEventListener("input", renderAllOffers);

async function loadStats() {
  statsNote.textContent = "Loading stats from Keitaro…";
  try {
    stats = await api("GET", `/api/campaigns/${campaignId}/stats`);
    statsNote.textContent = `Stats for ${stats.days[0]} – ${stats.days[stats.days.length - 1]}, updated ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    stats = null;
    statsNote.textContent = `Stats are unavailable: ${error.message}`;
  }
  if (campaign) renderCampaign();
}

async function loadCampaign() {
  try {
    campaign = await api("GET", `/api/campaigns/${campaignId}`);
    renderCampaign();
    loadStats();
  } catch (error) {
    document.getElementById("title").textContent = "Campaign not found";
    showMessage(pageMessage, error.message, "error");
  }
}

document.getElementById("fetch-button").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const hasChanges = campaign && campaign.streams.some((stream) => stream.dirty);
  if (hasChanges && !confirm("Unpublished changes will be replaced with the current state from Keitaro. Continue?")) {
    return;
  }
  clearMessage(pageMessage);
  button.disabled = true;
  try {
    campaign = await api("POST", `/api/campaigns/${campaignId}/fetch`);
    renderCampaign();
    showMessage(pageMessage, "Streams fetched from Keitaro", "success");
    loadStats();
  } catch (error) {
    showMessage(pageMessage, error.message, "error");
  } finally {
    button.disabled = false;
  }
});

loadCampaign();
