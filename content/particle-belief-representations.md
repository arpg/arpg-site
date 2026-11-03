---
title: "Particle Belief Representations for Reinforcement Learning under Partial Observability"
title_main: "Particle Belief Representations"
title_follow: "for Reinforcement Learning under Partial Observability"
layout: paper
# Draft until the paper is public: it is under double-blind review, and a public page
# with the author list would break anonymity. Flip to false (and add the publication-list
# entry) once the arXiv version is out.
draft: true
description: "A controlled study of how particle-filter beliefs should be encoded for reinforcement learning: statistical summaries, cumulant-generating-function features and permutation-invariant set encoders, trained end-to-end or pretrained, across eight partially observable tasks."
authors:
  - "Himanshu Gupta*"
  - "Brendan Crowe*"
  - "Christoffer Heckman"
  - "Bradley Hayes"
  - "Zachary Sunberg"
author_note: "\\* Equal contribution"
links:
  - { url: "https://github.com/brendanjcrowe/set_transformer", text: "Code" }
  - { url: "https://github.com/brendanjcrowe/pomdp-domains", text: "Environments" }
news:
  - "2026-10 Under review."
---

<p>Under partial observability an agent acts on a <em>belief</em> &mdash; a distribution
over the states it might be in &mdash; rather than on the state itself. Particle filters
are the standard way to track a belief that is multimodal or shaped by nonlinear
dynamics: they represent it as a weighted set of point estimates,
<em>b<sub>t</sub></em> = {(<em>x<sub>t</sub><sup>i</sup></em>,
<em>w<sub>t</sub><sup>i</sup></em>)}<sub><em>i</em>=1</sub><sup><em>N</em></sup>.
That set is exactly what a reinforcement-learning policy cannot take as input. It is
unordered and potentially variable in size, while a policy network expects a fixed-length
vector.</p>

<p>The usual workarounds each give something up. Flattening the particles imposes an
arbitrary order and ties the policy to one particle count. Sorting them substitutes a
hand-designed order that can be discontinuous. Compressing the belief to its mean and
covariance is cheap, but beliefs that call for entirely different actions &mdash; one
tight mode, or two well-separated ones &mdash; can share the same low-order statistics.
The encoding decides which beliefs a policy can tell apart, so it is not an
implementation detail.</p>

<p>We study it as a problem in its own right: <strong>what are the most effective
particle-belief encodings for reinforcement learning, and how should they be
built?</strong></p>

<div style="overflow:auto;text-align:center">
  <img src="/img/particle-belief-representations/system_overview.png" alt="System overview: a POMDP environment feeds a fixed particle filter, whose weighted, unordered particle set passes through a belief encoder to an RL policy. The encoder is a statistical summary, CGF features, or a set network, and is trained end-to-end or pretrained offline by belief reconstruction or task-specific prediction, then frozen or fine-tuned.">
</div>

<p>Everything except the encoder is held fixed. Within a task, every condition sees the
same particle filter, the same observation branch, the same policy and value networks,
and the same PPO configuration. Only the map from the weighted particle set to a
fixed-length code changes, along with how that map is trained.</p>

<h2 id="encoders">Encoders</h2>

<ul>
  <li><strong>Statistical summaries.</strong> The weighted mean and covariance
  (<em>Gaussian</em>), or the mean plus central moments through order eight
  (<em>Moments</em>). Cheap and permutation-invariant, but blind to anything beyond
  those statistics.</li>
  <li><strong>Cumulant-generating-function features.</strong> The empirical CGF,
  <em>K</em>(<em>t</em>) = log &Sigma;<sub><em>i</em></sub> <em>w<sub>i</sub></em>
  e<sup><em>t</em>&middot;<em>x<sub>i</sub></em></sup>, evaluated at 64 probe locations,
  or its gradient &nabla;<em>K</em>, which is the particle mean under exponentially
  tilted weights. Derivatives at the origin recover the cumulants, so evaluating away from
  the origin captures structure that a fixed list of moments misses. Probes are either
  fixed or learned, and the representation stays compact.</li>
  <li><strong>Set networks.</strong> <em>Deep Sets</em> pools per-particle features with a
  weighted sum and <em>PointNet</em> with a max; the two are otherwise matched, isolating
  the pooling operation. The <em>Set Transformer</em> lets particles attend to one another
  before attention-based pooling. All three produce a 64-dimensional code at comparable
  parameter counts.</li>
  <li><strong>Frame stacking.</strong> A history baseline that skips the belief entirely
  and concatenates the most recent raw observations.</li>
