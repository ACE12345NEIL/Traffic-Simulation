// app.js - Interactive Simulation, Visualization, and Experiment Plots Manager

let animationTimer = null;
let isPlaying = false;
let currentRoadLength = 200;
let currentNumLanes = 2;
let signalPos = 150;

// Tab Switching
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-links a').forEach(el => el.classList.remove('active'));

  const targetTab = document.getElementById(tabId);
  if (targetTab) targetTab.classList.add('active');

  if (tabId === 'sim-tab') document.getElementById('tab-btn-sim')?.classList.add('active');
  if (tabId === 'experiments-tab') {
    document.getElementById('tab-btn-exp')?.classList.add('active');
    loadExperimentPlots();
  }
  if (tabId === 'stability-tab') {
    document.getElementById('tab-btn-stab')?.classList.add('active');
    loadSensitivityData();
  }
  if (tabId === 'comparison-tab') document.getElementById('tab-btn-comp')?.classList.add('active');
}

// Input Value Mirroring
function updateVal(id) {
  const input = document.getElementById(id);
  const display = document.getElementById(`val_${id}`);
  if (input && display) {
    display.textContent = input.value;
  }
}

// Model Selector toggle
function onModelChange() {
  const modelType = document.getElementById('model_type').value;
  const extControls = document.getElementById('extended_controls');
  const baseControls = document.getElementById('baseline_controls');

  if (modelType === 'nasch') {
    extControls.style.display = 'none';
    baseControls.style.display = 'block';
  } else {
    extControls.style.display = 'block';
    baseControls.style.display = 'none';
  }
  initSimulation();
}

// Read current form payload
function getPayload() {
  const modelType = document.getElementById('model_type').value;
  return {
    model_type: modelType,
    road_length: parseInt(document.getElementById('road_length').value),
    density: parseFloat(document.getElementById('density').value),
    slowdown_prob: parseFloat(document.getElementById('slowdown_prob')?.value || 0.3),
    two_wheeler_share: parseFloat(document.getElementById('two_wheeler_share')?.value || 0.4),
    lane_discipline: document.getElementById('lane_discipline')?.value || 'moderate',
    signal_position: parseInt(document.getElementById('signal_position')?.value || 150),
    green_time: parseInt(document.getElementById('green_time')?.value || 30),
    red_time: parseInt(document.getElementById('red_time')?.value || 30),
    simulation_steps: 400,
    warmup_steps: 100,
    random_seed: parseInt(document.getElementById('random_seed').value || 42),
    is_circular: false
  };
}

// Persistent track and vehicle animation state
let vehicleMap = new Map(); // vehId -> { el, pos, lane, type }
let builtTrackConfig = { roadLength: 0, numLanes: 0, signalPos: -1 };

