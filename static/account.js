const credentials = document.querySelector("#credentials");
const dialog = document.querySelector("#dialog");
const changes = new BroadcastChannel("polyglotta-account");

export function sessionChanged() {
  document.body.classList.add("signed-out");
  dialog.close();
  document.querySelector("#main").replaceChildren();
  location.reload();
}

changes.onmessage = sessionChanged;
window.addEventListener("pageshow", event => {
  if (event.persisted) sessionChanged();
});

async function accountRequest(path, method, body) {
  const response = await fetch("/api/" + path, {
    method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)
  });
  if (response.status === 401 && path === "auth/me") return null;
  if (response.status === 401 && path === "account") sessionChanged();
  if (!response.ok) throw Error((await response.json()).detail);
  return response.status === 204 ? null : response.json();
}

function completed() {
  changes.postMessage("changed");
  sessionChanged();
}

function bindForm(form, submit) {
  form.onsubmit = async event => {
    event.preventDefault();
    const button = event.submitter;
    if (button.disabled) return;
    button.disabled = true;
    try {
      await submit(Object.fromEntries(new FormData(form)));
      completed();
    } catch (error) {
      form.querySelector(".error").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
}

const closeButton = '<button type="button" class="settings-close" data-close aria-label="Close">×</button>';
const backButton = '<button type="button" class="settings-back">← Back to account</button>';
let profile;

function settingsPanel(title, content, backTo) {
  const panel = document.createElement("section");
  panel.className = "settings-panel";
  panel.innerHTML = `<div class="settings-tools">${backTo ? backButton : ""}${closeButton}</div>
    <h2 id="modalTitle" tabindex="-1">${title}</h2>${content}`;
  const body = document.querySelector("#dialogBody");
  body.replaceChildren(panel);
  dialog.setAttribute("aria-labelledby", "modalTitle");
  if (!dialog.open) dialog.showModal();
  panel.querySelector("h2").focus();
  if (backTo) panel.querySelector(".settings-back").onclick = () => {
    showSettings();
    document.querySelector(backTo).focus();
  };
  return panel;
}

export async function showAnkiSettings() {
  const panel = settingsPanel("Anki sync", `
    <p class="settings-status" role="status">Loading…</p>
    <form hidden>
      <label>Anki username<input name="username" autocomplete="username" pattern="[A-Za-z0-9_\\-]{1,64}" maxlength="64" required aria-describedby="username-hint"></label>
      <small id="username-hint">Use letters, digits, underscores or hyphens. Names like p123 are reserved.</small>
      <label>Anki password<input name="password" type="password" minlength="15" maxlength="128" autocomplete="new-password" required aria-describedby="password-hint"></label>
      <small id="password-hint">Use 15 to 128 characters.</small>
      <button class="primary">Connect</button>
    </form>
    <div class="connection-details" hidden><dl><dt>Server URL</dt><dd></dd><dt>Username</dt><dd></dd></dl>
      <h3>First sync</h3><ol><li>Back up the device with your complete collection. Enter the custom server URL and your Anki credentials, then choose <strong>Upload</strong>.</li>
      <li>On each additional device, enter the same connection details and choose <strong>Download</strong>.</li></ol></div>
    <p class="error" role="alert"></p>`, "#anki-settings");
  const status = panel.querySelector('[role="status"]');
  const details = panel.querySelector(".connection-details");
  const form = panel.querySelector("form");
  const connect = panel.querySelector(".primary");
  const errorText = panel.querySelector(".error");

  function render(info, justConnected = false) {
    form.hidden = info.linked || !info.endpoint;
    if (!info.linked) {
      status.textContent = info.endpoint ? "Connect your profile to hosted Anki sync." : "Anki sync is unavailable on this host.";
      return;
    }
    form.reset();
    const guidance = justConnected ? "Use your chosen Anki username and password to sync." : "If you lost your sync password, ask the host operator to rotate it.";
    status.textContent = [guidance, info.message].filter(Boolean).join(" ");
    if (justConnected) {
      dialog.addEventListener("close", () => dialog.dispatchEvent(new Event("anki-connected")), {once: true});
      panel.querySelector("h2").focus();
    }
    details.hidden = false;
    const [endpoint, username] = details.querySelectorAll("dd");
    endpoint.textContent = info.endpoint || "Ask the operator for the server URL.";
    username.textContent = info.username;

  }

  dialog.addEventListener("close", () => panel.remove(), {once: true});
  try {
    render(await accountRequest("anki", "GET"));
  } catch (error) {
    status.textContent = "";
    errorText.textContent = error.message;
  }
  form.onsubmit = async event => {
    event.preventDefault();
    if (connect.disabled) return;
    connect.disabled = true;
    errorText.textContent = "";
    try {
      render({...await accountRequest("anki/connect", "POST", Object.fromEntries(new FormData(form))), linked: true}, true);
    } catch (error) {
      errorText.textContent = error.message;
      try {
        const info = await accountRequest("anki", "GET");
        render(info);
        if (info.linked) errorText.textContent = "";
      } catch {
        status.textContent = "Reopen Anki settings to check your connection.";
      }
    } finally {
      connect.disabled = false;
    }
  };
}

function showSettings() {
  const body = settingsPanel("Account settings", `
    <div class="settings-identity"><span class="avatar" aria-hidden="true"></span><strong></strong></div>
    <button id="anki-settings" class="settings-row"><span>Anki sync</span><span aria-hidden="true">→</span></button>
    <button id="logout">Sign out</button>
    <div class="delete-row"><button id="delete-profile">Delete account…</button></div>
    <p class="error" role="alert"></p>`);
  body.querySelector(".avatar").textContent = profile.username[0].toUpperCase();
  body.querySelector(".settings-identity strong").textContent = profile.username;
  body.querySelector("#anki-settings").onclick = showAnkiSettings;
  body.querySelector("#logout").onclick = async () => {
    try {
      await accountRequest("auth/logout", "POST");
      completed();
    } catch (error) {
      body.querySelector(".error").textContent = error.message;
    }
  };
  body.querySelector("#delete-profile").onclick = () => {
    const confirmation = settingsPanel('Delete your account?', '<p>This permanently deletes your account, languages, history and cards from the live journal and signs out every device. Hosted Anki data will be removed. Downloaded device copies remain on your devices. Backup copies expire according to the host’s retention policy.</p><form><label>Current password<input type="password" name="password" required autocomplete="current-password"></label><p class="error" role="alert"></p><button class="danger">Permanently delete account</button></form>', "#delete-profile");
    bindForm(confirmation.querySelector("form"), data => accountRequest("account", "DELETE", data));
  };
}

export async function initializeAccount() {
  let registering = false;
  const toggle = document.querySelector("#auth-switch");
  toggle.onclick = () => {
    registering = !registering;
    const label = registering ? "Create account" : "Sign in";
    document.querySelector("#auth-title").textContent = label;
    credentials.querySelector(".primary").textContent = label;
    toggle.textContent = registering ? "Back to sign in" : "Create account";
    document.querySelector("#policy").hidden = !registering;
    credentials.password.value = "";
    credentials.password.autocomplete = registering ? "new-password" : "current-password";
    credentials.querySelector(".error").textContent = "";
  };
  bindForm(credentials, data => accountRequest(registering ? "auth/register" : "auth/login", "POST", data));
  const account = await accountRequest("auth/me", "GET");
  if (account) {
    document.querySelector(".profile b").textContent = account.username;
    document.querySelector(".avatar").textContent = account.username[0].toUpperCase();
    profile = account;
    document.querySelector("#account").onclick = showSettings;
    document.querySelector(".profile").onclick = showSettings;
    document.body.classList.remove("signed-out");
  }
  return account;
}
