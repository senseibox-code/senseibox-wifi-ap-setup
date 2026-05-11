const form = document.querySelector("#wifi-form");
const message = document.querySelector("#message");

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
