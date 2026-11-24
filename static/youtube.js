export function youtubeVideoId(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  if (!["https:", "http:"].includes(url.protocol)) return null;
  let id;
  if (["youtu.be", "www.youtu.be"].includes(url.hostname)) {
    id = url.pathname.slice(1).replace(/\/$/, "");
  } else if (["youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"].includes(url.hostname)) {
    id = url.pathname === "/watch" ? url.searchParams.get("v")
      : url.pathname.match(/^\/(?:shorts|embed|live)\/([^/]+)\/?$/)?.[1];
  }
  return id && /^[\w-]{11}$/.test(id) ? id : null;
}

export function bindVideoLookup(form) {
  const {url, kind, title, minutes} = form.elements;
  const status = form.querySelector("[data-video-status]");
  const filled = new Map();
  let controller, timer;
  for (const field of [title, minutes]) {
    field.addEventListener("input", () => filled.delete(field));
  }

  function reset() {
    clearTimeout(timer);
    controller?.abort();
    for (const [field, value] of filled) {
      if (field.value === value) field.value = "";
    }
    filled.clear();
    status.textContent = "";
  }

  function schedule() {
    reset();
    const id = youtubeVideoId(url.value.trim());
    if (!id || kind.value !== "video") return;
    controller = new AbortController();
    const {signal} = controller;
    status.textContent = "Looking up video details…";
    timer = setTimeout(async () => {
      try {
        const response = await fetch("/api/youtube/" + id, {signal});
        if (!response.ok) throw new Error("lookup");
        const data = await response.json();
        if (signal.aborted || !form.isConnected) return;
        function fill(field, value) {
          if (field.value) return;
          field.value = value;
          filled.set(field, field.value);
        }
        fill(title, data.title);
        const seconds = data.duration_seconds;
        if (seconds > 0) {
          const length = Math.floor(seconds / 60) + "m " + seconds % 60 + "s";
          if (seconds <= 86400) fill(minutes, Math.max(1, Math.round(seconds / 60)));
          status.textContent = "Video length: " + length + ". Adjust minutes to match your session.";
        } else {
          status.textContent = "Duration unavailable. Enter your viewing time.";
        }
      } catch {
        if (!signal.aborted) status.textContent = "Couldn’t fetch video details. Enter the title and minutes manually.";
      }
    }, 300);
  }
  url.addEventListener("input", schedule);
  kind.addEventListener("change", schedule);
  form.closest("dialog").addEventListener("close", () => {
    clearTimeout(timer);
    controller?.abort();
  }, {once:true});
}
