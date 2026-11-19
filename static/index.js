const createMessage = document.getElementById("create-message");
const importMessage = document.getElementById("import-message");
let selectedOffer = null;

const offerPicker = offerAutocomplete(document.getElementById("offer-picker"), (offer) => {
  selectedOffer = offer;
});

function fillSelect(select, items, preferredName) {
  select.innerHTML = items
    .map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`)
    .join("");
  const preferred = items.find((item) => item.name === preferredName);
  if (preferred) select.value = preferred.id;
}

async function loadOptions() {
  try {
    const [settings, options] = await Promise.all([
      api("GET", "/api/settings"),
      api("GET", "/api/keitaro/options"),
    ]);
    document.getElementById("prefix").textContent = settings.campaign_prefix;
    fillSelect(document.getElementById("domain"), options.domains);
    fillSelect(document.getElementById("group"), options.groups, "FORTESTS");
    fillSelect(document.getElementById("source"), options.traffic_sources, "FORTESTS");
  } catch (error) {
    showMessage(createMessage, `Could not load Keitaro settings: ${error.message}`, "error");
  }
}

async function loadCampaigns() {
  const campaigns = await api("GET", "/api/campaigns");
  const body = document.getElementById("campaigns");
  if (!campaigns.length) {
    body.innerHTML = '<tr><td colspan="3" class="muted">No campaigns yet</td></tr>';
    return;
  }
  body.innerHTML = campaigns
    .map(
      (campaign) => `
        <tr>
          <td><a href="/campaigns/${campaign.id}">${escapeHtml(campaign.name)}</a></td>
          <td>${campaign.keitaro_id}</td>
          <td><a class="icon-link" href="${campaign.keitaro_url}" target="_blank" rel="noopener">View in Keitaro ${icon("external")}</a></td>
        </tr>`
    )
    .join("");
}

document.getElementById("create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(createMessage);
  if (!selectedOffer) {
    showMessage(createMessage, "Pick an offer from the list", "error");
    return;
  }
  const button = document.getElementById("create-button");
  button.disabled = true;
  try {
    const campaign = await api("POST", "/api/campaigns", {
      name: document.getElementById("name").value,
      geo: document.getElementById("geo").value,
      offer_id: selectedOffer.id,
      domain_id: Number(document.getElementById("domain").value),
      group_id: Number(document.getElementById("group").value),
      traffic_source_id: Number(document.getElementById("source").value),
    });
    createMessage.className = "message success";
    createMessage.innerHTML = `Created <a href="/campaigns/${campaign.id}">${escapeHtml(campaign.name)}</a> (Keitaro ID ${campaign.keitaro_id})`;
    document.getElementById("name").value = "";
    document.getElementById("geo").value = "";
    offerPicker.reset();
    await loadCampaigns();
  } catch (error) {
    showMessage(createMessage, error.message, "error");
  } finally {
    button.disabled = false;
  }
});

document.getElementById("import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(importMessage);
  const button = document.getElementById("import-button");
  button.disabled = true;
  try {
    const campaign = await api("POST", "/api/campaigns/import", {
      keitaro_id: Number(document.getElementById("keitaro-id").value),
    });
    window.location.href = `/campaigns/${campaign.id}`;
  } catch (error) {
    showMessage(importMessage, error.message, "error");
    button.disabled = false;
  }
});

loadOptions();
loadCampaigns();