</ul>

<p>Each trainable encoder is learned three ways: <strong>end-to-end</strong>, from a random
start by PPO alone; or <strong>pretrained</strong> offline and then transferred either
<strong>frozen</strong> or <strong>fine-tuned</strong> at a tenth of the policy's learning
rate. Pretraining uses one of two objectives: <em>belief reconstruction</em>, a set
decoder trained to redraw the particle set under a Sinkhorn loss, or <em>task-specific
prediction</em>, a head trained to predict a decision-relevant label. Either can take an
optional <em>latent metric alignment</em> term that pulls distances between codes toward
distances between the beliefs they encode.</p>

<h2 id="tasks">Eight tasks, three kinds of belief</h2>

<div style="overflow:auto;text-align:center">
  <img src="/img/particle-belief-representations/task_suite.png" alt="The eight evaluation tasks with example particle beliefs: Car-Flag; Ant Tag, Lantern Ant Tag and Hideout Ant Tag; Odd-Even's comb-shaped posterior; and the three beacon tasks, Beacon Sweep, Faint Beacon and Diffuse Beacon. Marker area is proportional to particle weight.">
</div>

<p>The tasks are grouped by what the policy has to extract from the belief.</p>

<p><strong>Active information gathering</strong> &mdash; Car&ndash;Flag and three Ant Tag
variants, adapted from established robot POMDP domains. The agent has to move to reduce its
own uncertainty. In Car&ndash;Flag a hidden bit selects the rewarding end of a track and is
revealed in an intermediate region. In the Ant Tag variants a MuJoCo ant must find and tag
an evasive target tracked by a particle filter. <em>Lantern Ant Tag</em> shrinks the
sensing radius so the target stays unseen for most of an episode. <em>Hideout Ant Tag</em>
is moment-matched by construction: the target hides in one of two den configurations that
are point reflections of each other, so both share a mean and covariance while differing
as distributions, and the inactive dens are terminal hazards.</p>

<p><strong>Beacon tasks</strong> &mdash; three new search-and-rescue environments on a
shared 20&times;20 arena with five survivors carrying radio beacons. <em>Beacon Sweep</em>
rewards reaching all five. <em>Faint Beacon</em> and <em>Diffuse Beacon</em> allow a single
rescue, of the one buried survivor, whose beacon either transmits least often (the mode
with the least mass) or gives the noisiest fixes (the mode with the greatest spread). The
three tasks isolate coverage, mass comparison and scale comparison on identical state and
action spaces.</p>

<p><strong>Odd&ndash;Even</strong> &mdash; a hidden integer from 1 to 50, observed through
noise that preserves its parity. The posterior is a comb over one parity and the agent is
rewarded only for an exact guess, so mean and variance &mdash; which capture location and
spread but not the comb &mdash; can conflate beliefs that put mass on different
integers.</p>

<h3 id="rollouts">Example rollouts</h3>

<p>Each task in motion, under a simple hand-written policy that acts on the belief (not a
trained agent). Blue markers are belief particles, with area proportional to weight; the
orange star is the hidden target, shown here for the viewer only.</p>

<div class="rollouts cols-2">
  <figure><img loading="lazy" src="/img/particle-belief-representations/rollouts/car_flag.gif" alt="Car-Flag rollout: the car drives to the information region, its belief over which end is rewarding collapses from two groups of particles to one, and it turns back to the correct flag."><figcaption>Car&ndash;Flag: visit the info region, then commit.</figcaption></figure>
  <figure><img loading="lazy" src="/img/particle-belief-representations/rollouts/odd_even.gif" alt="Odd-Even rollout: the comb-shaped posterior over one parity sharpens with each noisy observation while the agent guesses its most likely integer."><figcaption>Odd&ndash;Even: guess the posterior's mode each step.</figcaption></figure>
