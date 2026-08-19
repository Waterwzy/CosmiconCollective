/* 银河战力党 WebUI 前端逻辑 */

"use strict";

// ===== 星空背景 =====

(function starfield() {
  const canvas = document.getElementById("starfield");
  const ctx = canvas.getContext("2d");
  let stars = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    stars = Array.from({ length: 160 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.4 + 0.3,
      speed: Math.random() * 0.25 + 0.05,
      phase: Math.random() * Math.PI * 2,
    }));
  }

  function tick(t) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const s of stars) {
      const alpha = 0.35 + 0.45 * Math.abs(Math.sin(t / 1400 + s.phase));
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(220, 230, 255, ${alpha})`;
      ctx.fill();
      s.y += s.speed;
      if (s.y > canvas.height) s.y = -2;
    }
    requestAnimationFrame(tick);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(tick);
})();

// ===== 音效（WebAudio 合成，无外部资源） =====

const SoundFX = {
  enabled: true,
  ctx: null,

  ensure() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) this.ctx = new AC();
    }
    if (this.ctx && this.ctx.state === "suspended") this.ctx.resume();
    return this.ctx;
  },

  tone(freq, dur = 0.12, type = "sine", vol = 0.06, delay = 0) {
    if (!this.enabled) return;
    const ctx = this.ensure();
    if (!ctx) return;
    const t = ctx.currentTime + delay;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(vol, t);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t);
    osc.stop(t + dur + 0.02);
  },

  click() { this.tone(660, 0.05, "triangle", 0.03); },
  roll() { [0, 70, 140].forEach((d, i) => this.tone(300 + i * 120, 0.06, "square", 0.022, d / 1000)); },
  hit() { this.tone(90, 0.25, "sawtooth", 0.09); this.tone(55, 0.3, "square", 0.07, 0.02); },
  heal() { this.tone(520, 0.12, "sine", 0.05); this.tone(780, 0.18, "sine", 0.05, 0.1); },
  special() { [660, 880, 1320].forEach((f, i) => this.tone(f, 0.12, "triangle", 0.045, i * 0.07)); },
  swap() { this.tone(440, 0.1, "triangle", 0.05); this.tone(590, 0.14, "triangle", 0.05, 0.09); },
  block() { this.tone(220, 0.14, "square", 0.06); this.tone(150, 0.2, "triangle", 0.06, 0.05); },
  clash() { this.tone(120, 0.3, "sawtooth", 0.08); this.tone(880, 0.1, "square", 0.03, 0.02); },
  win() { [523, 659, 784, 1047].forEach((f, i) => this.tone(f, 0.22, "triangle", 0.06, i * 0.12)); },
  lose() { [400, 340, 280, 200].forEach((f, i) => this.tone(f, 0.24, "sine", 0.06, i * 0.14)); },
};

// ===== DOM 工具 =====

function $(id) {
  return document.getElementById(id);
}

$("sound-toggle").onclick = () => {
  SoundFX.enabled = !SoundFX.enabled;
  $("sound-toggle").textContent = SoundFX.enabled ? "🔊" : "🔇";
};

const menuScreen = $("menu-screen");
const gameScreen = $("game-screen");
const overlay = $("overlay");
const toastEl = $("toast");
const effectPop = $("effect-pop");

const PHASE_NAMES = { begin: "开始阶段", attack: "攻击阶段", defence: "防御阶段", sum: "结算阶段" };

/* 效果名 → 图标映射（未收录的效果用 ✦ 兜底） */
const EFFECT_ICONS = {
  "骇入": "💻", "瞬伤": "⚡", "中毒": "🧪", "力场": "🔰", "力量": "💪",
  "干扰": "📡", "治愈": "💖", "攻击等级": "🗡️", "防御等级": "🛡️",
  "洞穿": "🔱", "连击": "🔁", "跃升": "🚀", "荆棘": "🌵", "韧性": "🐚",
  "反击": "↩️", "虹吸": "🩸", "不屈": "🛡️", "进化": "🧬", "翻倍": "✖️",
  "超载": "🔥", "背水": "🏴", "曜彩": "🌈", "升级": "⬆️",
};

const ROLE_ICONS = { attacker: "⚔️", defender: "🛡️" };
const ROLE_NAMES = { attacker: "攻击方", defender: "防御方" };

/* 重投动画的最短可见时长：服务器返回再快，也保证翻滚动画播满 */
const MIN_REROLL_MS = 700;
/* 新回合骰子翻滚揭示的时长 */
const REVEAL_MS = 550;
/* 结算演出各阶段时长：算式分步弹出 → 碰撞/伤害 → 收尾揭示新状态 */
const SETTLE_FORMULA_MS = 1300;
const SETTLE_HIT_MS = 1200;
const SETTLE_TOTAL_MS = SETTLE_FORMULA_MS + SETTLE_HIT_MS + 500;

// ===== 全局状态 =====

let ws = null;
let menu = null;
let pickedCharacter = null;
let pickedSpecial = null;
let currentState = null;
let currentPrompt = null;
let localSelection = new Set();
let gameEnded = false;
let rerollTimer = null;
let rerollStartTs = 0;
let settlementPlaying = false;
let queuedUpdate = null;

// ===== WebSocket =====

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => handleMessage(JSON.parse(ev.data));
  ws.onclose = () => showToast("连接已断开，请刷新页面");
  ws.onerror = () => showToast("连接出错");
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

function handleMessage(msg) {
  if (msg.type === "menu") {
    menu = msg;
    renderMenu();
    return;
  }
  if (msg.type === "error") {
    showToast(msg.message);
    return;
  }
  if (msg.type !== "update") return;

  // 重投动画保底：结果回来得太快时延迟应用，保证翻滚可见
  if (rerollTimer) {
    const remain = MIN_REROLL_MS - (performance.now() - rerollStartTs);
    if (remain > 0) {
      setTimeout(() => handleMessage(msg), remain);
      return;
    }
    stopRerollAnimation();
  }

  // 结算演出期间：日志照常滚动，状态更新排队（全量快照，只保留最新一条）
  if (settlementPlaying) {
    if (msg.log && msg.log.length) appendLog(msg.log);
    queuedUpdate = msg;
    return;
  }

  if (msg.log && msg.log.length) appendLog(msg.log);
  const prev = currentState;
  const settle = msg.settlement || null;
  if (msg.state) currentState = msg.state;
  currentPrompt = msg.prompt || null;
  if (currentPrompt) localSelection.clear();

  // 有结算数据时先播放结算演出，结束后再揭示新状态
  if (settle && prev && msg.state && !msg.game_over?.error) {
    runSettlementSequence(settle, prev, currentState);
    if (msg.game_over) setTimeout(() => showGameOver(msg.game_over), SETTLE_TOTAL_MS + 200);
    return;
  }

  if (msg.state) renderState();
  renderActions();
  if (msg.state) playDiffAnimations(prev, currentState);
  if (msg.game_over) showGameOver(msg.game_over);
}

// ===== 菜单 =====

function renderMenu() {
  const charGrid = $("character-grid");
  charGrid.innerHTML = "";
  for (const c of menu.characters) {
    const card = document.createElement("div");
    card.className = "card";
    const effects = (c.related_effects || [])
      .map((e) => `◆ ${e.name}：${e.description}`)
      .join("\n");
    card.innerHTML = `
      <div class="card-name">${esc(c.name)}</div>
      <div class="card-meta">生命 ${c.hp} · 攻击骰 ${fmtNeed(c.attack_dice)} · 防御骰 ${fmtNeed(c.defence_dice)}</div>
      <div class="mini-dices">${c.dices.map((s) => `<span class="mini-dice">d${s}</span>`).join("")}</div>
      <div class="card-desc">${esc(c.description)}</div>
      ${effects ? `<div class="card-effects">${esc(effects)}</div>` : ""}
    `;
    card.onclick = () => {
      SoundFX.click();
      pickedCharacter = c.index;
      charGrid.querySelectorAll(".card").forEach((el) => el.classList.remove("selected"));
      card.classList.add("selected");
      refreshStartBtn();
    };
    charGrid.appendChild(card);
  }

  const spGrid = $("special-grid");
  spGrid.innerHTML = "";
  for (const d of menu.special_dices) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-name">${esc(d.name)}</div>
      <div class="card-desc">${esc(d.description)}</div>
    `;
    card.onclick = () => {
      SoundFX.click();
      pickedSpecial = d.index;
      spGrid.querySelectorAll(".card").forEach((el) => el.classList.remove("selected"));
      card.classList.add("selected");
      refreshStartBtn();
    };
    spGrid.appendChild(card);
  }
}

