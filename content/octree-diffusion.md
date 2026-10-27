---
title: "Octree Diffusion: Semantic Scene Generation and Completion"
title_main: "Octree Diffusion:"
title_follow: "Semantic Scene Generation and Completion"
layout: paper
description: "A single octree-latent diffusion framework for 3D semantic scene generation, completion and extension, indoors and outdoors. ICRA 2026."
authors:
  - "Xujia Zhang"
  - "Brendan Crowe"
  - "Christoffer Heckman"
links:
  - { url: "https://arxiv.org/abs/2509.16483", text: "ArXiv" }
  - { url: "https://arxiv.org/pdf/2509.16483", text: "PDF" }
  - { url: "https://github.com/XUJIAZHANG2002/Octree-Scene-Diffusion", text: "Code" }
news:
  - "2026-06-05 Presented at [ICRA 2026 in Vienna](/news/2026-06-05-icra-2026/)."
  - "2026-03-31 Camera-ready on arXiv: [arXiv:2509.16483](https://arxiv.org/abs/2509.16483)."
  - "2026-01-31 Accepted to ICRA 2026."
---

<link rel="stylesheet" href="/octree-viewer/octree-viewer.css">

<p>Generating a 3D semantic scene, completing one from a partial sensor reading, and
extending one past its edges are usually three separate models, usually built for one
domain at a time &mdash; indoor <em>or</em> outdoor. <strong>Octree Latent Semantic
Diffusion</strong> does all three with one framework, in both domains, and only the
first requires training. Completion and extension are inference-time operations on the
same weights.</p>

<p>The move that makes this tractable is to stop treating a scene as a dense voxel grid.
Scenes are mostly empty: a <code>128&times;128&times;64</code> indoor patch is about 92%
free space, and outdoor LiDAR volumes are emptier still. We represent the scene as a
<strong>dual octree graph</strong> &mdash; hierarchical, sparse, memory-efficient &mdash;
so the model spends capacity only where there is geometry. Synthesis then factors into
two stages: <strong>structure diffusion</strong> predicts the binary split signals that
build a coarse occupancy octree (<em>where</em> surfaces are), and <strong>latent
semantic diffusion</strong> generates embeddings that a graph VAE decodes into per-voxel
labels (<em>what</em> they are).</p>

<div style="overflow:auto;text-align:center">
  <img src="/img/octree-diffusion/method_overview.png" alt="Method overview: a semantic scene and a partial LiDAR scan are encoded to structure and semantic latents, completed by masked diffusion, and decoded back to a labelled scene.">
</div>

<p>Everything below is output from the released models, exactly as it came out: no
post-processing. Each scene was picked by eye from a larger batch of draws &mdash; 300 for
outdoor generation, 20 to 42 for each of the other sets &mdash; ranked by automatic
scores for realism and, for completion and extension, for how much of the input each draw
keeps. Drag to orbit, scroll to zoom, hover a voxel to name its class. On the indoor
scenes, <em>cut height</em> slices away the ceiling and upper walls so you can see
inside.</p>

<h2 id="generation">1. Generation</h2>

<p>With nothing to condition on, the two stages produce whole scenes from noise. Indoors
that means floors, walls and ceilings in the right relationship, with furniture standing
on the floor; outdoors, road and sidewalk under buildings and vegetation.</p>

<div id="viewer-gen-indoor"></div>
<p style="text-align:center;font-size:.9rem;color:var(--cu-light-gray)">Replica &mdash; unconditional samples</p>

<div id="viewer-gen-kitti"></div>
<p style="text-align:center;font-size:.9rem;color:var(--cu-light-gray)">SemanticKITTI &mdash; unconditional samples</p>

<div style="overflow:auto;text-align:center">
  <img src="/img/octree-diffusion/generation_grid.png" alt="Six unconditionally generated scenes: four Replica rooms with the ceiling cut away, and two SemanticKITTI streets.">
</div>

<p>Because structure and semantics are separate stages, the geometry can be held fixed
while only the semantic diffusion is resampled. What comes back is mostly the same room:
across four labellings of one layout below, 6% of the voxels the draws share change
label, and the wall, floor and ceiling counts move by under 6%. The variation is in the
smaller objects. That is the behaviour to want &mdash; a surface the structure stage put
where a wall goes should keep coming back a wall &mdash; but it does mean the split
buys reusable geometry rather than a free source of diversity.</p>