</div>

<div class="rollouts cols-3">
  <figure><img loading="lazy" src="/img/particle-belief-representations/rollouts/beacon_sweep.gif" alt="Beacon Sweep rollout: the agent visits the nearest belief cluster in turn; each survivor reached is removed from the belief until all five are found."><figcaption>Beacon Sweep: reach all five survivors.</figcaption></figure>
  <figure><img loading="lazy" src="/img/particle-belief-representations/rollouts/faint_beacon.gif" alt="Faint Beacon rollout: the agent picks the cluster with the fewest particles and steers around the others to reach it."><figcaption>Faint Beacon: the lightest mode.</figcaption></figure>
  <figure><img loading="lazy" src="/img/particle-belief-representations/rollouts/diffuse_beacon.gif" alt="Diffuse Beacon rollout: the agent picks the most spread-out cluster and steers around the others to reach it."><figcaption>Diffuse Beacon: the widest mode.</figcaption></figure>
</div>

<div class="rollouts">
  <figure><img loading="lazy" src="/img/particle-belief-representations/rollouts/ant_tag.gif" alt="Ant Tag rollout: the MuJoCo scene beside the particle belief; the ant searches toward the densest part of the belief until it sees and tags the evading target."><figcaption>Ant Tag: the MuJoCo scene (left) and the particle belief (right).</figcaption></figure>
  <figure><img loading="lazy" src="/img/particle-belief-representations/rollouts/lantern_ant_tag.gif" alt="Lantern Ant Tag rollout: the same task with a smaller sensing radius, so the target stays unseen for longer."><figcaption>Lantern Ant Tag: a smaller sensing radius.</figcaption></figure>
  <figure><img loading="lazy" src="/img/particle-belief-representations/rollouts/hideout_ant_tag.gif" alt="Hideout Ant Tag rollout: the belief splits between a near and a far den; the ant heads for the heavier den, avoiding the hatched phantom dens, and tags the target."><figcaption>Hideout Ant Tag: hatched circles are terminal phantom dens.</figcaption></figure>
</div>

<p>Each condition is trained with five PPO seeds &mdash; 1M environment steps on
Car&ndash;Flag, 3M on Odd&ndash;Even and the beacon tasks, 6M on the Ant Tag variants
&mdash; and evaluated deterministically over 300 episodes.</p>

<h2 id="results">Results</h2>

<h3>End-to-end training</h3>

<div style="overflow:auto;text-align:center">
  <img src="/img/particle-belief-representations/results_end_to_end.png" alt="Mean end-to-end success rate per task group for each encoder. Set networks and gradient CGF features lead on active information gathering; on the beacon tasks no encoder averages above 50% and the Set Transformer is near zero; on Odd-Even PointNet leads at 57%.">
</div>

<p>The simple baselines are not uniformly weak: Gaussian statistics, higher-order moments
and frame stacking are competitive on Car&ndash;Flag, and moments and frame stacking nearly
match the best encoders on Hideout Ant Tag. Elsewhere they generally trail the richer
representations.</p>

<p>On the <strong>active information-gathering</strong> tasks the set networks are strongest,
with the gradient CGF features close behind. These tasks need more than a faithful picture
of the belief; the policy also has to use its uncertainty to decide where to look while
controlling the ant.</p>

<p>On the <strong>beacon tasks</strong> several encoders nearly solve Beacon Sweep, but every
encoder does poorly on Faint and Diffuse Beacon, so none averages above 50% across the
three. The Set Transformer is the exception on Beacon Sweep itself: trained end-to-end it
collects about a fifth of the beacons. On <strong>Odd&ndash;Even</strong> no encoder
exceeds 57% success, with PointNet best and gradient CGF features second.</p>

<h3>Pretraining and transfer</h3>