function refreshStartBtn() {
  $("start-btn").disabled = pickedCharacter === null || pickedSpecial === null;
}

$("start-btn").onclick = () => {
  const seedRaw = $("seed-input").value.trim();
  send({
    type: "start",
    character: pickedCharacter,
    special_dice: pickedSpecial,
    seed: seedRaw === "" ? null : Number(seedRaw),
  });
  menuScreen.classList.add("hidden");
  gameScreen.classList.remove("hidden");
  overlay.classList.add("hidden");
  gameEnded = false;
  currentState = null;
  currentPrompt = null;
  localSelection.clear();
  $("log-panel").innerHTML = "";
  appendLog(["正在开局，AI 正在选择角色与曜彩骰…"]);
};

// ===== 对局渲染 =====

function renderState() {
  const s = currentState;
  $("round-label").textContent = `第 ${s.round} 回合`;
  $("phase-label").textContent = PHASE_NAMES[s.phase] || "准备中";

  renderPlayer("you", s.you, s, true);
  renderPlayer("opp", s.opponent, s, false);

  $("special-info").textContent = s.you.special_dice
    ? `曜彩骰【${s.you.special_dice.name}】剩余 ${s.you.special_dice.uses_left} 次`
    : "";
}

function renderPlayer(prefix, p, s, isYou) {
  $(`${prefix}-name`).textContent = p.name + (isYou ? "（你）" : "（AI）");

  const roleEl = $(`${prefix}-role-icon`);
  roleEl.textContent = ROLE_ICONS[p.role] || "";
  roleEl.className = `role-icon ${p.role || ""}`;
  roleEl.title = ROLE_NAMES[p.role] || "";

  const hpPct = `${Math.max(0, (p.hp / p.max_hp) * 100)}%`;
  $(`${prefix}-hp-fill`).style.width = hpPct;
  $(`${prefix}-hp-ghost`).style.width = hpPct;
  $(`${prefix}-hp-text`).textContent = `${p.hp} / ${p.max_hp}`;

  const effBar = $(`${prefix}-effects`);
  effBar.innerHTML = "";
  for (const e of p.effects) {
    const icon = document.createElement("span");
    icon.className = "effect-icon";
    icon.dataset.name = e.name;
    icon.innerHTML = `${EFFECT_ICONS[e.name] || "✦"}${
      e.addable ? `<span class="layer-badge">${e.layer}</span>` : ""
    }`;
    icon.onclick = (ev) => {
      ev.stopPropagation();
      SoundFX.click();
      openEffectPop(e, ev.clientX, ev.clientY);
    };
    effBar.appendChild(icon);
  }

  const diceRow = $(`${prefix}-dices`);
  diceRow.innerHTML = "";
  p.dices.forEach((d, i) => diceRow.appendChild(renderDice(d, i, isYou)));

  $(`${prefix}-score`).textContent = scoreLine(p, s);
}