<div style="overflow:auto;text-align:center">
  <img src="/img/octree-diffusion/one_layout_many_labellings.png" alt="Four panels of one generated layout, each with the semantic stage resampled; the room is the same and the small objects differ.">
</div>

<h2 id="completion">2. Semantic scene completion</h2>

<p>Voxelise a sensor reading, treat it as a known region, and complete the rest. No
retraining, no fine-tuning, no conditioning branch &mdash; the observation enters at
inference time only.</p>

<p>How it enters is worth stating, because the two stages need different treatment.
The structure stage is conditioned directly: the known region is held fixed at every
diffusion step and the model fills the rest. Indoors, several layouts are sampled and
the one that agrees best with the observation is kept, which needs no ground truth. The
semantic latents cannot be pinned that way, because the encoder is a graph network over
voxel patches, so a node's latent is not a function of its own patch. Outdoors, encode a
scan's labels and even the nodes whose entire patch was observed come back a median 61%
away from where the full labels would put them; indoors, pinning latents encoded from a
single view kept only 59&ndash;82% of the observed labels. So in both domains the
observation is applied instead as a gradient step in decoded label space, measured at
the voxels the sensor actually saw. The completions shown keep at least 99% of the
observed voxels and 98% of their labels.</p>

<p>Indoors the input is a single viewpoint, so most of the room is shadow. Toggle between
what the sensor saw, the completion, and the ground truth; the camera holds still so the
three line up.</p>

<div id="viewer-comp-indoor"></div>

<p>Outdoors the input is one voxelised LiDAR sweep. Ray-tracing each return back to the
sensor clears the space it passed through, so the observation covers 7&ndash;13% of the
volume &mdash; a few percent of it returns, the rest observed empty &mdash; and the same
three-way toggle applies. The frames are from sequence 08, which the model never saw in
training; scans 000133 and 000149 are the same street 1.6 seconds apart. The ground
truth is SemanticKITTI's own dense voxel labels. Read it knowing that it is itself
incomplete: voxels the benchmark marks invalid &mdash; outside the sensor's traversal,
where no label is defined &mdash; are drawn as empty. That is a mean 29% of a volume
across the dataset and 10&ndash;21% of these four frames, so where the completion fills
space the ground truth leaves empty, the ground truth may simply have no label there.</p>

<div id="viewer-comp-kitti"></div>

<div style="overflow:auto;text-align:center">
  <img src="/img/octree-diffusion/completion_triptych.png" alt="Three panels of SemanticKITTI sequence 08, scan 000149: the voxelised LiDAR sweep at 14,565 visible voxels, the completion at 131,391, and the ground truth at 148,564.">
</div>

<h2 id="extension">3. Scene extension</h2>

<p>The same mechanism run outward instead of inward. Hold roughly three quarters of a
scene fixed and outpaint the remainder, then slide the window and repeat &mdash; scenes
grow indefinitely along an axis, each new section conditioned on the one before it.</p>

<div id="viewer-ext-indoor"></div>
<p style="text-align:center;font-size:.9rem;color:var(--cu-light-gray)">Replica &mdash; grown from 128 to 256 voxels along +x</p>

<div id="viewer-ext-kitti"></div>
<p style="text-align:center;font-size:.9rem;color:var(--cu-light-gray)">SemanticKITTI &mdash; the last quarter of a held-out frame outpainted from its ground truth</p>

<div style="overflow:auto;text-align:center">
  <img src="/img/octree-diffusion/extension.png" alt="Two panels: a Replica apartment at 83,920 visible voxels, and the same scene outpainted along the positive x axis to 166,877.">
</div>

<h2 id="method">How it works</h2>

<p>The semantic branch is a <strong>patch VAE</strong>. A shared patch encoder compresses
every non-empty patch of the semantic voxel map and builds an octree in the compressed
space; that becomes a dual octree graph, which a graph VAE encodes to a latent at a
shallower depth. The decoder predicts a split signal for each node at the finest depth,
reconstructs the latent graph, and a shared patch decoder turns it back into a semantic
voxel map. Diffusion happens entirely in that latent graph space.</p>

<div style="overflow:auto;text-align:center">
  <img src="/img/octree-diffusion/patch_vae.png" alt="The patch VAE pipeline: input, patch encoder, patched latent graph, graph VAE encoder, latent graph, graph VAE decoder, reconstructed latent graph, patch decoder, output.">
</div>

<h2 id="results">Results</h2>