<div style="overflow:auto;text-align:center">
  <img src="/img/particle-belief-representations/results_pretraining.png" alt="Success under pretraining for the five trainable encoders, with and without latent alignment, for reconstruction and task-specific pretraining, frozen and fine-tuned. A grey line marks each encoder's end-to-end score. The Set Transformer with task-specific pretraining reaches about 93% on the beacon tasks, and all three set networks reach 87% on Odd-Even.">
</div>

<p>The beacon tasks show the clearest effect of the pretraining objective. Reconstruction
pretraining lifts the Set Transformer on Beacon Sweep from 0.21 to 0.87 frozen and 0.95
fine-tuned, so learning to redraw the particle set recovers the geometry needed to sweep the
beacons. It does little for Faint and Diffuse Beacon, which require comparing properties
of different clusters. <strong>Task-specific pretraining</strong> improves all three set
networks on those comparison tasks, and the Set Transformer most: it reaches 0.87&ndash;0.88 on Faint
Beacon and 0.91&ndash;0.92 on Diffuse Beacon, frozen or fine-tuned, against 0.12 and 0.11
end-to-end. Deep Sets and PointNet improve too but fall short. Attention may make
cluster-to-cluster comparisons easier to learn, since it models particle interactions
directly while the pooling networks encode each particle independently first.</p>

<p>On <strong>Odd&ndash;Even</strong>, task-specific pretraining on the categorical
posterior brings all three frozen set networks to 0.87 and their fine-tuned versions to
0.82&ndash;0.85, against an end-to-end best of 0.57. Here the three architectures perform
alike under direct supervision. Reconstruction raises the frozen Set Transformer from 0.22
to 0.62 but gives no consistent benefit across encoders or transfer modes.</p>

<p>On the <strong>active information-gathering</strong> tasks, pretraining generally does
not improve on end-to-end training and sometimes reduces performance. Latent alignment
narrows the gap, particularly after reconstruction pretraining, but does not consistently
exceed end-to-end training. Across all groups the CGF features gain little from
pretraining, and latent alignment gives no consistent benefit on the beacon tasks or
Odd&ndash;Even.</p>

<h3>Takeaways</h3>

<ul>
  <li><strong>End-to-end, choose a pooling set network or gradient CGF features.</strong>
  Deep Sets, PointNet and &nabla;<em>K</em> are the reliable choices when there is no
  pretraining signal.</li>
  <li><strong>The Set Transformer has the highest ceiling, but needs pretraining to reach
  it.</strong> From a random start under PPO it is among the weakest encoders on the beacon
  tasks and Odd&ndash;Even; with the right pretraining it is the strongest.</li>
  <li><strong>Pretrain on the decision, not just the belief.</strong> Task-specific
  prediction gives the largest gains in the study when its target captures the structure
  the decision depends on. Reconstruction and latent alignment help more selectively.</li>
  <li><strong>CGF features are a compact middle ground.</strong> They beat the statistical
  summaries on most tasks, stay comparatively compact, and are largely insensitive to
  pretraining.</li>
</ul>

<p>More broadly, representational fidelity alone is not enough. An encoding has to make the
parts of the belief that matter for the decision accessible to the policy, while keeping
the uncertainty it needs when it still has to gather information.</p>

<h2 id="tables">Per-task results</h2>

<p>Success rate, mean &plusmn; standard error over five PPO seeds, each evaluated on 300
episodes. Bold marks the best entry in a row and underline the second. Car&ndash;Flag reports
the rate of reaching the rewarding end and the Ant Tag variants the tag rate;
Odd&ndash;Even reports the exact-match rate over steady-state steps 22&ndash;30; Beacon Sweep reports the fraction of beacons
collected; Faint and Diffuse Beacon report the rate of reaching the correct survivor.
Car&ndash;Flag is not pretrained, since it has only three reachable beliefs.</p>

<h3>End-to-end</h3>

