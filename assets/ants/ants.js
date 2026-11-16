/*
 * Ant colony simulation: emergent trails between a nest and food sources.
 *
 * Embed in a page with:
 *   <div data-ant-sim></div>
 *   <script src="/assets/ants/ants.js"></script>
 *
 * How it works (the whole "intelligence" is in these few rules):
 *   - Every ant is in one of two states: SEARCHING for food, or RETURNING home
 *     carrying food.
 *   - There are two pheromone fields on a grid:
 *       toHome: laid by searching ants ("I came from the nest this way")
 *       toFood: laid by returning ants ("I came from food this way")
 *   - Searching ants follow toFood; returning ants follow toHome.
 *   - The amount an ant deposits fades with the time since it left the nest or
 *     the food, so trails are strongest close to where they lead.
 *   - Pheromone evaporates and diffuses a little every step.
 *   - Ants "smell" with three sensors (left, ahead, right) and turn towards the
 *     strongest one, plus a bit of random wandering.
 */
(function () {
  'use strict';

  var W = 320, H = 200;          // pheromone grid size (cells)
  var SCALE = 3;                 // canvas pixels per cell

  var DEFAULTS = {
    ants: 500,
    stepsPerFrame: 2,
    speed: 1.0,                  // cells per step
    sensorDist: 7,               // cells ahead
    sensorAngle: 0.55,           // radians
    turnRate: 0.3,               // radians per step
    wander: 0.12,                // random turn, radians per step
    deposit: 1.0,                // pheromone at the moment of leaving nest/food
    depositTau: 150,             // deposit fades as exp(-steps / tau)
    senseMin: 0.02,              // ignore pheromone weaker than this
    patience: 600,               // searching ants give up and go home after this many steps
    evaporation: 0.01,           // fraction lost per step
    diffusion: 0.08,             // fraction mixed with neighbours per step
    maxPheromone: 6,
    reinforceCap: 4,             // see step 5 in stepAnt
    seeRadius: 10,               // ants spot a target directly within this range
    foodAmount: 1500,
    respawnFood: true,           // when a source runs out, a new one appears elsewhere
    showTrails: true,
    showAnts: true
  };

  function Sim(opts) {
    this.p = {};
    for (var k in DEFAULTS) this.p[k] = DEFAULTS[k];
    for (var k2 in opts || {}) this.p[k2] = opts[k2];
    this.reset();
  }

  Sim.prototype.reset = function () {
    this.toFood = new Float32Array(W * H);
    this.toHome = new Float32Array(W * H);
    this.tmp = new Float32Array(W * H);
    this.nest = { x: 55, y: 100, r: 9 };
    this.foods = [
      { x: 262, y: 42, r: 7, amount: this.p.foodAmount },
      { x: 275, y: 158, r: 7, amount: this.p.foodAmount },
      { x: 165, y: 172, r: 6, amount: this.p.foodAmount }
    ];
    this.ants = [];
    this.setAntCount(this.p.ants);
    this.delivered = 0;
    this.steps = 0;
  };

  Sim.prototype.clearTrails = function () {
    this.toFood.fill(0);
    this.toHome.fill(0);
  };

  Sim.prototype.newAnt = function () {
    var a = Math.random() * Math.PI * 2;
    return {
      x: this.nest.x + Math.cos(a) * this.nest.r * 0.5,
      y: this.nest.y + Math.sin(a) * this.nest.r * 0.5,
      a: a,
      carrying: false,
      t: 0,                      // steps since leaving the nest or the food
      lost: false                // gave up searching, heading home empty-handed
    };
  };

  Sim.prototype.setAntCount = function (n) {
    this.p.ants = n;
    while (this.ants.length < n) this.ants.push(this.newAnt());
    if (this.ants.length > n) this.ants.length = n;
  };

  Sim.prototype.addFood = function (x, y) {
    this.foods.push({ x: x, y: y, r: 7, amount: this.p.foodAmount });
  };

  Sim.prototype.spawnFoodAwayFromNest = function () {
    for (var tries = 0; tries < 50; tries++) {
      var x = 15 + Math.random() * (W - 30), y = 15 + Math.random() * (H - 30);
      if (Math.hypot(x - this.nest.x, y - this.nest.y) > 110) { this.addFood(x, y); return; }
    }
  };

  function sample(field, x, y) {
    var ix = x | 0, iy = y | 0;
    if (ix < 0 || iy < 0 || ix >= W || iy >= H) return -1;
    return field[iy * W + ix];
  }

  Sim.prototype.stepAnt = function (ant) {
    var p = this.p;
    var homeward = ant.carrying || ant.lost;
    var follow = homeward ? this.toHome : this.toFood;
    var lay = ant.carrying ? this.toFood : this.toHome;

    // 1. Smell: three sensors ahead of the ant.
    var sd = p.sensorDist, sa = p.sensorAngle;
    var l = sample(follow, ant.x + Math.cos(ant.a - sa) * sd, ant.y + Math.sin(ant.a - sa) * sd);
    var c = sample(follow, ant.x + Math.cos(ant.a) * sd, ant.y + Math.sin(ant.a) * sd);
    var r = sample(follow, ant.x + Math.cos(ant.a + sa) * sd, ant.y + Math.sin(ant.a + sa) * sd);
    if (Math.max(l, c, r) > p.senseMin && (c < l || c < r)) {
      ant.a += (l > r ? -1 : 1) * p.turnRate;
    }

    // 2. Wander a little.
    ant.a += (Math.random() - 0.5) * 2 * p.wander;

    // 3. If the target is close enough to see, head for it.
    var target = null, best = Infinity;
    if (homeward) {
      var dn = Math.hypot(this.nest.x - ant.x, this.nest.y - ant.y);
      if (dn < this.nest.r + p.seeRadius) target = this.nest;
    } else {
      for (var i = 0; i < this.foods.length; i++) {
        var f = this.foods[i];
        var d = Math.hypot(f.x - ant.x, f.y - ant.y);
        if (d < f.r + p.seeRadius && d < best) { best = d; target = f; }
      }
    }
    if (target) ant.a = Math.atan2(target.y - ant.y, target.x - ant.x);

    // 4. Move, bouncing off the edges.
    var nx = ant.x + Math.cos(ant.a) * p.speed;
    var ny = ant.y + Math.sin(ant.a) * p.speed;
    if (nx < 1 || nx > W - 2) { ant.a = Math.PI - ant.a; nx = ant.x; }
    if (ny < 1 || ny > H - 2) { ant.a = -ant.a; ny = ant.y; }
    ant.x = nx; ant.y = ny;

    // 5. Lay pheromone, weaker the longer since leaving home/food.
    //    Lost ants lay nothing: they have no useful news.
    if (!ant.lost) {
      var idx = (ant.y | 0) * W + (ant.x | 0);
      var amt = p.deposit * Math.exp(-ant.t / p.depositTau);
      // Reinforce, but never beyond a few times what this ant itself would
      // lay. Fresh ants (just left nest/food) can build strong trails; ants
      // that have been wandering for a long time cannot, however many of them
      // there are. Without this, a crowd of ants can keep a loop alive forever.
      var ceiling = Math.min(p.maxPheromone, amt * p.reinforceCap);
      lay[idx] = Math.max(lay[idx], Math.min(lay[idx] + amt, ceiling));
    }
    ant.t++;
    if (!ant.carrying && !ant.lost && ant.t > p.patience) ant.lost = true;

    // 6. Arrive: pick up food, or drop it at the nest. Turn around either way.
    if (homeward) {
      if (Math.hypot(this.nest.x - ant.x, this.nest.y - ant.y) < this.nest.r) {
        if (ant.carrying) this.delivered++;
        ant.carrying = false; ant.lost = false; ant.t = 0; ant.a += Math.PI;
      }
    } else {
      for (var j = 0; j < this.foods.length; j++) {
        var fo = this.foods[j];
        if (fo.amount > 0 && Math.hypot(fo.x - ant.x, fo.y - ant.y) < fo.r) {
          fo.amount--; ant.carrying = true; ant.t = 0; ant.a += Math.PI;
          break;
        }
      }
    }
  };

  // Evaporate and diffuse (a cheap 3x3 blur) one field.
  Sim.prototype.updateField = function (field) {
    var p = this.p, tmp = this.tmp;
    var keep = 1 - p.evaporation, d = p.diffusion;
    for (var y = 1; y < H - 1; y++) {
      var row = y * W;
      for (var x = 1; x < W - 1; x++) {
        var i = row + x;
        var avg = (field[i - W - 1] + field[i - W] + field[i - W + 1] +
                   field[i - 1] + field[i] + field[i + 1] +
                   field[i + W - 1] + field[i + W] + field[i + W + 1]) / 9;
        tmp[i] = (field[i] * (1 - d) + avg * d) * keep;
      }
    }
    field.set(tmp);
  };

  Sim.prototype.step = function () {
    for (var i = 0; i < this.ants.length; i++) this.stepAnt(this.ants[i]);
    this.updateField(this.toFood);
    this.updateField(this.toHome);
    var before = this.foods.length;
    this.foods = this.foods.filter(function (f) { return f.amount > 0; });
    if (this.p.respawnFood) {
      for (var k = this.foods.length; k < before; k++) this.spawnFoodAwayFromNest();
    }
    this.steps++;
  };

  // ---------------------------------------------------------------- rendering

  var BG = [17, 20, 27];
  var FOOD_COL = [120, 230, 150];   // toFood trail
  var HOME_COL = [90, 150, 255];    // toHome trail

  function Renderer(sim, canvas) {
    this.sim = sim;
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.off = document.createElement('canvas');
    this.off.width = W; this.off.height = H;
    this.offCtx = this.off.getContext('2d');
    this.img = this.offCtx.createImageData(W, H);
  }

  Renderer.prototype.draw = function () {
    var s = this.sim, ctx = this.ctx, data = this.img.data;
    var show = s.p.showTrails, norm = 1 / 1.5;
    for (var i = 0, j = 0; i < W * H; i++, j += 4) {
      // sqrt makes faint trails visible without saturating the strong ones
      var f = show ? Math.sqrt(Math.min(1, s.toFood[i] * norm)) : 0;
      var h = show ? Math.sqrt(Math.min(1, s.toHome[i] * norm)) * 0.7 : 0;
      data[j]     = Math.min(255, BG[0] + f * FOOD_COL[0] + h * HOME_COL[0]);
      data[j + 1] = Math.min(255, BG[1] + f * FOOD_COL[1] + h * HOME_COL[1]);
      data[j + 2] = Math.min(255, BG[2] + f * FOOD_COL[2] + h * HOME_COL[2]);
      data[j + 3] = 255;
    }
    this.offCtx.putImageData(this.img, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(this.off, 0, 0, W * SCALE, H * SCALE);

    // nest
    ctx.fillStyle = '#d9a35b';
    ctx.beginPath();
    ctx.arc(s.nest.x * SCALE, s.nest.y * SCALE, s.nest.r * SCALE, 0, Math.PI * 2);
    ctx.fill();

    // food, shrinking as it is eaten
    ctx.fillStyle = '#7be495';
    for (var k = 0; k < s.foods.length; k++) {
      var fo = s.foods[k];
      var rr = fo.r * SCALE * Math.sqrt(fo.amount / s.p.foodAmount);
      ctx.beginPath();
      ctx.arc(fo.x * SCALE, fo.y * SCALE, Math.max(2, rr), 0, Math.PI * 2);
      ctx.fill();
    }

    if (!s.p.showAnts) return;
    var ants = s.ants;
    ctx.fillStyle = 'rgba(230, 234, 244, 0.85)';
    for (var a = 0; a < ants.length; a++) {
      if (!ants[a].carrying) ctx.fillRect(ants[a].x * SCALE - 1, ants[a].y * SCALE - 1, 2.5, 2.5);
    }
    ctx.fillStyle = '#ffd166';
    for (var b = 0; b < ants.length; b++) {
      if (ants[b].carrying) ctx.fillRect(ants[b].x * SCALE - 1, ants[b].y * SCALE - 1, 2.5, 2.5);
    }
  };

  // ---------------------------------------------------------------------- UI

  var CSS =
    '.ant-sim{margin:1.5em 0;font-size:14px;color:#d6dae4}' +
    '.ant-sim canvas{display:block;width:100%;height:auto;border-radius:6px;' +
    'background:#11141b;cursor:crosshair;touch-action:manipulation}' +
    '.ant-sim .as-controls{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin-top:10px}' +
    '.ant-sim button{background:#343b4d;color:#d6dae4;border:0;border-radius:4px;' +
    'padding:5px 12px;font:inherit;cursor:pointer}' +
    '.ant-sim button:hover{background:#465069}' +
    '.ant-sim label{display:flex;align-items:center;gap:6px;white-space:nowrap}' +
    '.ant-sim input[type=range]{width:110px}' +
    '.ant-sim .as-stats{margin-left:auto;color:#8a93a6;font-variant-numeric:tabular-nums}' +
    '.ant-sim .as-legend{margin-top:6px;color:#8a93a6;font-size:13px}' +
    '.ant-sim .as-dot{display:inline-block;width:9px;height:9px;border-radius:50%;' +
    'margin:0 4px 0 10px;vertical-align:middle}';

  function injectCss() {
    if (document.getElementById('ant-sim-css')) return;
    var st = document.createElement('style');
    st.id = 'ant-sim-css';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  function el(tag, attrs, parent) {
    var e = document.createElement(tag);
    for (var k in attrs) {
      if (k === 'text') e.textContent = attrs[k];
      else if (k === 'html') e.innerHTML = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    if (parent) parent.appendChild(e);
    return e;
  }

  function slider(parent, label, min, max, step, value, onInput) {
    var lab = el('label', {}, parent);
    el('span', { text: label }, lab);
    var input = el('input', { type: 'range', min: min, max: max, step: step, value: value }, lab);
    input.addEventListener('input', function () { onInput(parseFloat(input.value)); });
    return input;
  }

  function mount(container, opts) {
    injectCss();
    container.classList.add('ant-sim');
    var sim = new Sim(opts);
    var canvas = el('canvas', { width: W * SCALE, height: H * SCALE,
      'aria-label': 'Ant colony simulation. Click to drop food.' }, container);
    var renderer = new Renderer(sim, canvas);

    var controls = el('div', { 'class': 'as-controls' }, container);
    var running = true;
    var playBtn = el('button', { type: 'button', text: 'Pause' }, controls);
    playBtn.addEventListener('click', function () {
      running = !running;
      playBtn.textContent = running ? 'Pause' : 'Play';
    });
    el('button', { type: 'button', text: 'Reset' }, controls)
      .addEventListener('click', function () { sim.reset(); });
    el('button', { type: 'button', text: 'Clear trails' }, controls)
      .addEventListener('click', function () { sim.clearTrails(); });

    slider(controls, 'Ants', 50, 1500, 50, sim.p.ants, function (v) { sim.setAntCount(v); });
    slider(controls, 'Evaporation', 0.001, 0.03, 0.001, sim.p.evaporation,
      function (v) { sim.p.evaporation = v; });
    slider(controls, 'Speed', 1, 8, 1, sim.p.stepsPerFrame,
      function (v) { sim.p.stepsPerFrame = v; });

    var trailsLab = el('label', {}, controls);
    var trailsBox = el('input', { type: 'checkbox' }, trailsLab);
    trailsBox.checked = sim.p.showTrails;
    el('span', { text: 'Trails' }, trailsLab);
    trailsBox.addEventListener('change', function () { sim.p.showTrails = trailsBox.checked; });

    var stats = el('span', { 'class': 'as-stats' }, controls);

    el('div', { 'class': 'as-legend', html:
      'Click to drop food.' +
      '<span class="as-dot" style="background:#d9a35b"></span>nest' +
      '<span class="as-dot" style="background:#7be495"></span>food / trail to food' +
      '<span class="as-dot" style="background:#5a96ff"></span>trail to nest' +
      '<span class="as-dot" style="background:#ffd166"></span>ant carrying food' }, container);

    canvas.addEventListener('click', function (e) {
      var rect = canvas.getBoundingClientRect();
      var x = (e.clientX - rect.left) / rect.width * W;
      var y = (e.clientY - rect.top) / rect.height * H;
      sim.addFood(x, y);
    });

    // Only animate while visible, so a long blog post stays light.
    var visible = true;
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
      }).observe(canvas);
    }
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      running = false;
      playBtn.textContent = 'Play';
    }

    function frame() {
      if (running && visible) {
        for (var i = 0; i < sim.p.stepsPerFrame; i++) sim.step();
      }
      if (visible) {
        renderer.draw();
        stats.textContent = 'Food delivered: ' + sim.delivered;
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    return sim;
  }

  window.AntSim = { mount: mount, Sim: Sim, W: W, H: H };

  function autoMount() {
    var nodes = document.querySelectorAll('[data-ant-sim]');
    for (var i = 0; i < nodes.length; i++) {
      var opts = {};
      try { opts = JSON.parse(nodes[i].getAttribute('data-ant-sim') || '{}'); } catch (e) {}
      mount(nodes[i], opts);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', autoMount);
  else autoMount();
})();