// Initialize Interactive Track
async function initSimulation() {
  pauseSimulation();
  const payload = getPayload();
  try {
    const res = await fetch('/api/simulate/interactive/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    currentRoadLength = data.road_length;
    currentNumLanes = data.num_lanes;
    signalPos = data.signal_position !== undefined ? data.signal_position : -1;

    // Clear existing vehicle actors
    vehicleMap.forEach(record => record.el.remove());
    vehicleMap.clear();
    builtTrackConfig = { roadLength: 0, numLanes: 0, signalPos: -1 };

    renderRoad(data);
    updateMetricsDisplay({
      mean_flow: 0.0,
      mean_speed: data.mean_speed || 0.0,
      mean_travel_time: 0.0,
      mean_queue_length: data.queue_length || 0,
      max_queue_length: data.queue_length || 0,
      completed_trips: 0
    });
  } catch (err) {
    console.error('Failed to init simulation:', err);
  }
}

// Advance simulation by 1 step
async function stepSimulation() {
  try {
    const res = await fetch('/api/simulate/interactive/step', {
      method: 'POST'
    });
    if (!res.ok) {
      pauseSimulation();
      return;
    }
    const data = await res.json();
    renderRoad(data);

    // Update metrics cards live on every step
    updateMetricsDisplay({
      mean_flow: data.flow !== undefined ? data.flow : ((data.active_vehicles || 0) / (data.road_length || 1) * (data.mean_speed || 0)),
      mean_speed: data.mean_speed !== undefined ? data.mean_speed : 0.0,
      mean_travel_time: data.mean_travel_time !== undefined ? data.mean_travel_time : 0.0,
      mean_queue_length: data.queue_length !== undefined ? data.queue_length : 0,
      max_queue_length: data.queue_length !== undefined ? data.queue_length : 0,
      completed_trips: data.completed_count !== undefined ? data.completed_count : (data.completed_trips !== undefined ? data.completed_trips : 0)
    });
  } catch (err) {
    console.error('Step error:', err);
    pauseSimulation();
  }
}

// Build Static Roadway Track and Signal Gantry (Only rebuilt when config changes)
function buildRoadTrack(roadLength, numLanes, signalPosition, cellWidthPx) {
  const container = document.getElementById('road_container');
  if (!container) return;

  container.innerHTML = '';
  container.style.minWidth = `${roadLength * cellWidthPx + 100}px`;

  // 1. Create Lanes and Cells
  for (let l = 0; l < numLanes; l++) {
    const laneDiv = document.createElement('div');
    laneDiv.className = 'lane';
    laneDiv.style.width = `${roadLength * cellWidthPx}px`;

    const label = document.createElement('div');
    label.className = 'lane-label';
    label.textContent = `Lane ${l}`;
    laneDiv.appendChild(label);

    // Render cell grid lines
    for (let c = 0; c < roadLength; c++) {
      const cell = document.createElement('div');
      cell.className = 'cell';
      cell.style.width = `${cellWidthPx}px`;
      cell.dataset.lane = l;
      cell.dataset.pos = c;
      laneDiv.appendChild(cell);
    }

    container.appendChild(laneDiv);
  }

  // 2. Add Stop Line Barrier and Signal Gantry if signalized
  if (signalPosition > 0 && signalPosition < roadLength) {
    const leftPx = signalPosition * cellWidthPx;

    const stopLine = document.createElement('div');
    stopLine.id = 'road_stop_line';
    stopLine.className = 'stop-line-barrier';
    stopLine.style.left = `${leftPx}px`;
    container.appendChild(stopLine);

    const gantry = document.createElement('div');
    gantry.id = 'road_signal_gantry';
    gantry.className = 'signal-gantry';
    gantry.style.left = `${leftPx + 2}px`;
    gantry.innerHTML = `
      <div class="signal-banner">STOP LINE [Cell ${signalPosition}]</div>
      <div class="signal-housing">
        <div class="signal-bulb red" id="signal_bulb_red" title="Red Signal Light"></div>
        <div class="signal-bulb green" id="signal_bulb_green" title="Green Signal Light"></div>
      </div>
      <div class="signal-pole"></div>
    `;
    container.appendChild(gantry);
  }

  // 3. Dynamic Vehicles Layer
  const vehiclesLayer = document.createElement('div');
  vehiclesLayer.id = 'vehicles_layer';
  vehiclesLayer.className = 'vehicles-layer';
  container.appendChild(vehiclesLayer);

  builtTrackConfig = { roadLength, numLanes, signalPos: signalPosition };
}

// Render Road grid and vehicles with smooth hardware-accelerated movement & swerving
function renderRoad(state) {
  const container = document.getElementById('road_container');
  if (!container) return;

  const numLanes = state.num_lanes || 1;
  const roadLength = state.road_length || currentRoadLength;
  const vehicles = state.vehicles || [];
  const signalState = state.signal_state || 'none';
  const signalPosition = state.signal_position !== undefined ? state.signal_position : signalPos;

  // Compute adaptive cell width
  const cellWidthPx = Math.max(16, Math.floor(1150 / roadLength));

  // Rebuild static track only if track dimensions changed
  if (
    builtTrackConfig.roadLength !== roadLength ||
    builtTrackConfig.numLanes !== numLanes ||
    builtTrackConfig.signalPos !== signalPosition
  ) {
    vehicleMap.forEach(record => record.el.remove());
    vehicleMap.clear();
    buildRoadTrack(roadLength, numLanes, signalPosition, cellWidthPx);
  }

  // Update step indicator
  document.getElementById('step_indicator').textContent = `Step: ${state.step || 0}`;

  // Update Signal Status Pill in Legend
  const sigBadge = document.getElementById('signal_status_badge');
  if (sigBadge) {
    if (signalState === 'none') {
      sigBadge.textContent = 'Signal: None (Circular)';
      sigBadge.className = 'signal-pill none';
    } else if (signalState === 'green') {
      sigBadge.textContent = '● Signal: GREEN (GO)';
      sigBadge.className = 'signal-pill green';
    } else {
      sigBadge.textContent = '● Signal: RED (STOP)';
      sigBadge.className = 'signal-pill red';
    }
  }

  // Update Overhead Signal Gantry Bulbs & Stop Line Barrier
  const redBulb = document.getElementById('signal_bulb_red');
  const greenBulb = document.getElementById('signal_bulb_green');
  const stopLine = document.getElementById('road_stop_line');

  if (redBulb && greenBulb && stopLine) {
    if (signalState === 'green') {
      greenBulb.classList.add('active');
      redBulb.classList.remove('active');
      stopLine.classList.add('green-phase');
    } else if (signalState === 'red') {
      redBulb.classList.add('active');
      greenBulb.classList.remove('active');
      stopLine.classList.remove('green-phase');
    } else {
      redBulb.classList.remove('active');
      greenBulb.classList.remove('active');
      stopLine.classList.remove('green-phase');
    }
  }

  // Calculate dynamic transition duration based on playback speed slider
  const playSpeed = parseInt(document.getElementById('play_speed')?.value || 150);
  const transitionMs = isPlaying ? Math.max(50, Math.floor(playSpeed * 0.94)) : 240;

  const vehiclesLayer = document.getElementById('vehicles_layer');
  if (!vehiclesLayer) return;

  const laneHeight = 64;
  const seenVehIds = new Set();

  vehicles.forEach(veh => {
    seenVehIds.add(veh.id);

    const isCar = veh.type !== 'two_wheeler';
    const vehWidth = isCar ? Math.max(16, Math.min(42, cellWidthPx - 2)) : Math.max(12, Math.min(26, cellWidthPx - 4));
    const vehHeight = isCar ? 44 : 32;

    const targetX = veh.pos * cellWidthPx + Math.max(0, (cellWidthPx - vehWidth) / 2);
    const targetY = veh.lane * laneHeight + (laneHeight - vehHeight) / 2;

    if (vehicleMap.has(veh.id)) {
      // Existing vehicle: update position and detect swerving
      const record = vehicleMap.get(veh.id);
      const oldLane = record.lane;
      const oldPos = record.pos;

      // Realistic swerving tilt angle during lane changing
      let swerveDeg = 0;
      if (veh.lane > oldLane) {
        swerveDeg = 7; // Swerving into lower lane
      } else if (veh.lane < oldLane) {
        swerveDeg = -7; // Swerving into upper lane
      }

      // Handle circular track wrap-around seamlessly
      if (veh.pos < oldPos - 10) {
        record.el.style.transition = 'none';
        record.el.style.transform = `translate3d(${-vehWidth}px, ${targetY}px, 0)`;
        void record.el.offsetWidth; // Force synchronous reflow
      }

      // Smooth hardware-accelerated movement & swerve
      record.el.style.transition = `transform ${transitionMs}ms cubic-bezier(0.25, 0.1, 0.25, 1.0), opacity 180ms ease`;
      record.el.style.transform = `translate3d(${targetX}px, ${targetY}px, 0) rotate(${swerveDeg}deg)`;

      // Straighten out after completing the lateral swerve
      if (swerveDeg !== 0) {
        setTimeout(() => {
          if (vehicleMap.has(veh.id)) {
            record.el.style.transform = `translate3d(${targetX}px, ${targetY}px, 0) rotate(0deg)`;
          }
        }, Math.floor(transitionMs * 0.7));
      }

      // Update speed badge
      const badge = record.el.querySelector('.speed-badge');
      if (badge && badge.textContent !== String(veh.speed)) {
        badge.textContent = veh.speed;
      }

      record.pos = veh.pos;
      record.lane = veh.lane;
    } else {
      // New vehicle entering track: instantiate smoothly
      const vEl = document.createElement('div');
      vEl.className = `veh-actor ${isCar ? 'car' : 'two-wheeler'}`;
      vEl.style.width = `${vehWidth}px`;
      vEl.style.height = `${vehHeight}px`;
      vEl.title = `ID: ${veh.id} | Speed: ${veh.speed} | Type: ${veh.type}`;
      vEl.innerHTML = `
        <div class="veh-taillights"><div class="veh-taillight"></div><div class="veh-taillight"></div></div>
        <span class="speed-badge">${veh.speed}</span>
        <div class="veh-headlights"><div class="veh-headlight"></div><div class="veh-headlight"></div></div>
      `;

      // Start slightly behind and slide into cell
      const startX = Math.max(-vehWidth - 5, targetX - (veh.speed || 1) * cellWidthPx);
      vEl.style.transform = `translate3d(${startX}px, ${targetY}px, 0)`;
      vEl.style.opacity = '0';
      vehiclesLayer.appendChild(vEl);

      void vEl.offsetWidth; // Force layout

      vEl.style.transition = `transform ${transitionMs}ms cubic-bezier(0.25, 0.1, 0.25, 1.0), opacity 200ms ease`;
      vEl.style.transform = `translate3d(${targetX}px, ${targetY}px, 0)`;
      vEl.style.opacity = '1';

      vehicleMap.set(veh.id, { el: vEl, pos: veh.pos, lane: veh.lane });
    }
  });

  // Smoothly exit vehicles that completed their trip past the road length
  for (const [id, record] of vehicleMap.entries()) {
    if (!seenVehIds.has(id)) {
      const exitX = roadLength * cellWidthPx + 40;
      const currentY = record.lane * laneHeight + (laneHeight - (record.el.offsetHeight || 44)) / 2;
      record.el.style.transition = 'transform 260ms ease-out, opacity 260ms ease-out';
      record.el.style.transform = `translate3d(${exitX}px, ${currentY}px, 0)`;
      record.el.style.opacity = '0';

      const elToRemove = record.el;
      setTimeout(() => {
        elToRemove.remove();
      }, 280);
      vehicleMap.delete(id);
    }
  }
}

// Toggle Play / Pause
function togglePlay() {
  if (isPlaying) {
    pauseSimulation();
  } else {
    startPlayback();
  }
}

function startPlayback() {
  if (animationTimer) clearInterval(animationTimer);
  isPlaying = true;
  const playBtn = document.getElementById('play_btn');
  if (playBtn) playBtn.textContent = 'Pause';
  const speed = parseInt(document.getElementById('play_speed').value);
  stepSimulation();
  animationTimer = setInterval(stepSimulation, speed);
}

function pauseSimulation() {
  isPlaying = false;
  const playBtn = document.getElementById('play_btn');
  if (playBtn) playBtn.textContent = 'Play';
  if (animationTimer) {
    clearInterval(animationTimer);
    animationTimer = null;
  }
}

function resetSimulation() {
  initSimulation();
}

function onSpeedChange() {
  if (isPlaying) {
    pauseSimulation();
    startPlayback();
  }
}

// Run Full Batch Simulation
async function runBatchSimulation() {
  const payload = getPayload();
  const flowCard = document.getElementById('metric_flow');
  flowCard.textContent = 'Running...';

  try {
    const res = await fetch('/api/simulate/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    if (result.status === 'success') {
      updateMetricsDisplay(result.data);
    } else {
      alert('Simulation error: ' + JSON.stringify(result));
    }
  } catch (err) {
    console.error('Batch error:', err);
    alert('Failed to run batch simulation.');
  }
}

function updateMetricsDisplay(m) {
  document.getElementById('metric_flow').textContent = m.mean_flow !== undefined ? Number(m.mean_flow).toFixed(4) : '--';
  document.getElementById('metric_speed').textContent = m.mean_speed !== undefined ? Number(m.mean_speed).toFixed(2) : '--';
  document.getElementById('metric_travel_time').textContent = m.mean_travel_time !== undefined ? Number(m.mean_travel_time).toFixed(1) : '--';
  document.getElementById('metric_queue').textContent = m.mean_queue_length !== undefined ? Number(m.mean_queue_length).toFixed(1) : 'N/A';
  document.getElementById('metric_max_queue').textContent = m.max_queue_length !== undefined ? m.max_queue_length : 'N/A';
  document.getElementById('metric_trips').textContent = m.completed_trips !== undefined ? m.completed_trips : (m.vehicle_count || '--');
}

// Load and Render Experiment Plots
async function loadExperimentPlots() {
  const container = document.getElementById('plots_container');
  if (!container) return;
  container.innerHTML = '<p>Loading verified experiment plots...</p>';

  try {
    const res = await fetch('/api/plots');
    const plots = await res.json();
    container.innerHTML = '';

    plots.forEach(p => {
      const card = document.createElement('div');
      card.className = 'plot-card';
      card.innerHTML = `
        <h3>${p.title}</h3>
        <a href="${p.url}" target="_blank" title="Click to view full resolution">
          <img src="${p.url}?t=${Date.now()}" alt="${p.title}" class="plot-img">
        </a>
        <p class="plot-desc">Generated from systematic simulation outputs. Click image to expand.</p>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = '<p style="color:red;">Error loading plots. Please run experiments first.</p>';
  }
}

function reloadExperimentPlots() {
  loadExperimentPlots();
}

// Load Sensitivity Data in Tab 3
async function loadSensitivityData() {
  const container = document.getElementById('sensitivity_content');
  if (!container) return;
  try {
    const res = await fetch('/api/experiments/results');
    const data = await res.json();
    const rep = data.sensitivity_repeatability.repeatability;
    const sens = data.sensitivity_repeatability.sensitivity;

    let html = `
      <h3 style="margin-top: 1rem; color: var(--heading-color);">1. Stochastic Repeatability (10 Independent Seeds)</h3>
      <table class="comp-table" style="margin-top: 0.5rem;">
        <thead>
          <tr>
            <th>Output Metric</th>
            <th>Mean (μ)</th>
            <th>Std Dev (σ)</th>
            <th>Coeff. of Variation (CV = σ/μ)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Mean Flow (J)</strong></td>
            <td>${rep.flow.mean}</td>
            <td>${rep.flow.std}</td>
            <td>${(rep.flow.cv * 100).toFixed(2)}%</td>
          </tr>
          <tr>
            <td><strong>Mean Travel Time</strong></td>
            <td>${rep.travel_time.mean} s</td>
            <td>${rep.travel_time.std} s</td>
            <td>${(rep.travel_time.cv * 100).toFixed(2)}%</td>
          </tr>
          <tr>
            <td><strong>Mean Queue Length</strong></td>
            <td>${rep.queue_length.mean} cells</td>
            <td>${rep.queue_length.std} cells</td>
            <td>${(rep.queue_length.cv * 100).toFixed(2)}%</td>
          </tr>
        </tbody>
      </table>

      <h3 style="margin-top: 1.5rem; color: var(--heading-color);">2. Parameter Sensitivity (±20% Perturbations)</h3>
      <table class="comp-table" style="margin-top: 0.5rem;">
        <thead>
          <tr>
            <th>Perturbed Parameter</th>
            <th>Perturbation</th>
            <th>Tested Value</th>
            <th>Mean Flow</th>
            <th>Δ Flow (%)</th>
            <th>Travel Time</th>
            <th>Δ Travel Time (%)</th>
          </tr>
        </thead>
        <tbody>
    `;

    for (const [param, rows] of Object.entries(sens)) {
      rows.forEach(r => {
        html += `
          <tr>
            <td><strong>${param}</strong></td>
            <td>${r.delta_param_pct > 0 ? '+' : ''}${r.delta_param_pct}%</td>
            <td>${r.value}</td>
            <td>${r.flow}</td>
            <td style="color: ${r.delta_flow_pct >= 0 ? '#2e7d32' : '#d32f2f'}">${r.delta_flow_pct > 0 ? '+' : ''}${r.delta_flow_pct}%</td>
            <td>${r.travel_time} s</td>
            <td style="color: ${r.delta_tt_pct <= 0 ? '#2e7d32' : '#d32f2f'}">${r.delta_tt_pct > 0 ? '+' : ''}${r.delta_tt_pct}%</td>
          </tr>
        `;
      });
    }

    html += `
        </tbody>
      </table>
    `;

    container.innerHTML = html;
  } catch (err) {
    console.error('Failed to load sensitivity data:', err);
    container.innerHTML = '<p>Data pending or unavailable.</p>';
  }
}

// Initial Boot
document.addEventListener('DOMContentLoaded', () => {
  initSimulation();
  runBatchSimulation();
});
