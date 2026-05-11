const form = document.querySelector("#wifi-form");
const message = document.querySelector("#message");
const networkList = document.querySelector("#network-list");
const refreshNetworks = document.querySelector("#refresh-networks");

async function loadNetworks() {
  networkList.innerHTML = "<li>Scanning...</li>";
  try {
    const response = await fetch("/api/networks");
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Unable to scan networks.");
    }
    if (body.networks.length === 0) {
      networkList.innerHTML = "<li>No networks found.</li>";
      return;
    }
    networkList.innerHTML = "";
    for (const network of body.networks) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      const meta = document.createElement("span");
      button.type = "button";
      button.textContent = network.ssid;
      button.addEventListener("click", () => {
        form.ssid.value = network.ssid;
        form.password.focus();
      });
      meta.className = "network-meta";
      meta.textContent = `${network.signal ?? "?"}% ${network.security}`;
      item.append(button, meta);
      networkList.append(item);
    }
  } catch (error) {
    networkList.innerHTML = "";
    const item = document.createElement("li");
    item.textContent = error.message;
    networkList.append(item);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button");
  const payload = {
    ssid: form.ssid.value,
    password: form.password.value,
  };

  button.disabled = true;
  message.textContent = "Saving network...";

  try {
    const response = await fetch("/api/wifi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Unable to save network.");
    }
    message.textContent = "Network saved. Senseibox will use these settings on reconnect.";
    form.reset();
  } catch (error) {
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

refreshNetworks.addEventListener("click", loadNetworks);
loadNetworks();