<table class="results">
  <thead>
    <tr><th></th><th colspan="2">Statistics</th><th colspan="4">CGF</th><th colspan="3">Set networks</th><th>History</th></tr>
    <tr><th>Task</th><th>Gaussian</th><th>Moments</th><th><em>K</em> fixed</th><th><em>K</em> learned</th><th>∇<em>K</em> fixed</th><th>∇<em>K</em> learned</th><th>Deep Sets</th><th>PointNet</th><th>Set Transf.</th><th>Frame stack</th></tr>
  </thead>
  <tbody>
    <tr><td>Car–Flag</td><td>0.80<span class="se"> ±0.12</span></td><td>0.70<span class="se"> ±0.12</span></td><td>0.70<span class="se"> ±0.12</span></td><td>0.70<span class="se"> ±0.12</span></td><td><span class="second">0.90</span><span class="se"> ±0.10</span></td><td><span class="second">0.90</span><span class="se"> ±0.10</span></td><td><strong>1.00</strong><span class="se"> ±0.00</span></td><td><strong>1.00</strong><span class="se"> ±0.00</span></td><td><strong>1.00</strong><span class="se"> ±0.00</span></td><td>0.80<span class="se"> ±0.12</span></td></tr>
    <tr><td>Ant Tag</td><td>0.55<span class="se"> ±0.06</span></td><td>0.18<span class="se"> ±0.05</span></td><td>0.48<span class="se"> ±0.02</span></td><td>0.58<span class="se"> ±0.07</span></td><td>0.74<span class="se"> ±0.02</span></td><td>0.75<span class="se"> ±0.01</span></td><td><span class="second">0.85</span><span class="se"> ±0.05</span></td><td>0.69<span class="se"> ±0.05</span></td><td><strong>0.87</strong><span class="se"> ±0.02</span></td><td>0.02<span class="se"> ±0.01</span></td></tr>
    <tr><td>Lantern Ant Tag</td><td>0.32<span class="se"> ±0.03</span></td><td>0.04<span class="se"> ±0.01</span></td><td>0.09<span class="se"> ±0.03</span></td><td>0.17<span class="se"> ±0.02</span></td><td>0.38<span class="se"> ±0.04</span></td><td>0.36<span class="se"> ±0.03</span></td><td><strong>0.59</strong><span class="se"> ±0.04</span></td><td>0.29<span class="se"> ±0.02</span></td><td><span class="second">0.43</span><span class="se"> ±0.05</span></td><td>0.00<span class="se"> ±0.00</span></td></tr>
    <tr><td>Hideout Ant Tag</td><td>0.29<span class="se"> ±0.05</span></td><td>0.72<span class="se"> ±0.01</span></td><td>0.71<span class="se"> ±0.01</span></td><td>0.72<span class="se"> ±0.01</span></td><td>0.70<span class="se"> ±0.04</span></td><td><span class="second">0.73</span><span class="se"> ±0.01</span></td><td><strong>0.75</strong><span class="se"> ±0.01</span></td><td><strong>0.75</strong><span class="se"> ±0.00</span></td><td><span class="second">0.73</span><span class="se"> ±0.02</span></td><td><span class="second">0.73</span><span class="se"> ±0.01</span></td></tr>
    <tr><td>Odd–Even</td><td>0.31<span class="se"> ±0.02</span></td><td>0.29<span class="se"> ±0.02</span></td><td>0.30<span class="se"> ±0.01</span></td><td>0.31<span class="se"> ±0.01</span></td><td><span class="second">0.42</span><span class="se"> ±0.03</span></td><td><span class="second">0.42</span><span class="se"> ±0.02</span></td><td>0.31<span class="se"> ±0.03</span></td><td><strong>0.57</strong><span class="se"> ±0.01</span></td><td>0.22<span class="se"> ±0.04</span></td><td>0.26<span class="se"> ±0.01</span></td></tr>
    <tr><td>Beacon Sweep</td><td>0.22<span class="se"> ±0.03</span></td><td>0.19<span class="se"> ±0.04</span></td><td>0.86<span class="se"> ±0.01</span></td><td>0.89<span class="se"> ±0.00</span></td><td>0.92<span class="se"> ±0.01</span></td><td>0.94<span class="se"> ±0.01</span></td><td><span class="second">0.97</span><span class="se"> ±0.01</span></td><td><strong>0.98</strong><span class="se"> ±0.01</span></td><td>0.21<span class="se"> ±0.01</span></td><td>0.24<span class="se"> ±0.00</span></td></tr>
    <tr><td>Faint Beacon</td><td>0.13<span class="se"> ±0.01</span></td><td>0.12<span class="se"> ±0.01</span></td><td><strong>0.21</strong><span class="se"> ±0.01</span></td><td>0.19<span class="se"> ±0.01</span></td><td>0.19<span class="se"> ±0.01</span></td><td><span class="second">0.20</span><span class="se"> ±0.01</span></td><td>0.18<span class="se"> ±0.01</span></td><td>0.15<span class="se"> ±0.01</span></td><td>0.12<span class="se"> ±0.01</span></td><td>0.12<span class="se"> ±0.01</span></td></tr>
    <tr><td>Diffuse Beacon</td><td>0.13<span class="se"> ±0.01</span></td><td>0.13<span class="se"> ±0.01</span></td><td>0.19<span class="se"> ±0.01</span></td><td>0.17<span class="se"> ±0.01</span></td><td><span class="second">0.27</span><span class="se"> ±0.01</span></td><td>0.26<span class="se"> ±0.01</span></td><td>0.15<span class="se"> ±0.01</span></td><td><strong>0.30</strong><span class="se"> ±0.03</span></td><td>0.11<span class="se"> ±0.01</span></td><td>0.14<span class="se"> ±0.01</span></td></tr>
  </tbody>
