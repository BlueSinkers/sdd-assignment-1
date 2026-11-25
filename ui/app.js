(() => {
  const cfg = () => window.HOOPS_CONFIG || {};
  const app = document.getElementById("app");
  const flashEl = document.getElementById("flash");
  const navEl = document.getElementById("nav");

  const TOKEN_KEY = "hoops_token";
  const TEAM_KEY = "hoops_team";

  function token() { return localStorage.getItem(TOKEN_KEY); }
  function team() {
    try { return JSON.parse(localStorage.getItem(TEAM_KEY) || "null"); }
    catch { return null; }
  }
  function setSession(t, teamObj) {
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(TEAM_KEY, JSON.stringify(teamObj));
  }
  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TEAM_KEY);
  }

  function flash(msg, isError = false) {
    if (!msg) {
      flashEl.classList.add("hidden");
      flashEl.textContent = "";
      return;
    }
    flashEl.textContent = msg;
    flashEl.classList.toggle("error", !!isError);
    flashEl.classList.remove("hidden");
  }

  function startupHint(status) {
    if (status === 503) {
      return "A service is starting up (or its database is resuming). Wait a few seconds and try again.";
    }
    return null;
  }

  async function api(base, path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (token()) headers.Authorization = `Bearer ${token()}`;
    let res;
    try {
      res = await fetch(`${base}${path}`, { ...options, headers });
    } catch {
      const err = new Error("Network error — is the service up?");
      err.status = 0;
      throw err;
    }
    const text = await res.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = { raw: text }; }
    if (!res.ok) {
      const hint = startupHint(res.status);
      const msg = hint
        || (body && (body.message || (body.errors && body.errors.join(" ")) || body.error))
        || `Request failed (${res.status})`;
      const err = new Error(msg);
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  }

  const teamsApi = (path, opts) => api(cfg().teamsUrl, path, opts);
  const gamesApi = (path, opts) => api(cfg().gamesUrl, path, opts);

  function route() {
    return (location.hash.replace(/^#/, "") || "/").split("?")[0];
  }

  function renderNav() {
    const t = team();
    const links = [
      ["/", "Home"],
      ["/teams", "Teams"],
      ["/courts", "Courts"],
      ["/stats", "Stats"],
    ];
    if (t) links.push(["/dashboard", "Dashboard"]);
    navEl.innerHTML = links.map(([href, label]) =>
      `<a href="#${href}" class="${route() === href ? "active" : ""}">${label}</a>`
    ).join("") + (
      t
        ? `<span class="muted">${t.name}</span><button type="button" class="linkish" id="logout">Log out</button>`
        : `<a href="#/login">Log in</a><a href="#/register">Register</a>`
    );
    const logout = document.getElementById("logout");
    if (logout) logout.onclick = () => { clearSession(); flash("Logged out."); location.hash = "#/"; paint(); };
  }

  function formToObj(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  async function viewHome() {
    app.innerHTML = `<h1>Upcoming games</h1><p class="lead">Agreed games across Madrid.</p><div id="list" class="muted">Loading…</div>`;
    try {
      const data = await gamesApi("/api/games/upcoming");
      const games = data.games || data;
      const list = document.getElementById("list");
      if (!games.length) {
        list.textContent = "No upcoming games yet.";
        return;
      }
      list.className = "";
      list.innerHTML = `<table><thead><tr><th>When</th><th>Matchup</th><th>Court</th></tr></thead><tbody>${
        games.map(g => `<tr>
          <td>${(g.start_time || "").replace("T", " ")}</td>
          <td>${g.challenger_name || "?"} vs ${g.opponent_name || "?"}</td>
          <td>${g.court_label || g.court_address || ""}</td>
        </tr>`).join("")
      }</tbody></table>${data.teams_degraded ? `<p class="muted">Team names unavailable — Teams service is down.</p>` : ""}`;
    } catch (e) {
      flash(e.message, true);
      document.getElementById("list").textContent = "";
    }
  }

  async function viewTeams() {
    app.innerHTML = `<h1>Teams</h1><p class="lead">Challenge a team that plays your format.</p><div id="list" class="muted">Loading…</div>`;
    try {
      const teams = await teamsApi("/api/teams");
      const me = team();
      const list = document.getElementById("list");
      list.className = "";
      list.innerHTML = `<table><thead><tr><th>Name</th><th>Format</th><th>Skill</th><th>District</th><th></th></tr></thead><tbody>${
        teams.map(t => `<tr>
          <td>${t.name}</td><td>${t.format}</td><td>${t.skill_level}</td><td>${t.district || ""}</td>
          <td>${me && me.format === t.format && me.id !== t.id
            ? `<a class="btn" href="#/challenge/${t.id}">Challenge</a>` : ""}</td>
        </tr>`).join("")
      }</tbody></table>`;
    } catch (e) {
      flash(e.message, true);
    }
  }

  function viewRegister() {
    app.innerHTML = `
      <h1>Register a team</h1>
      <form id="f" class="stack" style="max-width:28rem">
        <label>Team name <input name="name" required maxlength="40" /></label>
        <label>Password <input name="password" type="password" required minlength="6" /></label>
        <label>Captain <input name="captain_name" required /></label>
        <label>Format
          <select name="format"><option>5v5</option><option>3v3</option></select>
        </label>
        <label>Players <input name="player_count" type="number" min="3" value="6" required /></label>
        <label>Skill
          <select name="skill_level">
            <option>casual</option><option>intermediate</option><option>competitive</option>
          </select>
        </label>
        <label>District <input name="district" /></label>
        <button type="submit">Create team</button>
      </form>`;
    document.getElementById("f").onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        const body = formToObj(ev.target);
        body.player_count = Number(body.player_count);
        const data = await teamsApi("/api/register", { method: "POST", body: JSON.stringify(body) });
        setSession(data.token, data.team);
        flash(`Welcome, ${data.team.name}!`);
        location.hash = "#/teams";
        paint();
      } catch (e) { flash(e.message, true); }
    };
  }

  function viewLogin() {
    app.innerHTML = `
      <h1>Captain login</h1>
      <form id="f" class="stack" style="max-width:24rem">
        <label>Team name <input name="name" required /></label>
        <label>Password <input name="password" type="password" required /></label>
        <button type="submit">Log in</button>
      </form>`;
    document.getElementById("f").onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        const data = await teamsApi("/api/login", { method: "POST", body: JSON.stringify(formToObj(ev.target)) });
        setSession(data.token, data.team);
        flash(`Logged in as ${data.team.name}.`);
        location.hash = "#/dashboard";
        paint();
      } catch (e) { flash(e.message, true); }
    };
  }

  async function viewCourts() {
    app.innerHTML = `
      <h1>Courts</h1>
      <p class="lead">Captains propose places to play.</p>
      <div id="list" class="muted">Loading…</div>
      <h2>Add a court</h2>
      <form id="f" class="stack" style="max-width:28rem">
        <label>Name <input name="name" /></label>
        <label>Address <input name="address" required maxlength="200" /></label>
        <label>Google Maps link <input name="maps_url" placeholder="https://…" /></label>
        <button type="submit">Add court</button>
      </form>`;
    try {
      const data = await gamesApi("/api/courts");
      const courts = data.courts || data;
      const list = document.getElementById("list");
      list.className = "";
      list.innerHTML = courts.length
        ? `<table><thead><tr><th>Name</th><th>Address</th><th></th></tr></thead><tbody>${
            courts.map(c => `<tr><td>${c.name || ""}</td><td>${c.address}</td>
              <td>${c.maps_url ? `<a href="${c.maps_url}" target="_blank" rel="noopener">Map</a>` : ""}</td></tr>`).join("")
          }</tbody></table>`
        : `<p class="muted">No courts yet.</p>`;
    } catch (e) { flash(e.message, true); }

    document.getElementById("f").onsubmit = async (ev) => {
      ev.preventDefault();
      if (!token()) { flash("Log in to add a court.", true); return; }
      try {
        await gamesApi("/api/courts", { method: "POST", body: JSON.stringify(formToObj(ev.target)) });
        flash("Court added.");
        paint();
      } catch (e) { flash(e.message, true); }
    };
  }

  async function viewChallenge(opponentId) {
    if (!token()) { location.hash = "#/login"; return paint(); }
    app.innerHTML = `<h1>Send a challenge</h1><p class="lead">Opponent team #${opponentId}</p>
      <form id="f" class="stack" style="max-width:28rem">
        <label>Court <select name="court_id" id="court" required></select></label>
        <label>Date and time <input name="start_time" type="datetime-local" required /></label>
        <button type="submit">Send challenge</button>
      </form>`;
    try {
      const data = await gamesApi("/api/courts");
      const courts = data.courts || data;
      document.getElementById("court").innerHTML = courts.map(c =>
        `<option value="${c.id}">${c.name || c.address}</option>`).join("") || `<option value="">No courts</option>`;
    } catch (e) { flash(e.message, true); }

    document.getElementById("f").onsubmit = async (ev) => {
      ev.preventDefault();
      const body = formToObj(ev.target);
      body.court_id = Number(body.court_id);
      body.opponent_team_id = Number(opponentId);
      try {
        await gamesApi("/api/challenges", { method: "POST", body: JSON.stringify(body) });
        flash("Challenge sent.");
        location.hash = "#/dashboard";
        paint();
      } catch (e) { flash(e.message, true); }
    };
  }

  async function viewDashboard() {
    if (!token()) { location.hash = "#/login"; return paint(); }
    app.innerHTML = `<h1>Dashboard</h1><p class="lead">Your challenges and games.</p><div id="d" class="muted">Loading…</div>`;
    try {
      const d = await gamesApi("/api/dashboard");
      const block = (title, rows, render) =>
        `<h2>${title}</h2>${rows.length ? `<div class="stack">${rows.map(render).join("")}</div>` : `<p class="muted">None.</p>`}`;
      const when = (g) => (g.start_time || "").replace("T", " ");
      const el = document.getElementById("d");
      el.className = "";
      el.innerHTML = [
        block("Received", d.received || [], g =>
          `<div class="row"><span>${g.challenger_name} · ${when(g)} · ${g.court_label}</span>
            <button data-act="accept" data-id="${g.id}">Agree</button>
            <button class="secondary" data-act="decline" data-id="${g.id}">Decline</button></div>`),
        block("Sent", d.sent || [], g =>
          `<div class="row"><span>${g.opponent_name} · ${when(g)}</span>
            <button class="secondary" data-act="cancel" data-id="${g.id}">Cancel</button></div>`),
        block("Upcoming", d.upcoming || [], g =>
          `<div>${g.challenger_name} vs ${g.opponent_name} · ${when(g)} · ${g.court_label}</div>`),
        block("Played — turnout", d.played || [], g =>
          `<form class="row turnout" data-id="${g.id}">
            <span>${g.challenger_name} vs ${g.opponent_name} · ${when(g)}</span>
            <input name="players" type="number" min="0" style="width:5rem" value="${g.my_turnout ?? ""}" required />
            <button type="submit">Save</button>
          </form>`),
        block("History", d.history || [], g =>
          `<div class="muted">${g.status}: ${g.challenger_name} vs ${g.opponent_name} · ${when(g)}</div>`),
      ].join("");

      el.querySelectorAll("button[data-act]").forEach(btn => {
        btn.onclick = async () => {
          try {
            await gamesApi(`/api/challenges/${btn.dataset.id}/${btn.dataset.act}`, { method: "POST", body: "{}" });
            flash(`Challenge ${btn.dataset.act}ed.`);
            paint();
          } catch (e) { flash(e.message, true); }
        };
      });
      el.querySelectorAll("form.turnout").forEach(f => {
        f.onsubmit = async (ev) => {
          ev.preventDefault();
          try {
            await gamesApi(`/api/challenges/${f.dataset.id}/turnout`, {
              method: "POST",
              body: JSON.stringify({ players: Number(new FormData(f).get("players")) }),
            });
            flash("Turnout saved.");
            paint();
          } catch (e) { flash(e.message, true); }
        };
      });
    } catch (e) { flash(e.message, true); }
  }

  async function viewStats() {
    app.innerHTML = `<h1>Stats</h1><div id="s" class="muted">Loading…</div>`;
    try {
      const s = await gamesApi("/api/stats");
      const el = document.getElementById("s");
      el.className = "stack";
      el.innerHTML = `
        <p>Games played: <strong>${s.games_played}</strong> · Upcoming: <strong>${s.upcoming_games}</strong> · Open challenges: <strong>${s.pending_challenges}</strong></p>
        <p>Acceptance rate: <strong>${s.acceptance_rate ?? "—"}%</strong> · Turnout rate: <strong>${s.turnout_rate ?? "—"}%</strong></p>
        <p>Players attended: <strong>${s.players_attended}</strong> · Avg per game: <strong>${s.avg_players_per_game ?? "—"}</strong></p>
        <p>By format — 3v3: ${s.games_by_format?.["3v3"] ?? 0}, 5v5: ${s.games_by_format?.["5v5"] ?? 0}</p>
        ${s.teams_degraded ? `<p class="muted">Some team names unavailable.</p>` : ""}`;
    } catch (e) { flash(e.message, true); }
  }

  async function paint() {
    flash("");
    renderNav();
    const r = route();
    if (r === "/") return viewHome();
    if (r === "/teams") return viewTeams();
    if (r === "/register") return viewRegister();
    if (r === "/login") return viewLogin();
    if (r === "/courts") return viewCourts();
    if (r === "/dashboard") return viewDashboard();
    if (r === "/stats") return viewStats();
    const m = r.match(/^\/challenge\/(\d+)$/);
    if (m) return viewChallenge(m[1]);
    app.innerHTML = `<h1>Not found</h1>`;
  }

  window.addEventListener("hashchange", paint);
  paint();
})();