function renderDice(d, index, isYou) {
  const el = document.createElement("div");
  el.className = "dice" + (d.special ? " special-dice" : "");
  el.innerHTML = `
    <span class="dice-value">${d.value}</span>
    <span class="sides-tag">${d.special ? "曜彩" : "d" + d.sides}</span>
    ${d.must_select ? '<span class="must-tag">必选</span>' : ""}
    ${d.effect ? `<span class="effect-tag">${esc(d.effect)}</span>` : ""}
  `;
  if (d.name) el.title = d.name;
  if (!isYou) {
    if (d.selected) el.classList.add("selected");
    else el.classList.add("locked");
    return el;
  }
  // 自己的骰子：仅在等待决策时可点选
  if (currentPrompt && !gameEnded) {
    el.classList.add("selectable");
    if (localSelection.has(index)) el.classList.add("selected");
    el.onclick = () => {
      if (!currentPrompt || gameEnded) return;
      SoundFX.click();
      if (localSelection.has(index)) localSelection.delete(index);
      else localSelection.add(index);
      el.classList.toggle("selected");
      renderActions();
    };
  } else {
    el.classList.add("locked");
    if (d.selected) el.classList.add("selected");
  }
  return el;
}

function scoreLine(p, s) {
  if (p.role === "attacker" && (s.attacker_sum || s.attacker_extra_sum)) {
    const total = (s.attacker_sum + s.attacker_extra_sum) * s.attacker_multiplier;
    return `攻击点数：${s.attacker_sum} + ${s.attacker_extra_sum}${s.attacker_multiplier > 1 ? ` × ${s.attacker_multiplier}` : ""} = ${total}`;
  }
  if (p.role === "defender" && (s.defender_sum || s.defender_extra_sum)) {
    const total = (s.defender_sum + s.defender_extra_sum) * s.defender_multiplier;
    return `防御点数：${s.defender_sum} + ${s.defender_extra_sum}${s.defender_multiplier > 1 ? ` × ${s.defender_multiplier}` : ""} = ${total}`;
  }
  return "";
}

