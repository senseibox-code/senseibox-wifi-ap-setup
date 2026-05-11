const screens = new Map(
  Array.from(document.querySelectorAll("[data-screen]")).map((screen) => [screen.dataset.screen, screen]),
);
const continueButton = document.querySelector("#continue-button");
const form = document.querySelector("#wifi-form");
const message = document.querySelector("#message");
const networkCard = document.querySelector(".network-card");
const networkHelper = document.querySelector("#network-helper");
const networkList = document.querySelector("#network-list");
const password = document.querySelector("#password");
const togglePassword = document.querySelector("#toggle-password");

let selectedSsid = "";

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
  networkCard.classList.toggle("network-card-empty", Boolean(text));
}

function networkSecurity(network) {
  return network.security && network.security !== "open" ? "locked" : "open";
}

function selectNetwork(name) {
  selectedSsid = name;
  for (const item of networkList.querySelectorAll("li")) {
    const isSelected = item.dataset.ssid === name;
    item.classList.toggle("network-selected", isSelected);
    const status = item.querySelector(".network-status");
    if (status) {
      status.innerHTML = "";
      const indicator = document.createElement("span");
      indicator.className = isSelected ? "selected-check" : "network-lock";
      indicator.hidden = !isSelected && item.dataset.security !== "locked";
      status.append(indicator);
    }
  }
}

function renderNetwork(network) {
  const item = document.createElement("li");
  const icon = document.createElement("span");
  const button = document.createElement("button");
  const status = document.createElement("span");
  const isSelected = network.ssid === selectedSsid;

  item.dataset.ssid = network.ssid;
  item.dataset.security = networkSecurity(network);
  item.className = isSelected ? "network-selected" : "";

  icon.className = "network-icon";

  button.className = "network-button";
  button.type = "button";
  button.textContent = network.ssid;
  button.addEventListener("click", () => selectNetwork(network.ssid));

  status.className = "network-status";
  const indicator = document.createElement("span");
  indicator.className = isSelected ? "selected-check" : "network-lock";
  indicator.hidden = !isSelected && networkSecurity(network) !== "locked";
  status.append(indicator);

  item.append(icon, button, status);
  return item;
}

function renderNetworkMessage(text) {
  networkList.innerHTML = "";
  setNetworkHelper(text);
}

async function loadNetworks() {
  renderNetworkMessage("Scanning networks...");
  try {
    const response = await fetch("/api/networks");
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Unable to scan networks.");
    }
    if (body.networks.length === 0) {
      renderNetworkMessage("No Wi-Fi networks found. Move closer to your router, then try again.");
      return;
    }
    selectedSsid = selectedSsid || body.networks[0].ssid;
    setNetworkHelper("");
    networkList.innerHTML = "";
    for (const network of body.networks.slice(0, 5)) {
      networkList.append(renderNetwork(network));
    }
  } catch (error) {
    renderNetworkMessage("Unable to scan Wi-Fi networks.");
    setMessage(error.message);
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
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector(".primary-action");
  if (!selectedSsid) {
    setMessage("Select a Wi-Fi network first.");
    return;
  }
  const payload = {
    ssid: selectedSsid,
    password: password.value,
  };

  button.disabled = true;
  setMessage("");
  showScreen("connecting");

  try {
    const response = await fetch("/api/wifi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Unable to connect to Wi-Fi.");
    }
    form.reset();
    showScreen("success");
  } catch (error) {
    showScreen("select");
    setMessage(error.message);
  } finally {
    button.disabled = false;
  }
});

loadNetworks();