</table>

<h3>Task-specific pretraining</h3>

<table class="results">
  <thead>
    <tr><th></th><th colspan="5">Frozen encoder</th><th colspan="5">Fine-tuned encoder (0.1× LR)</th></tr>
    <tr><th>Task</th><th><em>K</em></th><th>∇<em>K</em></th><th>Deep Sets</th><th>PointNet</th><th>Set Transf.</th><th><em>K</em></th><th>∇<em>K</em></th><th>Deep Sets</th><th>PointNet</th><th>Set Transf.</th></tr>
  </thead>
  <tbody>
    <tr><td>Ant Tag</td><td>0.43<span class="se"> ±0.08</span></td><td>0.71<span class="se"> ±0.04</span></td><td>0.86<span class="se"> ±0.01</span></td><td>0.78<span class="se"> ±0.02</span></td><td>0.87<span class="se"> ±0.03</span></td><td>0.47<span class="se"> ±0.07</span></td><td>0.68<span class="se"> ±0.05</span></td><td><span class="second">0.88</span><span class="se"> ±0.03</span></td><td>0.80<span class="se"> ±0.00</span></td><td><strong>0.89</strong><span class="se"> ±0.02</span></td></tr>
    <tr><td>Lantern Ant Tag</td><td>0.10<span class="se"> ±0.02</span></td><td>0.33<span class="se"> ±0.03</span></td><td>0.30<span class="se"> ±0.06</span></td><td>0.31<span class="se"> ±0.02</span></td><td>0.36<span class="se"> ±0.02</span></td><td>0.08<span class="se"> ±0.01</span></td><td><span class="second">0.39</span><span class="se"> ±0.02</span></td><td>0.26<span class="se"> ±0.05</span></td><td>0.31<span class="se"> ±0.03</span></td><td><strong>0.45</strong><span class="se"> ±0.06</span></td></tr>
    <tr><td>Hideout Ant Tag</td><td>0.61<span class="se"> ±0.08</span></td><td>0.74<span class="se"> ±0.00</span></td><td>0.73<span class="se"> ±0.01</span></td><td>0.72<span class="se"> ±0.02</span></td><td>0.71<span class="se"> ±0.01</span></td><td>0.73<span class="se"> ±0.01</span></td><td>0.74<span class="se"> ±0.01</span></td><td><span class="second">0.76</span><span class="se"> ±0.01</span></td><td><strong>0.77</strong><span class="se"> ±0.02</span></td><td>0.71<span class="se"> ±0.02</span></td></tr>
    <tr><td>Odd–Even</td><td>0.24<span class="se"> ±0.02</span></td><td>0.43<span class="se"> ±0.01</span></td><td><strong>0.87</strong><span class="se"> ±0.00</span></td><td><strong>0.87</strong><span class="se"> ±0.00</span></td><td><strong>0.87</strong><span class="se"> ±0.00</span></td><td>0.25<span class="se"> ±0.02</span></td><td>0.44<span class="se"> ±0.01</span></td><td>0.82<span class="se"> ±0.01</span></td><td><span class="second">0.85</span><span class="se"> ±0.01</span></td><td>0.83<span class="se"> ±0.02</span></td></tr>
    <tr><td>Beacon Sweep</td><td>0.86<span class="se"> ±0.01</span></td><td>0.91<span class="se"> ±0.01</span></td><td><span class="second">0.99</span><span class="se"> ±0.00</span></td><td><strong>1.00</strong><span class="se"> ±0.00</span></td><td><strong>1.00</strong><span class="se"> ±0.00</span></td><td>0.87<span class="se"> ±0.01</span></td><td>0.92<span class="se"> ±0.00</span></td><td><strong>1.00</strong><span class="se"> ±0.00</span></td><td><strong>1.00</strong><span class="se"> ±0.00</span></td><td><strong>1.00</strong><span class="se"> ±0.00</span></td></tr>
    <tr><td>Faint Beacon</td><td>0.18<span class="se"> ±0.01</span></td><td>0.22<span class="se"> ±0.01</span></td><td>0.40<span class="se"> ±0.01</span></td><td>0.25<span class="se"> ±0.01</span></td><td><strong>0.88</strong><span class="se"> ±0.01</span></td><td>0.20<span class="se"> ±0.01</span></td><td>0.22<span class="se"> ±0.01</span></td><td>0.40<span class="se"> ±0.01</span></td><td>0.34<span class="se"> ±0.00</span></td><td><span class="second">0.87</span><span class="se"> ±0.01</span></td></tr>
    <tr><td>Diffuse Beacon</td><td>0.19<span class="se"> ±0.02</span></td><td>0.21<span class="se"> ±0.01</span></td><td>0.63<span class="se"> ±0.01</span></td><td>0.79<span class="se"> ±0.01</span></td><td><span class="second">0.91</span><span class="se"> ±0.00</span></td><td>0.20<span class="se"> ±0.01</span></td><td>0.23<span class="se"> ±0.01</span></td><td>0.52<span class="se"> ±0.04</span></td><td>0.78<span class="se"> ±0.01</span></td><td><strong>0.92</strong><span class="se"> ±0.01</span></td></tr>
  </tbody>
