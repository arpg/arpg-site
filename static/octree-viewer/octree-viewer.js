/*
 * Interactive voxel viewer for the Octree Diffusion project page.
 *
 * Reads a manifest.json describing a set of scenes, each with three variants
 * (observed / completed / truth) stored as flat binaries of uint8 x,y,z,label
 * records. Renders one variant at a time as a THREE.InstancedMesh so the three
 * can be toggled under a shared camera -- seeing the same viewpoint fill in is
 * the whole argument, and three static panels do not make it.
 *
 * Depends on THREE (r128 global build) and THREE.OrbitControls.
 *
 * Data axes are x, y, z with z up; three.js is y-up, so z maps to world Y.
 */
(function (global) {
  'use strict';

  // Default variant set. A manifest may override it -- the outdoor scenes ship
  // without a `truth` panel because SemanticKITTI's dense voxel ground truth is
  // a separate download we do not have, and inventing one would be a lie.
  var DEFAULT_VARIANTS = [
    { key: 'observed',  label: 'Observed',  hint: 'what the sensor saw' },
    { key: 'completed', label: 'Completed', hint: 'the model’s completion' },
    { key: 'truth',     label: 'Ground truth', hint: 'the real scene' }
  ];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function webglAvailable() {
    try {
      var c = document.createElement('canvas');
      return !!(global.WebGLRenderingContext &&
                (c.getContext('webgl') || c.getContext('experimental-webgl')));
    } catch (e) {
      return false;
    }
  }

  function OctreeViewer(container, opts) {
    this.container = typeof container === 'string'
      ? document.getElementById(container) : container;
    this.opts = opts || {};
    this.base = this.opts.base || '';
    this.cache = {};
    this.variant = 'observed';
    this.cut = 0.6;   // fraction of the volume height kept
    this.manifest = null;
    this.scene_ = null;
    this.mesh = null;
    this.labelOf = null;

    if (!webglAvailable()) { this.failWebGL(); return; }
    var self = this;
    fetch(this.base + 'manifest.json')
      .then(function (r) {
        if (!r.ok) throw new Error('manifest ' + r.status);
        return r.json();
      })
      .then(function (m) {
        self.manifest = m;
        self.variants = m.variants || DEFAULT_VARIANTS;
        self.variant = self.variants[0].key;
        if (m.default_cut != null) self.cut = m.default_cut;
        self.build();
      })
      .catch(function (e) { self.fail('Could not load scene data: ' + e.message); });
  }

  /* ---------------------------------------------------------------- chrome */

  OctreeViewer.prototype.fail = function (msg) {
    this.container.innerHTML = '';
    var box = el('div', 'ov-fallback');
    box.appendChild(el('p', null, msg));
    if (this.opts.fallbackImage) {
      var img = el('img');
      img.src = this.opts.fallbackImage;
      img.alt = 'Scene completion: observed input, model completion, ground truth';
      box.appendChild(img);
    }
    this.container.appendChild(box);
  };

  OctreeViewer.prototype.failWebGL = function () {
    this.fail('This browser has WebGL disabled, so the interactive viewer ' +
              'cannot run. The same three scenes are shown below.');
  };

  OctreeViewer.prototype.build = function () {
    var self = this, m = this.manifest;
    this.container.innerHTML = '';
    this.container.classList.add('ov-root');

    /* --- controls row --- */
    var bar = el('div', 'ov-bar');

    var pick = el('select', 'ov-select');
    m.scenes.forEach(function (s, i) {
      // generation scenes have no observation, so there is no coverage to show
      var label = s.scene.replace(/_/g, ' ');
      if (s.volume_observed != null) {
        label += '  —  ' + Math.round(s.volume_observed * 100) + '% observed';
      } else if (s.classes != null) {
        label += '  —  ' + s.classes + ' classes';
      }
      var o = el('option', null, label);
      o.value = String(i);
      pick.appendChild(o);
    });
    // where there is an observation, open on the best-observed scene
    var best = 0;
    m.scenes.forEach(function (s, i) {
      if ((s.volume_observed || 0) > (m.scenes[best].volume_observed || 0)) best = i;
    });
    pick.value = String(best);
    pick.addEventListener('change', function () { self.loadScene(+pick.value); });
    bar.appendChild(pick);

    var tabs = el('div', 'ov-tabs');
    this.tabButtons = {};
    this.variants.forEach(function (v) {
      var b = el('button', 'ov-tab', v.label);
      b.type = 'button';
      b.title = v.hint;
      b.addEventListener('click', function () { self.setVariant(v.key); });
      tabs.appendChild(b);
      self.tabButtons[v.key] = b;
    });
    bar.appendChild(tabs);

    // A completed room is a closed box: hiding the ceiling is not enough, the
    // near walls still occlude everything. Cutting the volume at a height lets
    // the viewer look in over the top of the walls.
    var cut = el('label', 'ov-check');
    cut.appendChild(el('span', null, 'cut height '));
    var sl = el('input', 'ov-range');
    sl.type = 'range';
    sl.min = '15';
    sl.max = '100';
    sl.value = String(Math.round(this.cut * 100));
    sl.addEventListener('input', function () {
      self.cut = +sl.value / 100;
      self.render_();
    });
    cut.appendChild(sl);
    bar.appendChild(cut);

    this.container.appendChild(bar);

    /* --- canvas --- */
    var stage = el('div', 'ov-stage');
    this.stage = stage;
    this.container.appendChild(stage);

    this.tip = el('div', 'ov-tip');
    this.tip.style.display = 'none';
    stage.appendChild(this.tip);

    this.status = el('div', 'ov-status');
    stage.appendChild(this.status);

    /* --- caption + legend --- */
    this.caption = el('div', 'ov-caption');
    this.container.appendChild(this.caption);
    this.legend = el('div', 'ov-legend');
    this.container.appendChild(this.legend);

    this.initThree();
    this.loadScene(best);
  };

  /* ----------------------------------------------------------------- three */

  OctreeViewer.prototype.initThree = function () {
    var self = this, m = this.manifest, d = m.dims;

    var size = this.measure();
    var w = size[0], h = size[1];

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(global.devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h);
    this.renderer.setClearColor(0xf4f5f7, 1);
    this.stage.appendChild(this.renderer.domElement);

    this.scene_ = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(42, w / h, 0.5, 4000);

    this.camera.position.set(d[0], d[2] * 1.4, d[1]);

    this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.target.set(0, d[2] * 0.25, 0);
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = 0.7;
    this.controls.addEventListener('start', function () {
      self.controls.autoRotate = false;
    });
    this.controls.update();

    this.scene_.add(new THREE.AmbientLight(0xffffff, 0.72));
    var key = new THREE.DirectionalLight(0xffffff, 0.55);
    key.position.set(1, 2, 1.2);
    this.scene_.add(key);
    var fill = new THREE.DirectionalLight(0xffffff, 0.25);
    fill.position.set(-1.2, 0.6, -1);
    this.scene_.add(fill);

    this.geom = new THREE.BoxBufferGeometry(1, 1, 1);
    this.material = new THREE.MeshLambertMaterial();

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.hoverAt = 0;

    this.renderer.domElement.addEventListener('mousemove', function (ev) {
      self.onHover(ev);
    });
    this.renderer.domElement.addEventListener('mouseleave', function () {
      self.tip.style.display = 'none';
    });

    this.stage.style.height = h + 'px';
    this.lastW = w;
    this.lastH = h;
    global.addEventListener('resize', function () { self.resize(); });
    if (global.ResizeObserver) {
      new global.ResizeObserver(function () { self.resize(); }).observe(this.stage);
    } else {
      setTimeout(function () { self.resize(); }, 250);
    }

    // A page can carry several of these. Rendering all of them continuously
    // burns a GPU for no reason, so only the ones on screen animate.
    this.onScreen = true;
    if (global.IntersectionObserver) {
      this.onScreen = false;
      new global.IntersectionObserver(function (entries) {
        self.onScreen = entries[entries.length - 1].isIntersecting;
      }, { rootMargin: '150px' }).observe(this.stage);
    }

    (function loop() {
      global.requestAnimationFrame(loop);
      if (!self.onScreen) return;
      self.controls.update();
      self.renderer.render(self.scene_, self.camera);
    })();
  };

  OctreeViewer.prototype.frame = function (data) {
    var n = data.length / 4, i;
    var lo = [255, 255, 255], hi = [0, 0, 0];
    for (i = 0; i < n; i++) {
      for (var k = 0; k < 3; k++) {
        var v = data[i * 4 + k];
        if (v < lo[k]) lo[k] = v;
        if (v > hi[k]) hi[k] = v;
      }
    }
    var d = this.manifest.dims;
    var cx = d[0] / 2, cy = d[1] / 2;
    // world = (x - cx, z, y - cy)
    var mid = [(lo[0] + hi[0]) / 2 - cx, (lo[2] + hi[2]) / 2, (lo[1] + hi[1]) / 2 - cy];
    // Frame on the footprint, not the longest edge. Extended scenes are long and
    // low; sizing the camera off the full diagonal pushes it far back and steeply
    // down, leaving the scene small and high in the frame.
    var foot = Math.max(hi[0] - lo[0], hi[1] - lo[1]) || 1;
    var tall = (hi[2] - lo[2]) || 1;
    var size = Math.max(foot, tall);

    this.controls.target.set(mid[0], lo[2] + tall * 0.35, mid[2]);
    var dist = foot * 0.95;
    this.camera.position.set(mid[0] + dist * 0.75, lo[2] + tall * 0.5 + dist * 0.42,
                             mid[2] + dist * 0.75);
    this.camera.near = Math.max(size / 200, 0.1);
    this.camera.far = size * 12;
    this.camera.updateProjectionMatrix();
    this.controls.update();

    if (this.grid) this.scene_.remove(this.grid);
    this.grid = new THREE.GridHelper(size * 1.6, 8, 0xc9ccd2, 0xe2e5ea);
    this.grid.position.set(mid[0], lo[2] - 0.5, mid[2]);
    this.scene_.add(this.grid);
  };

  OctreeViewer.prototype.measure = function () {
    var w = this.stage.clientWidth || this.container.clientWidth || 800;
    var max = this.opts.height || 460;
    // keep a sane aspect on narrow screens instead of a letterbox slot
    var h = Math.round(Math.min(max, Math.max(260, w * 0.58)));
    return [w, h];
  };

  OctreeViewer.prototype.resize = function () {
    var s = this.measure(), w = s[0], h = s[1];
    if (!w || (w === this.lastW && h === this.lastH)) return;
    this.lastW = w;
    this.lastH = h;
    this.stage.style.height = h + 'px';
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  };

  /* ------------------------------------------------------------------ data */

  OctreeViewer.prototype.fetchVariant = function (sceneIdx, key) {
    var self = this;
    var v = this.manifest.scenes[sceneIdx].variants[key];
    var url = this.base + v.file;
    if (this.cache[url]) return Promise.resolve(this.cache[url]);
    return fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error(v.file + ' ' + r.status);
        return r.arrayBuffer();
      })
      .then(function (buf) {
        var a = new Uint8Array(buf);
        if (a.length !== v.count * 4) {
          throw new Error(v.file + ': expected ' + v.count * 4 +
                          ' bytes, got ' + a.length);
        }
        self.cache[url] = a;
        return a;
      });
  };

  OctreeViewer.prototype.loadScene = function (idx) {
    var self = this;
    this.sceneIdx = idx;
    this.busy('loading…');
    // frame on the ground truth, not the current variant: the camera must not
    // jump when the observed/completed/truth toggle changes what is drawn
    var anchor = this.variants[this.variants.length - 1].key;
    this.fetchVariant(idx, anchor)
      .then(function () { self.frame(self.cache[self.base +
        self.manifest.scenes[idx].variants[anchor].file]); })
      .then(function () { return self.fetchVariant(idx, self.variant); })
      .then(function () {
        self.busy(null);
        self.render_();
        // the toggle should feel instant, so pull the others in behind it
        self.variants.forEach(function (v) {
          if (v.key !== self.variant) self.fetchVariant(idx, v.key).catch(function () {});
        });
      })
      .catch(function (e) { self.busy('failed: ' + e.message); });
  };

  OctreeViewer.prototype.setVariant = function (key) {
    var self = this;
    this.variant = key;
    this.busy('loading…');
    this.fetchVariant(this.sceneIdx, key)
      .then(function () { self.busy(null); self.render_(); })
      .catch(function (e) { self.busy('failed: ' + e.message); });
  };

  OctreeViewer.prototype.busy = function (msg) {
    this.status.textContent = msg || '';
    this.status.style.display = msg ? 'block' : 'none';
  };

  /* --------------------------------------------------------------- drawing */

  OctreeViewer.prototype.render_ = function () {
    var m = this.manifest, d = m.dims;
    var v = m.scenes[this.sceneIdx].variants[this.variant];
    var data = this.cache[this.base + v.file];
    if (!data) return;

    if (this.mesh) {
      this.scene_.remove(this.mesh);
      this.mesh.dispose();
      this.mesh = null;
    }

    var zmax = Math.round(this.cut * (d[2] - 1));
    var n = data.length / 4;

    // count first so the InstancedMesh is allocated exactly once
    var keep = 0, i;
    for (i = 0; i < n; i++) {
      if (data[i * 4 + 2] <= zmax) keep++;
    }
    if (!keep) { this.updateCaption(0, {}); return; }

    var mesh = new THREE.InstancedMesh(this.geom, this.material, keep);
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    var mat = new THREE.Matrix4();
    var col = new THREE.Color();
    var pal = m.palette;
    var labels = new Uint8Array(keep);
    var counts = {};
    var cx = d[0] / 2, cy = d[1] / 2;
    var j = 0;

    for (i = 0; i < n; i++) {
      if (data[i * 4 + 2] > zmax) continue;
      var lab = data[i * 4 + 3];
      // data z is up; three.js is y-up
      mat.setPosition(data[i * 4] - cx, data[i * 4 + 2], data[i * 4 + 1] - cy);
      mesh.setMatrixAt(j, mat);
      var p = pal[lab] || [128, 128, 128];
      col.setRGB(p[0] / 255, p[1] / 255, p[2] / 255);
      mesh.setColorAt(j, col);
      labels[j] = lab;
      counts[lab] = (counts[lab] || 0) + 1;
      j++;
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.frustumCulled = false;

    this.mesh = mesh;
    this.labelOf = labels;
    this.scene_.add(mesh);

    this.variants.forEach(function (vv) {
      this.tabButtons[vv.key].classList.toggle('is-on', vv.key === this.variant);
    }, this);

    this.updateCaption(keep, counts);
  };

  /* -------------------------------------------------------- caption/legend */

  OctreeViewer.prototype.updateCaption = function (shown, counts) {
    var m = this.manifest, s = m.scenes[this.sceneIdx];
    var bits = ['<strong>' + s.scene.replace(/_/g, ' ') + '</strong>'];
    if (s.volume_observed != null) {
      bits.push(Math.round(s.volume_observed * 100) + '% of the volume observed');
    }
    if (s.classes != null) bits.push(s.classes + ' classes');
    bits.push(shown.toLocaleString() + ' voxels drawn');
    this.caption.innerHTML = bits.join(' &nbsp;·&nbsp; ');

    var top = Object.keys(counts)
      .map(function (k) { return [+k, counts[k]]; })
      .sort(function (p, q) { return q[1] - p[1]; })
      .slice(0, 12);

    this.legend.innerHTML = '';
    top.forEach(function (t) {
      var p = m.palette[t[0]] || [128, 128, 128];
      var chip = el('span', 'ov-chip');
      var sw = el('i');
      sw.style.background = 'rgb(' + p[0] + ',' + p[1] + ',' + p[2] + ')';
      chip.appendChild(sw);
      chip.appendChild(el('span', null, m.class_names[t[0]] + ' (' +
                                        t[1].toLocaleString() + ')'));
      this.legend.appendChild(chip);
    }, this);
  };

  /* ----------------------------------------------------------------- hover */

  OctreeViewer.prototype.onHover = function (ev) {
    // raycasting an InstancedMesh tests every instance, so throttle hard
    var now = Date.now();
    if (now - this.hoverAt < 60) return;
    this.hoverAt = now;
    if (!this.mesh) return;

    var r = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    this.pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);

    var hit = this.raycaster.intersectObject(this.mesh, false)[0];
    if (!hit || hit.instanceId == null) {
      this.tip.style.display = 'none';
      return;
    }
    var lab = this.labelOf[hit.instanceId];
    this.tip.textContent = this.manifest.class_names[lab];
    this.tip.style.display = 'block';
    this.tip.style.left = (ev.clientX - r.left + 12) + 'px';
    this.tip.style.top = (ev.clientY - r.top + 12) + 'px';
  };

  global.OctreeViewer = OctreeViewer;
})(window);
