const ICONS = {
  download: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>',
  upload: '<path d="M12 21V9"/><path d="m7 14 5-5 5 5"/><path d="M5 3h14"/>',
  external: '<path d="M14 4h6v6"/><path d="M10 14 20 4"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
  list: '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
  trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>',
  undo: '<path d="M3 7v6h6"/><path d="M3 13a9 9 0 1 0 3-7.7L3 8"/>',
  close: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  login: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/>',
};

function icon(name) {
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
}

function setButton(button, iconName, text) {
  button.innerHTML = `${icon(iconName)}<span>${escapeHtml(text)}</span>`;
}

document.querySelectorAll("button[data-icon]").forEach((button) => {
  setButton(button, button.dataset.icon, button.textContent.trim());
});

async function api(method, url, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(formatError(data) || `Request failed with HTTP ${response.status}`);
  }
  return data;
}

function formatError(data) {
  if (!data || !data.detail) return "";
  if (typeof data.detail === "string") return data.detail;
  return data.detail.map((item) => `${item.loc.slice(1).join(".")}: ${item.msg}`).join("; ");
}

function showMessage(element, text, kind) {
  element.textContent = text;
  element.className = `message ${kind}`;
}

function clearMessage(element) {
  element.textContent = "";
  element.className = "message";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function offerAutocomplete(container, onSelect) {
  container.classList.add("autocomplete");
  const combo = document.createElement("div");
  combo.className = "combo";
  const input = document.createElement("input");
  input.placeholder = "Type to search or pick from the list";
  input.autocomplete = "off";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "combo-toggle";
  toggle.title = "Show offers";
  toggle.textContent = "▾";
  combo.append(input, toggle);
  const list = document.createElement("ul");
  list.hidden = true;
  container.append(combo, list);

  let selected = null;
  let timer = null;
  let items = [];
  let activeIndex = -1;
  let requestId = 0;

  function label(item) {
    return item.name.includes(String(item.id)) ? item.name : `${item.id} ${item.name}`;
  }

  function choose(item) {
    selected = item;
    input.value = label(item);
    list.hidden = true;
    onSelect(item);
  }

  function render() {
    list.innerHTML = "";
    if (!items.length) {
      list.innerHTML = '<li class="empty">Nothing found</li>';
    }
    items.forEach((item, index) => {
      const li = document.createElement("li");
      li.textContent = label(item);
      li.className = index === activeIndex ? "active" : "";
      li.addEventListener("mousedown", (event) => {
        event.preventDefault();
        choose(item);
      });
      list.append(li);
    });
    open();
  }

  function open() {
    list.hidden = false;
    list.classList.remove("up");
    const box = combo.getBoundingClientRect();
    const spaceBelow = window.innerHeight - box.bottom;
    const spaceAbove = box.top;
    if (list.offsetHeight > spaceBelow && spaceAbove > spaceBelow) {
      list.classList.add("up");
    }
  }

  async function search(query = input.value.trim()) {
    const currentId = ++requestId;
    try {
      const result = await api("GET", `/api/offers?q=${encodeURIComponent(query)}`);
      if (currentId !== requestId) return;
      items = result;
      activeIndex = -1;
      render();
    } catch (error) {
      if (currentId !== requestId) return;
      list.innerHTML = `<li class="empty">${escapeHtml(error.message)}</li>`;
      open();
    }
  }

  toggle.addEventListener("mousedown", (event) => event.preventDefault());
  toggle.addEventListener("click", () => {
    if (!list.hidden) {
      list.hidden = true;
      return;
    }
    input.focus();
    search(selected ? "" : input.value.trim());
  });

  input.addEventListener("input", () => {
    selected = null;
    onSelect(null);
    clearTimeout(timer);
    timer = setTimeout(search, 250);
  });
  input.addEventListener("focus", () => {
    if (!selected) search();
  });
  input.addEventListener("blur", () => {
    list.hidden = true;
  });
  input.addEventListener("keydown", (event) => {
    if (list.hidden || !items.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      activeIndex = (activeIndex + step + items.length) % items.length;
      render();
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      choose(items[activeIndex]);
    } else if (event.key === "Escape") {
      list.hidden = true;
    }
  });

  return {
    reset() {
      selected = null;
      input.value = "";
      onSelect(null);
    },
  };
}