</table>

<h3>Reconstruction pretraining</h3>

<table class="results">
  <thead>
    <tr><th></th><th colspan="5">Frozen encoder</th><th colspan="5">Fine-tuned encoder (0.1× LR)</th></tr>
    <tr><th>Task</th><th><em>K</em></th><th>∇<em>K</em></th><th>Deep Sets</th><th>PointNet</th><th>Set Transf.</th><th><em>K</em></th><th>∇<em>K</em></th><th>Deep Sets</th><th>PointNet</th><th>Set Transf.</th></tr>
  </thead>
  <tbody>
    <tr><td>Ant Tag</td><td>0.31<span class="se"> ±0.05</span></td><td>0.70<span class="se"> ±0.02</span></td><td><strong>0.94</strong><span class="se"> ±0.03</span></td><td><span class="second">0.90</span><span class="se"> ±0.02</span></td><td>0.79<span class="se"> ±0.03</span></td><td>0.38<span class="se"> ±0.03</span></td><td>0.78<span class="se"> ±0.03</span></td><td>0.81<span class="se"> ±0.05</span></td><td>0.77<span class="se"> ±0.05</span></td><td>0.78<span class="se"> ±0.03</span></td></tr>
    <tr><td>Lantern Ant Tag</td><td>0.09<span class="se"> ±0.02</span></td><td>0.40<span class="se"> ±0.04</span></td><td>0.38<span class="se"> ±0.08</span></td><td>0.35<span class="se"> ±0.04</span></td><td>0.40<span class="se"> ±0.05</span></td><td>0.09<span class="se"> ±0.03</span></td><td>0.36<span class="se"> ±0.02</span></td><td><span class="second">0.43</span><span class="se"> ±0.04</span></td><td>0.34<span class="se"> ±0.03</span></td><td><strong>0.44</strong><span class="se"> ±0.05</span></td></tr>
    <tr><td>Hideout Ant Tag</td><td>0.71<span class="se"> ±0.02</span></td><td>0.72<span class="se"> ±0.02</span></td><td>0.72<span class="se"> ±0.01</span></td><td><strong>0.74</strong><span class="se"> ±0.01</span></td><td><span class="second">0.73</span><span class="se"> ±0.02</span></td><td><strong>0.74</strong><span class="se"> ±0.01</span></td><td><span class="second">0.73</span><span class="se"> ±0.01</span></td><td>0.72<span class="se"> ±0.02</span></td><td>0.69<span class="se"> ±0.06</span></td><td><strong>0.74</strong><span class="se"> ±0.01</span></td></tr>
    <tr><td>Odd–Even</td><td>0.29<span class="se"> ±0.01</span></td><td>0.44<span class="se"> ±0.01</span></td><td>0.48<span class="se"> ±0.02</span></td><td>0.48<span class="se"> ±0.02</span></td><td><strong>0.62</strong><span class="se"> ±0.01</span></td><td>0.28<span class="se"> ±0.01</span></td><td>0.43<span class="se"> ±0.01</span></td><td>0.54<span class="se"> ±0.01</span></td><td><span class="second">0.55</span><span class="se"> ±0.03</span></td><td>0.40<span class="se"> ±0.02</span></td></tr>
    <tr><td>Beacon Sweep</td><td>0.88<span class="se"> ±0.01</span></td><td>0.95<span class="se"> ±0.01</span></td><td>0.71<span class="se"> ±0.01</span></td><td>0.91<span class="se"> ±0.00</span></td><td>0.87<span class="se"> ±0.03</span></td><td>0.89<span class="se"> ±0.02</span></td><td>0.95<span class="se"> ±0.01</span></td><td><span class="second">0.97</span><span class="se"> ±0.01</span></td><td><strong>0.99</strong><span class="se"> ±0.00</span></td><td>0.95<span class="se"> ±0.01</span></td></tr>
    <tr><td>Faint Beacon</td><td>0.20<span class="se"> ±0.02</span></td><td><strong>0.24</strong><span class="se"> ±0.01</span></td><td>0.13<span class="se"> ±0.01</span></td><td>0.17<span class="se"> ±0.01</span></td><td>0.13<span class="se"> ±0.02</span></td><td>0.19<span class="se"> ±0.01</span></td><td>0.21<span class="se"> ±0.01</span></td><td><span class="second">0.23</span><span class="se"> ±0.01</span></td><td>0.18<span class="se"> ±0.01</span></td><td>0.14<span class="se"> ±0.01</span></td></tr>
    <tr><td>Diffuse Beacon</td><td>0.19<span class="se"> ±0.00</span></td><td>0.25<span class="se"> ±0.02</span></td><td>0.14<span class="se"> ±0.01</span></td><td>0.19<span class="se"> ±0.02</span></td><td>0.13<span class="se"> ±0.01</span></td><td>0.16<span class="se"> ±0.01</span></td><td><strong>0.27</strong><span class="se"> ±0.02</span></td><td>0.16<span class="se"> ±0.01</span></td><td><span class="second">0.26</span><span class="se"> ±0.01</span></td><td>0.18<span class="se"> ±0.01</span></td></tr>
  </tbody>
</table>

<p>The aligned variants of both pretraining tables are in the paper.</p>

<h2 id="code">Code</h2>

<p>The belief encoders, particle-filter wrappers and training harness are in
<a href="https://github.com/brendanjcrowe/set_transformer">github.com/brendanjcrowe/set_transformer</a>.
The environments, including the three beacon tasks, are Gymnasium-compatible and live in
<a href="https://github.com/brendanjcrowe/pomdp-domains">github.com/brendanjcrowe/pomdp-domains</a>.</p>