/* 效果详情弹卡：点击图标打开，点击任意空白处关闭 */
function openEffectPop(effect, x, y) {
  effectPop.innerHTML = `
    <div class="effect-pop-title">${EFFECT_ICONS[effect.name] || "✦"} ${esc(effect.name)}${
      effect.addable ? `<span class="effect-pop-layer">×${effect.layer}</span>` : ""
    }</div>
    <div class="effect-pop-desc">${esc(effect.description || "暂无描述")}</div>
  `;
  effectPop.classList.remove("hidden");
  effectPop.style.left = `${Math.max(8, Math.min(x - 20, window.innerWidth - 280))}px`;
  effectPop.style.top = `${Math.max(8, Math.min(y + 14, window.innerHeight - 150))}px`;
}

document.addEventListener("click", () => effectPop.classList.add("hidden"));

// ===== 操作区 =====

function renderActions() {
  const hint = $("action-hint");
  const btnConfirm = $("btn-confirm");
  const btnReload = $("btn-reload");
  const btnSpecial = $("btn-special");

  if (settlementPlaying) {
    hint.textContent = "回合结算中…";
    btnConfirm.disabled = btnReload.disabled = btnSpecial.disabled = true;
    $("you-dices").classList.remove("active");
    return;
  }

  $("you-dices").classList.toggle("active", !!currentPrompt && !gameEnded);
  $("reload-label").textContent =
    currentState && currentPrompt ? `剩余重投 ${currentPrompt.reload_times} 次` : "";

  if (!currentPrompt || gameEnded) {
    if (!gameEnded) hint.textContent = "等待对手行动…";
    btnConfirm.disabled = btnReload.disabled = btnSpecial.disabled = true;
    btnReload.textContent = "重投";
    return;
  }

  const need = currentPrompt.need;
  const needText = need === "any" ? "任意数量" : `${need} 颗`;
  const phaseText = currentPrompt.phase === "attack" ? "攻击" : "防御";
  const selCount = localSelection.size;
  const mustMissing = [];
  if (currentState) {
    currentState.you.dices.forEach((d, i) => {
      if (d.must_select && !localSelection.has(i)) mustMissing.push(i);
    });
  }
  hint.textContent = `${phaseText}阶段：请选择 ${needText}骰子（已选 ${selCount} 颗）`;
  if (mustMissing.length) hint.textContent += "，含「必选」骰子";

  const countOk = need === "any" ? selCount >= 1 : selCount === need;
  btnConfirm.disabled = !countOk || mustMissing.length > 0;
  btnReload.disabled = currentPrompt.reload_times <= 0 || selCount === 0;
  btnReload.textContent = `重投（剩 ${currentPrompt.reload_times} 次）`;
  btnSpecial.disabled = !currentPrompt.special_usable;
}

$("btn-confirm").onclick = () => {
  SoundFX.click();
  send({ type: "action", action: 1, selected: [...localSelection] });
  afterSubmit();
};

