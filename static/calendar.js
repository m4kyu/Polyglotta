const DAY_MS = 86400000;
const weekday = new Intl.DateTimeFormat(undefined, { weekday: "short", timeZone: "UTC" });
const month = new Intl.DateTimeFormat(undefined, { month: "short", timeZone: "UTC" });
const fullDate = new Intl.DateTimeFormat(undefined, { dateStyle: "full", timeZone: "UTC" });
const thresholds = [1, 15, 30, 60];
const dayNumber = iso => Date.parse(iso + "T00:00:00Z") / DAY_MS;

export function calendarData(activities, today) {
  // Use date ordinals for calendar arithmetic, including across DST changes.
  const end = dayNumber(today);
  const start = end - 364;
  const minutes = new Map();
  for (const activity of activities) {
    const day = dayNumber(activity.day);
    if (day <= end) minutes.set(day, (minutes.get(day) ?? 0) + activity.minutes);
  }

  let run = 0, longest = 0, previous;
  for (const day of [...minutes.keys()].sort((a, b) => a - b)) {
    run = day === previous + 1 ? run + 1 : 1;
    longest = Math.max(longest, run);
    previous = day;
  }
  const current = previous >= end - 1 ? run : 0;
  return { start, end, minutes, current, longest };
}

export function renderCalendar(panel, activities, today) {
  const { start, end, minutes, current, longest } = calendarData(activities, today);
  const sunday = start - new Date(start * DAY_MS).getUTCDay();
  const count = n => n + (n === 1 ? " day" : " days");
  panel.innerHTML = `
    <div class="calendar-head"><div><h2>Immersion calendar</h2><p class="sub">Daily immersion over the past year</p></div>
      <dl class="streaks"><div><dt>Current streak</dt><dd>${count(current)}</dd></div>
      <div><dt>Longest streak</dt><dd>${count(longest)}</dd></div></dl></div>
    <div class="calendar-scroll"><div class="calendar-grid" role="group" aria-label="Daily immersion. Use arrow keys to explore dates."></div></div>
    <div class="calendar-foot"><output aria-live="polite"></output><div class="calendar-legend" aria-label="Minutes per day: zero, 1–14, 15–29, 30–59, and 60 or more">Less
      ${[0,1,2,3,4].map(level => '<i class="level-' + level + '"></i>').join("")} More</div></div>`;
  const grid = panel.querySelector(".calendar-grid");
  const output = panel.querySelector("output");
  function label(text, column, row, css) {
    const span = document.createElement("span");
    span.textContent = text;
    span.className = css;
    span.style.gridArea = row + " / " + column;
    grid.append(span);
  }
  for (const offset of [1,3,5]) {
    label(weekday.format((sunday + offset) * DAY_MS), 1, offset + 2, "weekday-label");
  }
  const buttons = [];
  let lastLabel = -5;
  for (let day = start; day <= end; day++) {
    const date = new Date(day * DAY_MS);
    const week = Math.floor((day - sunday) / 7);
    if ((day === start || date.getUTCDate() === 1) && week - lastLabel >= 3 && week <= 50) {
      label(month.format(date), week + 2, 1, "month-label");
      lastLabel = week;
    }
    const total = minutes.get(day) ?? 0;
    const text = fullDate.format(date) + " · " + total + (total === 1 ? " minute" : " minutes");
    const button = document.createElement("button");
    button.type = "button";
    button.title = text;
    button.setAttribute("aria-label", text);
    button.className = "calendar-day level-" + thresholds.filter(n => total >= n).length;
    button.tabIndex = day === end ? 0 : -1;
    button.style.gridArea = (date.getUTCDay() + 2) + " / " + (week + 2);
    buttons.push(button);
    grid.append(button);
    if (day === end) output.textContent = text;
  }
  function select(button) {
    grid.querySelector('[tabindex="0"]').tabIndex = -1;
    button.tabIndex = 0;
    output.textContent = button.title;
  }
  function selectTarget(event) {
    if (event.target.matches("button")) select(event.target);
  }
  grid.addEventListener("focusin", selectTarget);
  grid.addEventListener("click", selectTarget);
  grid.onpointerover = event => {
    if (event.target.matches("button")) output.textContent = event.target.title;
  };
  grid.onpointerleave = () => { output.textContent = grid.querySelector('[tabindex="0"]').title; };
  grid.onkeydown = event => {
    const offset = {ArrowLeft:-7, ArrowRight:7, ArrowUp:-1, ArrowDown:1}[event.key];
    if (!offset) return;
    event.preventDefault();
    const index = buttons.indexOf(event.target);
    const next = buttons[Math.max(0, Math.min(buttons.length - 1, index + offset))];
    next.focus();
    select(next);
  };
  const scroll = panel.querySelector(".calendar-scroll");
  scroll.scrollLeft = scroll.scrollWidth;
}
