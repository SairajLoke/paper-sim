# paper-sim

Genesis (MPM) simulation of a paper sheet being lifted from one edge and
folded, aimed at eventually driving a robot-manipulation environment (not
just a pretty render).

## Files

- `paper_fold_sim.py` -- single continuous sheet (one MPM entity), lifted at
  one edge and folded toward center. Produces a coherent, physically stable
  fold, but the bend is a smooth curl along the whole sheet rather than a
  sharp crease -- this is a documented limitation of naive volumetric MPM for
  thin shells (see "Known issues" below).
- `hinge_render.py` -- experimental approach: splits the sheet into three
  separate MPM entities sharing one grid -- a stiff anchored `base`, a stiff
  `flap` (the part that gets lifted), and a thin, deliberately weak `hinge`
  strip between them. Concentrates the plastic bending into the hinge,
  producing a genuine visible crease line instead of a smooth curl. Currently
  shows a visible gap/tear at the hinge-to-panel seam under load (see below).
- `demo_creased_fold.mp4` -- the hinge approach's best result so far: sharp
  crease line, but visibly tears (opens a gap) at the seam under load.
- `demo_smooth_fold.mp4` -- the single-entity approach: no tearing, fully
  coherent, but curls smoothly rather than creasing sharply.

## Key parameters and why (paper_fold_sim.py)

- `yield_stress=10000` (not the naive-first-guess 200): 200 let the sheet
  plastically flow/neck apart under its own weight (confirmed via
  `get_particles_pos()` -- full-sheet spread collapsed to 0.03-0.08m instead
  of holding its actual 0.2m width). Raising `E` instead of `yield_stress`
  does **not** help: higher `E` means *more* stress at the same curvature, so
  it hits the same yield threshold *sooner*, not later.
- `grip_stiffness=50` (library example uses 1e5): 1e5 is orders of magnitude
  too stiff for explicit MPM at these particle masses/dt -- it detonates the
  sheet to full-domain spread on the very first step.
- `settle_seconds=0.3`: once the fold compacts the sheet enough that folded
  layers land within one MPM grid cell of each other (or of the floor), this
  setup hits a self-contact blowup -- spread collapses smoothly then jumps to
  full-domain in a single step. Recording stops just before that point.
- `vis_mode="recon"`: rebuilds the surface from the actual current particle
  cloud every frame (true to the physics). `"particle"` renders a point
  cloud (fine for fast iteration, ugly for final output); `"visual"` skins a
  rest-pose mesh to nearby particles, which visibly distorts/collapses under
  this much plastic deformation.

## Known issues / open problems

1. **No sharp crease with a single continuous entity.** Standard MPM
   produces smooth curved surfaces, not sharp folds -- this matches published
   research (a SIGGRAPH Asia 2025 paper on origami crease discovery notes
   exactly this limitation and needed a separate post-processing step to
   extract straight folding lines from MPM output).
2. **The multi-entity hinge trick creases sharply but tears at the seam.**
   Genesis's `von_mises_yield_stress` is a single scalar baked into the
   material class, not a per-particle field, and there's no public API to
   assign different materials to different particles within one entity. The
   workaround (three separate entities sharing the grid) has no true
   continuum bond at the boundaries, so under load the seam can visibly
   separate -- this reads as tearing, not creasing. Tried widening the hinge
   and overlapping entity bounding boxes; overlap made it worse (extra
   density at the overlap caused a new necking artifact). Not yet solved.
3. **Self-contact blowup once folded layers compact.** A general thin-shell
   MPM limitation at this grid resolution -- see `settle_seconds` above.
   Root cause; not something the current script fixes, just avoids by timing.

## Where this probably goes next

Naive volumetric MPM (a thin box of particles) is the wrong tool for a true
thin shell -- real prior art either couples a proper 2D shell FEM
discretization with an MPM grid only for contact (see "A material point
method for thin shells with frictional contact", Jiang/Gast/Teran), or uses
a purpose-built cloth solver with bending plasticity (ARCSim,
http://graphics.berkeley.edu/resources/ARCSim/ -- open source, built
explicitly for cloth/paper/plastic/metal sheets with bending plasticity and
crease-preserving adaptive remeshing). Given the actual goal is a
robot-interaction sim (not a VFX-quality render), the more relevant next
step is probably putting an actual robot gripper model into the Genesis
scene rather than continuing to chase crease geometry with a bare handle --
Genesis already supports robots and MPM in the same engine.