$("btn-reload").onclick = () => {
  startRerollAnimation([...localSelection]);
  send({ type: "action", action: 2, selected: [...localSelection] });
  afterSubmit();
};

$("btn-special").onclick = () => {
  SoundFX.special();
  send({ type: "action", action: 3, selected: [] });
  afterSubmit();
};

function afterSubmit() {
  localSelection.clear();
  currentPrompt = null;
  renderActions();
}

// ===== 重投过渡动画（服务器返回前骰子持续翻滚） =====

function startRerollAnimation(indices) {
  stopRerollAnimation();
  if (!currentState || !indices.length) return;
  SoundFX.roll();
  rerollStartTs = performance.now();
  const els = $("you-dices").querySelectorAll(".dice");
  const sides = currentState.you.dices.map((d) => d.sides);
  indices.forEach((i) => els[i] && els[i].classList.add("tumbling"));
  rerollTimer = setInterval(() => {
    indices.forEach((i) => {
      const el = els[i];
      if (!el) return;
      const valueEl = el.querySelector(".dice-value");
      if (valueEl) valueEl.textContent = 1 + Math.floor(Math.random() * sides[i]);
    });
  }, 80);
}

function stopRerollAnimation() {
  if (rerollTimer) {
    clearInterval(rerollTimer);
    rerollTimer = null;
  }
}

// ===== 状态差分动画 =====

function playDiffAnimations(prev, curr, opts = {}) {
  const skipHpPrefix = opts.skipHpPrefix || null;
  if (!prev) {
    revealDice("you", curr.you.dices.map((_, i) => i));
    revealDice("opp", curr.opponent.dices.map((_, i) => i));
    SoundFX.roll();
    return;
  }

  if (curr.round !== prev.round) {
    showRoundBanner(curr.round);
    revealDice("you", curr.you.dices.map((_, i) => i));
    revealDice("opp", curr.opponent.dices.map((_, i) => i));
    SoundFX.roll();
  } else {
    const changedYou = changedDice(prev.you.dices, curr.you.dices);
    if (changedYou.length) {
      revealDice("you", changedYou, 450);
      SoundFX.roll();
    }
    const changedOpp = changedDice(prev.opponent.dices, curr.opponent.dices);
    if (changedOpp.length) revealDice("opp", changedOpp, 450);
  }

  // 攻守互换：两个图标互相飞向对方位置
  if (prev.you.role && curr.you.role && prev.you.role !== curr.you.role) {
    animateRoleSwap();
  }

  // 曜彩骰登场
  if (!prev.you.dices.some((d) => d.special) && curr.you.dices.some((d) => d.special)) {
    flashSpecial("you");
    SoundFX.special();
  }
  if (!prev.opponent.dices.some((d) => d.special) && curr.opponent.dices.some((d) => d.special)) {
    flashSpecial("opp");
    SoundFX.special();
  }

  // 血量变化（含攻击动画；结算演出已展示过的受击方跳过）
  if (skipHpPrefix !== "you") handleHpChange("you", prev.you, curr.you);
  if (skipHpPrefix !== "opp") handleHpChange("opp", prev.opponent, curr.opponent);

  // 效果图标动效
  applyEffectAnims("you", prev.you.effects, curr.you.effects);
  applyEffectAnims("opp", prev.opponent.effects, curr.opponent.effects);

  // 阶段切换
  if (curr.phase !== prev.phase) {
    const badge = $("phase-label");
    badge.classList.remove("phase-pop");
    void badge.offsetWidth;
    badge.classList.add("phase-pop");
  }
}

function changedDice(prevList, currList) {
  const out = [];
  const n = Math.min(prevList.length, currList.length);
  for (let i = 0; i < n; i++) {
    if (prevList[i].value !== currList[i].value) out.push(i);
  }
  return out;
}

