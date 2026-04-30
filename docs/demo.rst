.. _demo:

Live Demo
=========

Try pymahjong without installing anything. The demos below run entirely in your browser.

Random AI Demo
---------------

Watch a short pre-recorded 4-AI sample battle. No installation required.

.. raw:: html

   <style>
   #demo-root { font-family: system-ui, sans-serif; max-width: 920px; margin: 1.5rem 0; }
   #demo-canvas { display: block; margin: 0 auto; background: #1a2a1a; border-radius: 8px; cursor: default; width: 100%; height: auto; }
   #demo-controls { display: flex; gap: 6px; justify-content: center; margin-top: 10px; flex-wrap: wrap; }
   #demo-controls button { padding: 5px 14px; border-radius: 4px; border: 1px solid #555; background: #222; color: #ddd; cursor: pointer; font-size: 13px; }
   #demo-controls button:hover { background: #3a3a3a; }
   #demo-controls button:disabled { opacity: 0.35; cursor: default; }
   #demo-info { display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; margin-top: 8px; font-size: 12px; color: #777; }
   #demo-players { display: flex; justify-content: space-around; margin-top: 8px; font-size: 12px; color: #666; gap: 6px; flex-wrap: wrap; }
   .dp { text-align: center; padding: 2px 8px; border-radius: 4px; }
   .dp.active { color: #ffd700; background: rgba(255,215,0,0.08); font-weight: bold; }
   #demo-speed { display: flex; align-items: center; gap: 8px; justify-content: center; margin-top: 6px; font-size: 12px; color: #666; flex-wrap: wrap; }
   #demo-speed input { cursor: pointer; }
   #demo-status { text-align: center; margin-top: 8px; font-size: 12px; color: #666; }
   </style>

   <div id="demo-root">
     <canvas id="demo-canvas" width="900" height="500"></canvas>
     <div id="demo-controls">
       <button id="d-btn-start" onclick="Demo.start()">&#9654; Start</button>
       <button id="d-btn-pause" onclick="Demo.pause()" disabled>&#9646;&#9646; Pause</button>
       <button id="d-btn-reset" onclick="Demo.reset()">&#8634; Reset</button>
       <button id="d-btn-slow" onclick="Demo.setSpeed(1200)">Slow</button>
       <button id="d-btn-fast" onclick="Demo.setSpeed(300)">Fast</button>
     </div>
     <div id="demo-info">
       <span>Step <span id="d-step">0</span> / <span id="d-total">0</span></span>
       <span>Honba: <span id="d-honba">0</span></span>
       <span>Riichibo: <span id="d-riichibo">0</span></span>
       <span>Dora: <span id="d-dora"></span></span>
       <span>Oya: <span id="d-oya">P0</span></span>
     </div>
     <div id="demo-players">
       <div class="dp" id="dp-0">P0 (You)</div>
       <div class="dp" id="dp-1">P1 (Right)</div>
       <div class="dp" id="dp-2">P2 (Top)</div>
       <div class="dp" id="dp-3">P3 (Left)</div>
     </div>
     <div id="demo-speed">
       Speed:
       <input type="range" id="d-speed" min="80" max="2000" value="600" step="20"
              oninput="Demo.setSpeed(this.value); document.getElementById('d-sv').textContent=this.value+'ms'">
       <span id="d-sv">600ms</span>
     </div>
     <div id="demo-status">Loading demo data...</div>
   </div>

   <script>
   var DEMO_GAME = { steps: [] };
   var DEMO_LOAD_ERROR = null;

   function setDemoStatus(message) {
     var el = document.getElementById('demo-status');
     if (el) el.textContent = message;
   }

   function loadDemoGame() {
     return fetch('_static/demo_game.json')
       .then(function(response) {
         if (!response.ok) throw new Error('HTTP ' + response.status);
         return response.json();
       })
       .then(function(data) {
         DEMO_GAME = data || { steps: [] };
         setDemoStatus('Ready');
       })
       .catch(function(error) {
         DEMO_LOAD_ERROR = error;
         setDemoStatus('Failed to load demo data');
         console.error('Failed to load demo data', error);
       });
   }

   var W = 900, H = 500;
   var TW = 30, TH = 42, TR = 3;
   var RW = 20, RH = 28;
   var P0Y = H - TH - 14, P0X = 14;
   var P1X = W - RH - 14, P1Y = 50;
   var P2X = 14, P2Y = 14;
   var P3X = 14, P3Y = 50;
   var TC = {m:'#1a5276', p:'#922b21', s:'#1e8449', z:'#1a1a6e'};

   function tc(s) { return TC[s.slice(-1)] || '#222'; }

   function rRect(c, x, y, w, h, r) {
     c.beginPath();
     c.moveTo(x + r, y);
     c.lineTo(x + w - r, y);
     c.quadraticCurveTo(x + w, y, x + w, y + r);
     c.lineTo(x + w, y + h - r);
     c.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
     c.lineTo(x + r, y + h);
     c.quadraticCurveTo(x, y + h, x, y + h - r);
     c.lineTo(x, y + r);
     c.quadraticCurveTo(x, y, x + r, y);
     c.closePath();
   }

   function dT(c, x, y, tile, opt) {
     opt = opt || {};
     var w = opt.w || TW;
     var h = opt.h || TH;
     var bg = opt.sel ? '#ffe066' : opt.hl ? '#fff3cd' : '#faf8f0';
     c.shadowColor = 'rgba(0,0,0,0.28)';
     c.shadowBlur = opt.sel ? 7 : 3;
     c.shadowOffsetX = 1;
     c.shadowOffsetY = 2;
     c.fillStyle = bg;
     rRect(c, x, y, w, h, TR);
     c.fill();
     c.shadowColor = 'transparent';
     c.strokeStyle = opt.sel ? '#f39c12' : (opt.hl ? '#e67e22' : '#aaa');
     c.lineWidth = opt.sel ? 2 : 1;
     rRect(c, x, y, w, h, TR);
     c.stroke();
     if (!tile) return;
     c.fillStyle = tc(tile);
     c.font = "bold " + (w * 0.52) + "px 'SimHei','Microsoft YaHei',serif";
     c.textAlign = 'center';
     c.textBaseline = 'middle';
     c.fillText(tile, x + w / 2, y + h / 2 + 1);
   }

   function dTB(c, x, y) {
     c.fillStyle = '#1a3a5c';
     rRect(c, x, y, RW, RH, 2);
     c.fill();
     c.strokeStyle = '#3a6a9c';
     c.lineWidth = 1;
     rRect(c, x, y, RW, RH, 2);
     c.stroke();
     c.strokeStyle = '#2a5a8c';
     c.lineWidth = 0.5;
     for (var i = -RH; i < RW + RH; i += 5) {
       c.beginPath();
       c.moveTo(x + i, y);
       c.lineTo(x + i + RH, y + RH);
       c.stroke();
     }
   }

   function dRT(c, x, y, tile, rot) {
     if (!tile) {
       dTB(c, x, y);
       return;
     }
     if (rot) dT(c, x, y, tile, {h: RW, w: RH});
     else dT(c, x, y, tile, {w: RW, h: RH});
   }

   function gRP(i, idx) {
     var cols = 6;
     if (i === 0) return {x: P0X + (idx % cols) * RW, y: P0Y - TH - 2 - Math.floor(idx / cols) * (RH + 2)};
     if (i === 2) return {x: P2X + (idx % cols) * RW, y: P2Y + TH + 2 + Math.floor(idx / cols) * (RH + 2)};
     if (i === 1) return {x: P1X - RH - 2 - Math.floor(idx / cols) * (RH + 2), y: P1Y + (idx % cols) * RW};
     return {x: P3X + TH + 2 + Math.floor(idx / cols) * (RH + 2), y: P3Y + (idx % cols) * RW};
   }

   function gHP(i, idx) {
     if (i === 0) return {x: P0X + idx * (TW + 1), y: P0Y};
     if (i === 2) return {x: P2X + idx * (TW + 1), y: P2Y};
     if (i === 1) return {x: P1X, y: P1Y + idx * (TH + 1)};
     return {x: P3X, y: P3Y + idx * (TH + 1)};
   }

   function dH(c, i, hand, hl) {
     for (var j = 0; j < hand.length; j++) {
       var p = gHP(i, j);
       var rot = i === 1 || i === 3;
       dT(c, p.x, p.y, hand[j], {sel: hl && j === hand.length - 1, w: rot ? TH : TW, h: rot ? TW : TH});
     }
   }

   function dR(c, i, river) {
     for (var j = 0; j < river.length; j++) {
       var p = gRP(i, j);
       dRT(c, p.x, p.y, river[j], i === 1 || i === 3);
     }
   }

   function dSB(c, i, score, riichi, active) {
     var lx = [4, W - 74, W - 74, 4];
     var ly = [P0Y - 32, 4, 4, P0Y - 32];
     var x = lx[i], y = ly[i], w = 70, h = 26;
     c.fillStyle = active ? 'rgba(255,215,0,0.12)' : 'rgba(0,0,0,0.45)';
     rRect(c, x, y, w, h, 3);
     c.fill();
     c.strokeStyle = active ? '#ffd700' : '#555';
     c.lineWidth = active ? 2 : 1;
     rRect(c, x, y, w, h, 3);
     c.stroke();
     c.fillStyle = active ? '#ffd700' : '#ccc';
     c.font = 'bold 11px system-ui';
     c.textAlign = 'center';
     c.textBaseline = 'middle';
     c.fillText('P' + i + (riichi ? ' [R]' : ' ') + score, x + w / 2, y + h / 2);
   }

   function dCI(c, dora, honba, rb, scores) {
     var cx = W / 2, cy = H / 2;
     c.fillStyle = 'rgba(0,0,0,0.55)';
     rRect(c, cx - 90, cy - 38, 180, 76, 6);
     c.fill();
     c.strokeStyle = '#555';
     c.lineWidth = 1;
     rRect(c, cx - 90, cy - 38, 180, 76, 6);
     c.stroke();
     c.fillStyle = '#ffd700';
     c.font = 'bold 12px system-ui';
     c.textAlign = 'center';
     c.fillText('Dora: ' + (dora || []).join(' '), cx, cy - 16);
     c.fillStyle = '#aaa';
     c.font = '11px system-ui';
     c.fillText('\u672c\u573a:' + honba + '  \u7acb\u76f4\u68d2:' + rb, cx, cy + 4);
     c.fillStyle = '#888';
     c.font = '10px system-ui';
     c.fillText((scores || []).join(' | '), cx, cy + 24);
   }

   function drawState(canvas, state, active) {
     var c = canvas.getContext('2d');
     c.clearRect(0, 0, W, H);
     c.fillStyle = '#1a2a1a';
     c.fillRect(0, 0, W, H);
     c.fillStyle = '#12201a';
     rRect(c, 8, 8, W - 16, H - 16, 12);
     c.fill();
     if (!state) return;
     var ps = state.players || [];
     for (var i = 0; i < 4; i++) if (ps[i]) dR(c, i, ps[i].river || []);
     for (var i = 0; i < 4; i++) if (ps[i]) dH(c, i, ps[i].hand || [], i === active);
     for (var i = 0; i < 4; i++) if (ps[i]) dSB(c, i, ps[i].score || 0, ps[i].riichi || false, i === active);
     dCI(c, state.dora || [], state.honba || 0, state.riichibo || 0, state.scores || []);
     var ox = [P0X - 6, W - RH - 10, P2X + TW * 14 + 6, P3X + TH + 6];
     var oy = [P0Y + TH / 2, P1Y + 20, P2Y + TH / 2, P3Y + 20];
     if (state.oya < 4) {
       c.fillStyle = '#ff9944';
       c.font = 'bold 10px system-ui';
       c.textAlign = 'center';
       c.textBaseline = 'middle';
       c.fillText('\u5e84', ox[state.oya], oy[state.oya]);
     }
     if (state.last_action) {
       c.fillStyle = '#666';
       c.font = '10px system-ui';
       c.textAlign = 'center';
       c.textBaseline = 'bottom';
       c.fillText(state.last_action + ' by P' + (state.turn || 0), W / 2, H - 10);
     }
   }

   var Demo = (function() {
     var steps = [];
     var cur = -1, playing = false, iv = null, speed = 600;
     var cv, btnS, btnP, sN, sT, oEl, hE, rE, dE, dpE = [];

     function init() {
       cv = document.getElementById('demo-canvas');
       btnS = document.getElementById('d-btn-start');
       btnP = document.getElementById('d-btn-pause');
       sN = document.getElementById('d-step');
       sT = document.getElementById('d-total');
       oEl = document.getElementById('d-oya');
       hE = document.getElementById('d-honba');
       rE = document.getElementById('d-riichibo');
       dE = document.getElementById('d-dora');
       for (var i = 0; i < 4; i++) dpE.push(document.getElementById('dp-' + i));
       btnS.disabled = true;
       render(-1);
       loadDemoGame().then(function() {
         steps = DEMO_GAME.steps || [];
         sT.textContent = steps.length;
         btnS.disabled = steps.length === 0;
         if (!DEMO_LOAD_ERROR) setDemoStatus('Loaded ' + steps.length + ' steps');
         render(-1);
       });
     }

     function render(idx) {
       var st = idx >= 0 && idx < steps.length ? steps[idx] : null;
       drawState(cv, st, st ? st.turn : -1);
       if (idx >= 0) {
         sN.textContent = idx + ' / ' + steps.length;
         oEl.textContent = 'P' + (st.oya || 0);
         hE.textContent = st.honba || 0;
         rE.textContent = st.riichibo || 0;
         dE.textContent = (st.dora || []).join(' ');
       } else {
         sN.textContent = '0';
         sT.textContent = steps.length;
         oEl.textContent = 'P0';
         hE.textContent = '0';
         rE.textContent = '0';
         dE.textContent = '';
       }
       for (var i = 0; i < 4; i++) dpE[i].className = 'dp' + (i === (st ? st.turn : -1) ? ' active' : '');
       btnS.disabled = idx >= steps.length - 1 || steps.length === 0;
     }

     function sched() {
       clearInterval(iv);
       if (!playing || cur >= steps.length - 1) return;
       iv = setInterval(function() {
         if (cur < steps.length - 1) step();
         else pause();
       }, speed);
     }

     function step() {
       if (cur < steps.length - 1) {
         cur++;
         render(cur);
         sched();
       }
     }

     function start() {
       if (DEMO_LOAD_ERROR || steps.length === 0) return;
       playing = true;
       btnS.disabled = true;
       btnP.disabled = false;
       sched();
     }

     function pause() {
       playing = false;
       clearInterval(iv);
       btnS.disabled = cur >= steps.length - 1 || steps.length === 0;
       btnP.disabled = true;
     }

     function reset() {
       pause();
       cur = -1;
       btnS.disabled = steps.length === 0;
       render(-1);
     }

     function setSpeed(v) {
       speed = parseInt(v, 10);
       if (playing) sched();
     }

     init();
     return {start: start, pause: pause, reset: reset, step: step, setSpeed: setSpeed};
   })();
   </script>

Full Interactive Demo
-----------------------

The live demo above shows a **pre-recorded** 4-AI sample battle.
For the full interactive experience — play against AI yourself, watch 4 AI agents battle in real time, and replay any Tenhou paipu XML — start the web server locally:

.. code-block:: bash

   cd /home/agony/projects/mahjong-dev/web
   pip install -r requirements.txt
   uvicorn server:app --host 0.0.0.0 --port 8000

Then open http://localhost:8000 in your browser.

Features:

- **Human vs AI**: play against 3 AI opponents (random or pretrained VLOG model)
- **4 AI Battle**: watch 4 AI agents compete in real time with adjustable speed
- **Paipu Replay**: load any Tenhou XML paipu file and step through every action
