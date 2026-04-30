.. _demo:

Live Demo
=========

Try pymahjong without installing anything. The preview below now reuses the same table renderer style as the main web frontend, so the documentation demo no longer drifts visually from the actual UI.

4 AI Sample Replay
------------------

This is a short pre-recorded browser replay. It uses a fixed logical table size and proportional scaling, so it should remain stable across desktop and mobile widths.

.. raw:: html

   <style>
   .demo-shell {
     margin: 1.5rem 0;
     padding: 1rem;
     border-radius: 18px;
     background:
       radial-gradient(circle at top, rgba(31, 84, 59, 0.25), transparent 42%),
       linear-gradient(180deg, #13271f, #0d1613);
     border: 1px solid rgba(255, 255, 255, 0.08);
     box-shadow: 0 18px 46px rgba(0, 0, 0, 0.24);
   }
   .demo-shell canvas {
     display: block;
     width: 100%;
     height: auto;
     margin: 0 auto;
     background: transparent;
   }
   .demo-meta {
     display: flex;
     justify-content: space-between;
     gap: 0.75rem;
     flex-wrap: wrap;
     margin-top: 0.9rem;
     color: #d8d0bf;
     font-size: 0.92rem;
   }
   .demo-controls {
     display: flex;
     gap: 0.55rem;
     flex-wrap: wrap;
     align-items: center;
     margin-top: 0.9rem;
   }
   .demo-controls button {
     border: 1px solid rgba(255, 255, 255, 0.18);
     background: rgba(255, 255, 255, 0.06);
     color: #f6f1e6;
     border-radius: 999px;
     padding: 0.42rem 0.85rem;
     font-size: 0.9rem;
     cursor: pointer;
   }
   .demo-controls button:hover {
     background: rgba(255, 255, 255, 0.12);
   }
   .demo-controls input[type="range"] {
     width: min(280px, 58vw);
   }
   .demo-note {
     margin-top: 0.85rem;
     color: #cbbda1;
     font-size: 0.88rem;
   }
   </style>

   <div class="demo-shell">
     <canvas id="docs-demo-canvas" width="1600" height="1000"></canvas>
     <div class="demo-meta">
       <span id="docs-demo-round">东一局 · 本场 0 · 供托 0</span>
       <span id="docs-demo-step">Step 0 / 0</span>
     </div>
     <div class="demo-controls">
       <button type="button" id="docs-demo-play">Play</button>
       <button type="button" id="docs-demo-pause">Pause</button>
       <button type="button" id="docs-demo-reset">Reset</button>
       <label for="docs-demo-speed">Speed</label>
       <input id="docs-demo-speed" type="range" min="180" max="1600" value="680" step="20" />
       <span id="docs-demo-speed-value">680 ms</span>
     </div>
     <div class="demo-note" id="docs-demo-status">Loading replay data…</div>
   </div>

   <script>
   window.__MAHJONG_TILE_ASSET_ROOT__ = '_static/demo_assets/tiles/Regular';
   </script>
   <script src="_static/demo_renderer.js"></script>
   <script src="_static/demo_embed.js"></script>

What This Demo Shows
--------------------

- The same board proportions, rivers, meld layout, dora area, honba/kyoutaku sticks, and seat badges used by the current web frontend.
- Responsive scaling without reflowing the Mahjong layout logic.
- A documentation-safe static replay source, so the page works on GitHub Pages without needing a live backend.

See Also
--------

- :doc:`web_frontend`
- :doc:`advanced/shanten_calculation`