/* 骰子揭示：先翻滚并乱跳点数，持续 duration 后落定真实点数 */
function revealDice(prefix, indices, duration = REVEAL_MS) {
  const playerKey = prefix === "you" ? "you" : "opponent";
  const els = $(`${prefix}-dices`).querySelectorAll(".dice");
  indices.forEach((i, order) => {
    const el = els[i];
    if (!el) return;
    const valueEl = el.querySelector(".dice-value");
    if (!valueEl) return;
    const finalValue = valueEl.textContent;
    const sides = currentState[playerKey].dices[i].sides;
    setTimeout(() => {
      el.classList.add("tumbling");
      const scramble = setInterval(() => {
        valueEl.textContent = 1 + Math.floor(Math.random() * sides);
      }, 70);
      setTimeout(() => {
        clearInterval(scramble);
        valueEl.textContent = finalValue;
        el.classList.remove("tumbling");
      }, duration);
    }, order * 80);
  });
}

/* 攻守图标互换：克隆图标互相飞行 + 原图标旋转落定 */
function animateRoleSwap() {
  SoundFX.swap();
  const youIcon = $("you-role-icon");
  const oppIcon = $("opp-role-icon");
  flyIcon(youIcon, oppIcon);
  flyIcon(oppIcon, youIcon);
  [youIcon, oppIcon].forEach((el) => {
    el.classList.add("role-swap");
    setTimeout(() => el.classList.remove("role-swap"), 600);
  });
}

function flyIcon(fromEl, toEl) {
  const a = fromEl.getBoundingClientRect();
  const b = toEl.getBoundingClientRect();
  const clone = document.createElement("div");
  clone.className = fromEl.className + " flying";
  clone.textContent = fromEl.textContent;
  clone.style.left = `${a.left}px`;
  clone.style.top = `${a.top}px`;
  document.body.appendChild(clone);
  requestAnimationFrame(() => {
    clone.style.transform = `translate(${b.left - a.left}px, ${b.top - a.top}px)`;
    clone.style.opacity = "0.3";
  });
  setTimeout(() => clone.remove(), 560);
}

function flashSpecial(prefix) {
  $(`${prefix}-dices`).querySelectorAll(".dice.special-dice").forEach((el) => {
    el.classList.add("special-flash");
    el.addEventListener("animationend", () => el.classList.remove("special-flash"), { once: true });
  });
}

function handleHpChange(prefix, prevP, currP) {
  const delta = currP.hp - prevP.hp;
  if (delta === 0) return;
  const panel = document.querySelector(`.player-panel.${prefix === "you" ? "you" : "opponent"}`);

  if (delta < 0) {
    spawnFloatNum(panel, String(delta), "damage");
    panel.classList.add("hit");
    setTimeout(() => panel.classList.remove("hit"), 700);
    SoundFX.hit();
    animateStrike(prefix === "you" ? "opp" : "you", prefix);
    ghostHp(prefix, prevP, currP);
  } else {
    spawnFloatNum(panel, `+${delta}`, "heal");
    panel.classList.add("healed");
    setTimeout(() => panel.classList.remove("healed"), 750);
    SoundFX.heal();
  }
}

/* 血条残影：先定格在旧血量，再延迟过渡到新血量（格斗游戏式缓冲扣血） */
function ghostHp(prefix, prevP, currP) {
  const ghost = $(`${prefix}-hp-ghost`);
  const oldPct = `${Math.max(0, (prevP.hp / prevP.max_hp) * 100)}%`;
  const newPct = `${Math.max(0, (currP.hp / currP.max_hp) * 100)}%`;
  ghost.style.transition = "none";
  ghost.style.width = oldPct;
  void ghost.offsetWidth;
  ghost.style.transition = "width 1.1s ease 0.6s";
  ghost.style.width = newPct;
}

function animateStrike(fromPrefix, toPrefix) {
  const fromEl = document.querySelector(`.player-panel.${fromPrefix === "you" ? "you" : "opponent"}`);
  const toEl = document.querySelector(`.player-panel.${toPrefix === "you" ? "you" : "opponent"}`);
  if (!fromEl || !toEl) return;

  const lungeClass = fromPrefix === "you" ? "lunge-up" : "lunge-down";
  fromEl.classList.add(lungeClass);
  setTimeout(() => fromEl.classList.remove(lungeClass), 240);

  const a = fromEl.getBoundingClientRect();
  const b = toEl.getBoundingClientRect();
  const ax = a.left + a.width / 2;
  const ay = a.top + a.height / 2;
  const orb = document.createElement("div");
  orb.className = "projectile";
  orb.style.left = `${ax}px`;
  orb.style.top = `${ay}px`;
  document.body.appendChild(orb);
  requestAnimationFrame(() => {
    orb.style.transform = `translate(${b.left + b.width / 2 - ax}px, ${b.top + b.height / 2 - ay}px) scale(0.5)`;
    orb.style.opacity = "0";
  });
  setTimeout(() => orb.remove(), 550);
}

