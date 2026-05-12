const screens = new Map(
  Array.from(document.querySelectorAll("[data-screen]")).map((screen) => [screen.dataset.screen, screen]),
);
const continueButton = document.querySelector("#continue-button");
const form = document.querySelector("#wifi-form");
const message = document.querySelector("#message");
const networkHelper = document.querySelector("#network-helper");
const networkList = document.querySelector("#network-list");
const password = document.querySelector("#password");
const refreshAction = document.querySelector(".refresh-action");
const refreshNetworks = document.querySelector("#refresh-networks");
const togglePassword = document.querySelector("#toggle-password");
const connectButton = form.querySelector(".primary-action");

let selectedSsid = "";

const icons = {
  checkCircle: `
    <svg class="svg-icon selected-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  `,
  lock: `
    <svg class="svg-icon network-lock" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5.5" y="10" width="13" height="10" rx="2" />
      <path d="M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10" />
    </svg>
  `,
  wifi: `
    <svg class="svg-icon network-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 13.1a10.1 10.1 0 0 1 14 0" />
      <path d="M8.5 16.2a5.1 5.1 0 0 1 7 0" />
      <path d="M12 19.5h.01" />
    </svg>
  `,
  eye: `
    <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.1 12.35C3.48 7.94 7.58 5 12 5s8.52 2.94 9.9 7.35a1.3 1.3 0 0 1 0 .3C20.52 17.06 16.42 20 12 20s-8.52-2.94-9.9-7.35a1.3 1.3 0 0 1 0-.3Z" />
      <circle cx="12" cy="12.5" r="3" />
    </svg>
  `,
  eyeOff: `
    <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m3 3 18 18" />
      <path d="M10.6 10.8a3 3 0 0 0 4.1 4.1" />
      <path d="M9.5 5.4A10.1 10.1 0 0 1 12 5c4.42 0 8.52 2.94 9.9 7.35a1.3 1.3 0 0 1 0 .3 11.3 11.3 0 0 1-2 3.68" />
      <path d="M6.4 6.9a11.2 11.2 0 0 0-4.3 5.45 1.3 1.3 0 0 0 0 .3C3.48 17.06 7.58 20 12 20a10.2 10.2 0 0 0 5.1-1.36" />
    </svg>
  `,
};

function showScreen(name) {
  for (const [screenName, screen] of screens) {
    screen.classList.toggle("screen-active", screenName === name);
  }
}

function setMessage(text) {
  message.textContent = text;
}

function setNetworkHelper(text) {
  networkHelper.textContent = text;
}

function updateConnectState() {
  connectButton.disabled = !(selectedSsid && password.value.length > 0);
}

function setRefreshLoading(isLoading) {
  refreshNetworks.disabled = isLoading;
  refreshNetworks.classList.toggle("is-loading", isLoading);
  refreshNetworks.setAttribute("aria-label", isLoading ? "Refreshing networks" : "Refresh networks");
  if (isLoading) {
    refreshAction.setAttribute("role", "status");
    refreshAction.setAttribute("aria-label", "Refreshing networks");
  } else {
    refreshAction.removeAttribute("role");
    refreshAction.removeAttribute("aria-label");
  }
}

function networkSecurity(network) {
  return network.security && network.security !== "open" ? "locked" : "open";
}

function selectNetwork(name) {
  selectedSsid = name;
  for (const item of networkList.querySelectorAll("li")) {
    const isSelected = item.dataset.ssid === name;
    const option = item.querySelector(".network-option");
    const lockIcon = item.querySelector(".lock-icon");
    const tickIcon = item.querySelector(".tick-icon");
    if (option) {
      option.classList.toggle("is-selected", isSelected);
      option.setAttribute("aria-pressed", String(isSelected));
    }
    if (lockIcon) {
      lockIcon.hidden = isSelected || item.dataset.security !== "locked";
    }
    if (tickIcon) {
      tickIcon.hidden = !isSelected;
    }
  }
  updateConnectState();
}

