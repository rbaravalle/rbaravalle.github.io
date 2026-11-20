/*
 * Replay of one robot run (a replay.json written by robot-agent/batch.py).
 *
 * Embed in a page with:
 *   <div data-robot-replay="/assets/robot-agent/runs/notebook-h003-r0.json"></div>
 *   <script src="/assets/robot-agent/replay.js"></script>
 *
 * Several runs in one player: separate the paths with commas, and optionally
 * name them with data-labels="Goldfish,Notebook".
 *
 * What it draws: the walls (8 cm thick), the exit in green, the path so far,
 * red marks where the robot bumped, the robot, and its lidar at that step:
 * all 72 rays (dashed when a ray sees nothing within 8 m). The model never
 * sees the rays, only a summary of 8 sectors. Older replays without rays show
 * the 8 summary readings instead. Below: what the model said before the
 * action, and its notebook if it has one.
 * The robot itself never sees its position or the map: only the 8 numbers.
 */
(function () {
  'use strict';

  var SECTOR_NAMES = ['front', 'front-left', 'left', 'back-left',
                      'back', 'back-right', 'right', 'front-right'];
  var COLORS = {
    bg: '#11141b', wall: '#aeb6c8', exit: '#7be495', path: '#5a96ff',
    robot: '#ffd166', ray: 'rgba(255, 209, 102, 0.35)', bump: '#ff5370',
    start: '#d9a35b', text: '#d6dae4', dim: '#8a93a6'
  };

  function css() {
    if (document.getElementById('robot-replay-css')) return;
    var s = document.createElement('style');
    s.id = 'robot-replay-css';
    s.textContent =
      '.rr{margin:1.5em 0;font-size:14px;color:' + COLORS.text + '}' +
      '.rr canvas{display:block;width:100%;max-width:520px;margin:0 auto;background:' + COLORS.bg + ';border-radius:6px}' +
      '.rr .rr-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}' +
      '.rr button,.rr select{background:#343b4d;color:' + COLORS.text + ';border:0;border-radius:4px;padding:4px 10px;font:inherit;cursor:pointer}' +
      '.rr button:hover{background:#465069}' +
      '.rr input[type=range]{flex:1;min-width:120px}' +
      '.rr .rr-step{min-width:9em;color:' + COLORS.dim + ';font-variant-numeric:tabular-nums}' +
      '.rr .rr-info{background:' + COLORS.bg + ';border-radius:6px;padding:8px 10px;line-height:1.45}' +
      '.rr .rr-say{font-style:italic}' +
      '.rr .rr-dim{color:' + COLORS.dim + '}' +
      '.rr pre{white-space:pre-wrap;margin:4px 0 0;font-size:13px;background:transparent;border:0;padding:0;color:' + COLORS.text + '}';
    document.head.appendChild(s);
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

  function Player(root, sources, labels) {
    css();
    root.classList.add('rr');
    var canvas = el('canvas', {width: 1040, height: 1200}, root);
    var bar = el('div', {'class': 'rr-bar'}, root);
    var select = null;
    if (sources.length > 1) {
      select = el('select', {}, bar);
      sources.forEach(function (src, i) {
        el('option', {value: i, text: labels[i] || src.split('/').pop()}, select);
      });
    }
    var play = el('button', {text: 'Play'}, bar);
    var slider = el('input', {type: 'range', min: 0, max: 0, value: 0}, bar);
    var stepLabel = el('span', {'class': 'rr-step'}, bar);
    var speed = el('button', {text: '1x'}, bar);
    var info = el('div', {'class': 'rr-info'}, root);

    var run = null, i = 0, timer = null, fps = 4;
    var ctx = canvas.getContext('2d');

    function load(k) {
      stop();
      info.textContent = 'loading...';
      fetch(sources[k]).then(function (r) { return r.json(); }).then(function (data) {
        run = data;
        slider.max = run.steps.length;
        i = 0;
        slider.value = 0;
        draw();
      }).catch(function (e) { info.textContent = 'Could not load ' + sources[k] + ': ' + e; });
    }

    function stop() {
      if (timer) clearInterval(timer);
      timer = null;
      play.textContent = 'Play';
    }

    function poseAt(k) { return k === 0 ? run.start : run.steps[k - 1].pose; }
    function scanAt(k) { return k === 0 ? run.start_scan : run.steps[k - 1].scan; }

    function draw() {
      if (!run) return;
      var h = run.house, M = 0.8;
      var W = h.width + 2 * M, H = h.height + 2 * M;
      var s = Math.min(canvas.width / W, canvas.height / H);
      canvas.height = Math.round(H * s);
      var X = function (x) { return (x + M) * s; };
      var Y = function (y) { return canvas.height - (y + M) * s; };
      ctx.fillStyle = COLORS.bg;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // exit
      var e = h.exit;
      ctx.strokeStyle = COLORS.exit; ctx.lineWidth = 0.08 * s; ctx.setLineDash([0.1 * s, 0.08 * s]);
      ctx.beginPath(); ctx.moveTo(X(e[0]), Y(e[1])); ctx.lineTo(X(e[2]), Y(e[3])); ctx.stroke();
      ctx.setLineDash([]);
      // walls
      ctx.strokeStyle = COLORS.wall; ctx.lineWidth = 0.08 * s; ctx.lineCap = 'round';
      h.walls.forEach(function (w) {
        ctx.beginPath(); ctx.moveTo(X(w[0]), Y(w[1])); ctx.lineTo(X(w[2]), Y(w[3])); ctx.stroke();
      });
      // start
      ctx.fillStyle = COLORS.start;
      ctx.beginPath(); ctx.arc(X(run.start[0]), Y(run.start[1]), 0.06 * s, 0, 7); ctx.fill();
      // path
      ctx.strokeStyle = COLORS.path; ctx.lineWidth = 2; ctx.globalAlpha = 0.8;
      ctx.beginPath(); ctx.moveTo(X(run.start[0]), Y(run.start[1]));
      for (var k = 1; k <= i; k++) { var p = run.steps[k - 1].pose; ctx.lineTo(X(p[0]), Y(p[1])); }
      ctx.stroke(); ctx.globalAlpha = 1;
      // bumps
      ctx.fillStyle = COLORS.bump;
      for (k = 1; k <= i; k++) {
        var st = run.steps[k - 1];
        if (st.bump) { ctx.beginPath(); ctx.arc(X(st.pose[0]), Y(st.pose[1]), 0.05 * s, 0, 7); ctx.fill(); }
      }
      // lidar: all 72 rays when the replay has them; else the 8 summary readings
      var pose = poseAt(i), scan = scanAt(i);
      var hd = pose[2] * Math.PI / 180;
      var rays = i === 0 ? run.start_rays : run.steps[i - 1].rays;
      if (rays) {
        for (k = 0; k < rays.length; k++) {
          var sector = Math.floor(k / 9), off = (k % 9) * 5 - 20;
          var ang = hd + (sector * 45 + off) * Math.PI / 180, r = rays[k];
          ctx.strokeStyle = COLORS.ray; ctx.lineWidth = 1;
          ctx.setLineDash(r === null ? [3, 4] : []);
          var L = r === null ? 8 : r;
          ctx.beginPath(); ctx.moveTo(X(pose[0]), Y(pose[1]));
          ctx.lineTo(X(pose[0] + Math.cos(ang) * L), Y(pose[1] + Math.sin(ang) * L)); ctx.stroke();
          if (r !== null) {
            ctx.fillStyle = COLORS.robot;
            ctx.fillRect(X(pose[0] + Math.cos(ang) * r) - 1.5, Y(pose[1] + Math.sin(ang) * r) - 1.5, 3, 3);
          }
        }
      }
      for (k = 0; k < 8 && !rays; k++) {
        var a = hd + k * Math.PI / 4, d = scan[k];
        var far = d === null;
        var len = far ? 8 : d;
        ctx.strokeStyle = COLORS.ray; ctx.lineWidth = 1.5;
        ctx.setLineDash(far ? [4, 4] : []);
        ctx.beginPath(); ctx.moveTo(X(pose[0]), Y(pose[1]));
        ctx.lineTo(X(pose[0] + Math.cos(a) * len), Y(pose[1] + Math.sin(a) * len)); ctx.stroke();
      }
      ctx.setLineDash([]);
      // robot
      ctx.fillStyle = COLORS.robot;
      ctx.beginPath(); ctx.arc(X(pose[0]), Y(pose[1]), 0.17 * s, 0, 7); ctx.fill();
      ctx.strokeStyle = COLORS.bg; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(X(pose[0]), Y(pose[1]));
      ctx.lineTo(X(pose[0] + Math.cos(hd) * 0.17), Y(pose[1] + Math.sin(hd) * 0.17)); ctx.stroke();

      // text
      var n = run.steps.length;
      stepLabel.textContent = 'step ' + i + ' / ' + n;
      var html = '';
      if (i === 0) {
        html = '<span class="rr-dim">' + run.setting + ' &middot; ' + run.model +
               ' &middot; house ' + run.house.seed + '. Press Play.</span>';
      } else {
        var cur = run.steps[i - 1];
        var act = cur.action === 'move'
          ? 'move(' + cur.requested + ' m)' + (cur.bump ? ': <b style="color:' + COLORS.bump + '">bump</b> after ' + Math.abs(cur.done).toFixed(2) + ' m' : '')
          : 'turn(' + cur.requested + '&deg;)';
        html = '<b>' + act + '</b>';
        if (cur.say) html += '<div class="rr-say">&ldquo;' + escapeHtml(cur.say) + '&rdquo;</div>';
        if (cur.notes) html += '<div class="rr-dim" style="margin-top:6px">notebook:</div><pre>' + escapeHtml(cur.notes) + '</pre>';
      }
      if (i === n) {
        var verdict = run.outcome === 'success' ? 'got out' : run.outcome.replace('_', ' ');
        html += '<div style="margin-top:6px"><b>End: ' + verdict + '</b> after ' + n + ' steps.</div>';
      }
      info.innerHTML = html;
    }

    function escapeHtml(t) {
      return String(t).replace(/[&<>"]/g, function (c) {
        return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
      });
    }

    play.onclick = function () {
      if (timer) { stop(); return; }
      if (run && i >= run.steps.length) i = 0;
      play.textContent = 'Pause';
      timer = setInterval(function () {
        if (!run || i >= run.steps.length) { stop(); return; }
        i++; slider.value = i; draw();
      }, 1000 / fps);
    };
    slider.oninput = function () { i = +slider.value; draw(); };
    speed.onclick = function () {
      fps = fps === 4 ? 12 : fps === 12 ? 40 : 4;
      speed.textContent = {4: '1x', 12: '3x', 40: '10x'}[fps];
      if (timer) { stop(); play.onclick(); }
    };
    if (select) select.onchange = function () { load(+select.value); };

    this.loadData = function (data) { stop(); run = data; slider.max = run.steps.length; i = 0; slider.value = 0; draw(); };
    if (sources.length) load(0);
  }

  function init() {
    var nodes = document.querySelectorAll('[data-robot-replay]');
    for (var k = 0; k < nodes.length; k++) {
      var n = nodes[k];
      if (n.__rr) continue;
      var srcs = (n.getAttribute('data-robot-replay') || '').split(',').map(function (x) { return x.trim(); }).filter(Boolean);
      var labels = (n.getAttribute('data-labels') || '').split(',').map(function (x) { return x.trim(); });
      n.__rr = new Player(n, srcs, labels);
    }
  }
  window.RobotReplay = {init: init, Player: Player};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