function spawnFloatNum(panel, text, kind) {
  const el = document.createElement("span");
  el.className = `float-num ${kind}`;
  el.textContent = text;
  el.style.left = `${25 + Math.random() * 50}%`;
  panel.appendChild(el);
  el.addEventListener("animationend", () => el.remove(), { once: true });
}

function applyEffectAnims(prefix, prevEffects, currEffects) {
  const prevMap = new Map(prevEffects.map((e) => [e.name, e.layer]));
  const icons = $(`${prefix}-effects`).querySelectorAll(".effect-icon");
  icons.forEach((icon) => {
    const name = icon.dataset.name;
    if (!prevMap.has(name)) {
      icon.classList.add("icon-pop");
    } else {
      const curr = currEffects.find((e) => e.name === name);
      if (curr && curr.addable && curr.layer > prevMap.get(name)) {
        icon.classList.add("icon-flash");
      }
    }
  });
}

let bannerTimer = null;
function showRoundBanner(round) {
  const banner = $("round-banner");
  banner.textContent = `第 ${round} 回合`;
  banner.classList.remove("hidden", "show");
  void banner.offsetWidth;
  banner.classList.add("show");
  clearTimeout(bannerTimer);
  bannerTimer = setTimeout(() => banner.classList.add("hidden"), 1600);
}

// ===== 回合结算演出 =====

function panelClass(prefix) {
  return prefix === "you" ? "you" : "opponent";
}

function sidePrefix(side) {
  return side === "you" ? "you" : "opp";
}

/* 在角色面板上覆盖大字算式：骰面 → 骰子和 + 额外 (×乘数) = 总点数 */
function showSettleOverlay(prefix, info, roleText) {
  const panel = document.querySelector(`.player-panel.${panelClass(prefix)}`);
  const ov = document.createElement("div");
  ov.className = "settle-overlay";
  ov.innerHTML = `
    <div class="settle-role">${roleText}方</div>
    <div class="settle-dice-row">${info.dices.map((v) => `<span class="settle-mini">${v}</span>`).join("")}</div>
    <div class="settle-formula">
      <span class="n part1">${info.dice_sum}</span>
      <span class="op op1">+</span>
      <span class="n part2">${info.extra}</span>
      ${info.mult > 1 ? `<span class="op op2">×</span><span class="n part3">${info.mult}</span>` : ""}
      <span class="op op3">=</span>
      <span class="n total">${info.total}</span>
    </div>
  `;
  panel.appendChild(ov);
  return ov;
}