function renderNetwork(network) {
  const item = document.createElement("li");
  const option = document.createElement("button");
  const main = document.createElement("span");
  const icon = document.createElement("span");
  const name = document.createElement("span");
  const lockIcon = document.createElement("span");
  const tickIcon = document.createElement("span");
  const isSelected = network.ssid === selectedSsid;

  item.dataset.ssid = network.ssid;
  item.dataset.security = networkSecurity(network);
  item.className = "network-list-item";

  option.className = "network-option";
  option.type = "button";
  option.setAttribute("aria-pressed", String(isSelected));
  if (isSelected) {
    option.classList.add("is-selected");
  }
  option.addEventListener("click", () => selectNetwork(network.ssid));

  main.className = "network-main";

  icon.className = "network-icon";
  icon.innerHTML = icons.wifi;

  name.className = "network-name";
  name.textContent = network.ssid;

  lockIcon.className = "status-icon lock-icon";
  lockIcon.innerHTML = icons.lock;
  lockIcon.hidden = isSelected || networkSecurity(network) !== "locked";

  tickIcon.className = "status-icon tick-icon";
  tickIcon.innerHTML = icons.checkCircle;
  tickIcon.hidden = !isSelected;

  main.append(icon, name);
  option.append(main, lockIcon, tickIcon);
  item.append(option);
  return item;
}

function renderNetworkMessage(text) {
  networkList.innerHTML = "";
  setNetworkHelper(text);
}

async function readJsonResponse(response) {
  try {
    return await response.json();
  } catch (_error) {
    return {};
  }
}

async function loadNetworks() {
  setRefreshLoading(true);
  networkList.setAttribute("aria-busy", "true");
  renderNetworkMessage("Scanning networks...");
  try {
    const response = await fetch("/api/networks");
    const body = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(body.error || "Unable to scan networks.");
    }
    if (body.networks.length === 0) {
      renderNetworkMessage("No Wi-Fi networks found. Move closer to your router, then try again.");
      return;
    }
    if (!body.networks.some((network) => network.ssid === selectedSsid)) {
      selectedSsid = "";
    }
    setNetworkHelper("");
    networkList.innerHTML = "";
    for (const network of body.networks) {
      networkList.append(renderNetwork(network));
    }
    updateConnectState();
  } catch (error) {
    renderNetworkMessage("Unable to scan Wi-Fi networks.");
    setMessage(error.message);
    selectedSsid = "";
    updateConnectState();
  } finally {
    setRefreshLoading(false);
    networkList.removeAttribute("aria-busy");
  }
}

continueButton.addEventListener("click", () => {
  showScreen("select");
});

for (const backButton of document.querySelectorAll("[data-back]")) {
  backButton.addEventListener("click", () => showScreen(backButton.dataset.back));
}

togglePassword.addEventListener("click", () => {
  const shouldShow = password.type === "password";
  password.type = shouldShow ? "text" : "password";
  togglePassword.setAttribute("aria-label", shouldShow ? "Hide password" : "Show password");
  togglePassword.innerHTML = shouldShow ? icons.eyeOff : icons.eye;
});

password.addEventListener("input", updateConnectState);

refreshNetworks.addEventListener("click", () => {
  setMessage("");
  loadNetworks();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedSsid) {
    setMessage("Select a Wi-Fi network first.");
    updateConnectState();
    return;
  }
  const payload = {
    ssid: selectedSsid,
    password: password.value,
  };

  connectButton.disabled = true;
  setMessage("");
  showScreen("connecting");

  try {
    const response = await fetch("/api/wifi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(body.error || "Unable to connect to Wi-Fi. Check the password and try again.");
    }
    form.reset();
    selectedSsid = "";
    updateConnectState();
    showScreen("success");
  } catch (error) {
    showScreen("select");
    setMessage(error.message);
  } finally {
    updateConnectState();
  }
});

loadNetworks();