<p>Because the model is generative rather than a per-voxel predictor, we evaluate it on
how closely the distribution of generated scenes matches the distribution of real ones,
using FID, KID and MMD against each validation set. Voxel-wise accuracy against one
particular ground-truth scene is not the right instrument: a completion can be entirely
plausible and still disagree voxel for voxel with the specific room behind the sensor.</p>

<p>Numbers below are from the paper. On SemanticKITTI, KID is scaled by
10<sup>3</sup>:</p>

<table>
  <thead><tr><th>Method</th><th>FID ↓</th><th>KID ↓</th><th>MMD ↓</th></tr></thead>
  <tbody>
    <tr><td>2-stage generation (ours)</td><td>0.2107</td><td>8.8700</td><td>0.1856</td></tr>
    <tr><td>Semantic generation (ours)</td><td>0.0289</td><td>0.7622</td><td>0.0265</td></tr>
    <tr><td>Semantic completion (ours)</td><td><strong>0.0353</strong></td><td><strong>0.6980</strong></td><td><strong>0.0216</strong></td></tr>
    <tr><td>SemCity (baseline)</td><td>0.0940</td><td>2.2256</td><td>0.0773</td></tr>
  </tbody>
</table>

<p>On Replica, FID, KID and MMD are scaled by 10<sup>4</sup>, 10<sup>5</sup> and
10<sup>4</sup> respectively:</p>

<table>
  <thead><tr><th>Method</th><th>FID ↓</th><th>KID ↓</th><th>MMD ↓</th></tr></thead>
  <tbody>
    <tr><td>2-stage generation (ours)</td><td>0.8671</td><td>0.5245</td><td>0.2837</td></tr>
    <tr><td>Semantic generation (ours)</td><td><strong>0.0486</strong></td><td><strong>0.1193</strong></td><td><strong>0.0668</strong></td></tr>
    <tr><td>SceneSense (baseline)</td><td>31.0950</td><td>89.7884</td><td>47.8399</td></tr>
    <tr><td>SemCity (baseline)</td><td>50.2789</td><td>187.2540</td><td>99.5552</td></tr>
  </tbody>
</table>

<p><strong>A note on the indoor weights in the public repo.</strong> The originals used
for the paper were lost, and the released indoor checkpoints are a retrain following the
same recipe with class-weighted semantics. The scenes rendered above come from that
retrain, so they are representative of what you get from the repo rather than
bit-identical to the paper's figures.</p>

<h2 id="code">Code</h2>

<p>Implementation, pretrained weights and notebooks:
<a href="https://github.com/XUJIAZHANG2002/Octree-Scene-Diffusion">github.com/XUJIAZHANG2002/Octree-Scene-Diffusion</a>.
Both halves of the paper run from one command-line entry point:</p>

<pre><code>octree-diff generate --num-samples 8 --out out/gen
octree-diff complete --input scene.pt --known-mask known.pt --best-of 64
octree-diff extend   --input scene.pt --steps-out 4
</code></pre>

<h2 id="citation">Citation</h2>

<pre><code>@inproceedings{zhang2026octree,
  title     = {Octree Diffusion for Semantic Scene Generation and Completion},
  author    = {Zhang, Xujia and Crowe, Brendan and Heckman, Christoffer},
  booktitle = {2026 IEEE International Conference on Robotics and Automation (ICRA)},
  year      = {2026}
}
</code></pre>

<script src="/octree-viewer/three.min.js"></script>
<script src="/octree-viewer/OrbitControls.js"></script>
<script src="/octree-viewer/octree-viewer.js"></script>
<script>
  [
    ['viewer-gen-indoor',  '/octree-viewer/scenes/indoor-generation/'],
    ['viewer-gen-kitti',   '/octree-viewer/scenes/kitti-generation/'],
    ['viewer-comp-indoor', '/octree-viewer/scenes/indoor-completion/'],
    ['viewer-comp-kitti',  '/octree-viewer/scenes/kitti-completion/'],
    ['viewer-ext-indoor',  '/octree-viewer/scenes/indoor-extension/'],
    ['viewer-ext-kitti',   '/octree-viewer/scenes/kitti-extension/']
  ].forEach(function (v) {
    if (document.getElementById(v[0])) {
      new OctreeViewer(v[0], {
        base: v[1], height: 460,
        fallbackImage: '/img/octree-diffusion/completion_triptych.png'
      });
    }
  });
</script>