function runSettlementSequence(settle, prev, curr) {
  settlementPlaying = true;
  renderActions();

  const atkPrefix = sidePrefix(settle.attacker.side);
  const defPrefix = sidePrefix(settle.defender.side);
  const defPlayerKey = settle.defender.side === "you" ? "you" : "opponent";
  const damage = Math.max(0, settle.defender_hp_before - settle.defender_hp_after);

  showSettleOverlay(atkPrefix, settle.attacker, "攻击");
  const defOverlay = showSettleOverlay(defPrefix, settle.defender, "防御");

  // 阶段二：碰撞 —— 光弹、超大伤害数字、血条缓慢下降
  setTimeout(() => {
    SoundFX.clash();
    animateStrike(atkPrefix, defPrefix);
    const panel = document.querySelector(`.player-panel.${panelClass(defPrefix)}`);
    if (damage > 0) {
      defOverlay.classList.add("loser");
      const big = document.createElement("div");
      big.className = "settle-damage-huge";
      big.textContent = `-${damage}`;
      defOverlay.appendChild(big);
      panel.classList.add("hit");
      setTimeout(() => panel.classList.remove("hit"), 800);
      SoundFX.hit();
      slowHpDrop(
        defPrefix,
        settle.defender_hp_before,
        settle.defender_hp_after,
        curr[defPlayerKey].max_hp
      );
    } else {
      const tag = document.createElement("div");
      tag.className = "settle-block";
      tag.textContent = "格挡！";
      defOverlay.appendChild(tag);
      SoundFX.block();
    }
  }, SETTLE_FORMULA_MS);

  // 阶段三：撤下覆盖层，揭示新状态（受击方的血量动画已在演出中展示，跳过）
  setTimeout(() => {
    document.querySelectorAll(".settle-overlay").forEach((el) => el.remove());
    // 清掉 slowHpDrop 的内联过渡，避免影响后续渲染
    for (const prefix of ["you", "opp"]) {
      $(`${prefix}-hp-fill`).style.transition = "";
      $(`${prefix}-hp-ghost`).style.transition = "";
    }
    settlementPlaying = false;
    renderState();
    renderActions();
    playDiffAnimations(prev, curr, { skipHpPrefix: damage > 0 ? defPrefix : null });
    // 演出期间到达的更新（如下一轮决策请求）在此时应用
    const queued = queuedUpdate;
    queuedUpdate = null;
    if (queued) handleMessage(queued);
  }, SETTLE_TOTAL_MS);
}

/* 结算演出专用：血条主条与残影都缓慢下降 */
function slowHpDrop(prefix, hpBefore, hpAfter, maxHp) {
  const fill = $(`${prefix}-hp-fill`);
  const ghost = $(`${prefix}-hp-ghost`);
  const afterPct = `${Math.max(0, (hpAfter / maxHp) * 100)}%`;
  fill.style.transition = "width 1.1s ease";
  fill.style.width = afterPct;
  ghost.style.transition = "width 1.5s ease 0.5s";
  ghost.style.width = afterPct;
  $(`${prefix}-hp-text`).textContent = `${hpAfter} / ${maxHp}`;
}

// ===== 日志 / 提示 / 结算 =====

function classifyLog(line) {
  if (/伤害|受伤|同归于尽|获胜|败/.test(line)) return "log-damage";
  if (/恢复|回复|治愈/.test(line)) return "log-heal";
  if (/曜彩/.test(line)) return "log-special";
  if (/重投|重掷/.test(line)) return "log-roll";
  if (/回合|先手|后手/.test(line)) return "log-round";
  return "";
}

function appendLog(lines) {
  const panel = $("log-panel");
  for (const line of lines) {
    const div = document.createElement("div");
    div.className = `log-line ${classifyLog(line)}`;
    div.textContent = line;
    panel.appendChild(div);
  }
  panel.scrollTop = panel.scrollHeight;
}

let toastTimer = null;
function showToast(text) {
  toastEl.textContent = text;
  toastEl.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.add("hidden"), 2600);
}

function showGameOver(payload) {
  gameEnded = true;
  currentPrompt = null;
  stopRerollAnimation();
  renderActions();
  const title = $("overlay-title");
  const detail = $("overlay-detail");
  title.className = "";
  if (payload.error) {
    title.textContent = "对局中断";
    detail.textContent = payload.error;
  } else if (payload.winner === "you") {
    title.textContent = "胜利！";
    title.className = "win";
    detail.textContent = "你击败了对手，银河属于你。";
    SoundFX.win();
  } else if (payload.winner === "opponent") {
    title.textContent = "败北";
    title.className = "lose";
    detail.textContent = "对手笑到了最后，再接再厉。";
    SoundFX.lose();
  } else {
    title.textContent = "同归于尽";
    detail.textContent = "双方同时倒下，平分秋色。";
    SoundFX.lose();
  }
  overlay.classList.remove("hidden");
  $("action-hint").textContent = "对局已结束";
}

$("btn-again").onclick = () => {
  overlay.classList.add("hidden");
  gameScreen.classList.add("hidden");
  menuScreen.classList.remove("hidden");
};

// ===== 工具 =====

function esc(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function fmtNeed(v) {
  return v === "any" ? "任意" : v;
}

connect();
