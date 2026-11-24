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

function showSettings(account) {
  const body = document.querySelector("#dialogBody");
  body.innerHTML = '<h2>Account</h2><p></p><button id="logout">Sign out</button> <button id="delete-profile">Delete account…</button> <button data-close>Close</button><p class="error" role="alert"></p>';
  body.querySelector("p").textContent = account.username;
  dialog.showModal();
  body.querySelector("#logout").onclick = async () => {
    try {
      await accountRequest("auth/logout", "POST");
      completed();
    } catch (error) {
      body.querySelector(".error").textContent = error.message;
    }
  };
  body.querySelector("#delete-profile").onclick = () => {
    body.innerHTML = '<h2>Delete your account?</h2><p>This permanently deletes your account, languages, history and cards from the live journal and signs out every device. Backup copies expire according to the host’s retention policy.</p><form><label>Current password<input type="password" name="password" required autocomplete="current-password"></label><p class="error" role="alert"></p><button type="button" data-close>Cancel</button> <button class="primary">Permanently delete account</button></form>';
    bindForm(body.querySelector("form"), data => accountRequest("account", "DELETE", data));
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
    document.querySelector("#account").onclick = () => showSettings(account);
    document.body.classList.remove("signed-out");
  }
  return account;
}
