# ARCSim: proper thin-shell folding (sharp creases, not smooth curls)

This is the follow-up to the MPM work (`../paper_fold_sim.py`, `../hinge_render.py`).
MPM gave a coherent fold but only ever produced a smooth curl — documented as an
inherent limitation of naive volumetric MPM for thin shells, matching published
research (a SIGGRAPH Asia 2025 origami paper explicitly notes MPM output needs a
post-processing step to extract straight fold lines because it's "unsuitable for
practical origami"). ARCSim is the real answer: a proper adaptive-remeshing thin
shell FEM solver, purpose-built for cloth/paper/metal plastic creasing
(Narain, Pfaff, O'Brien, SIGGRAPH 2013 -- http://graphics.berkeley.edu/resources/ARCSim/).

Confirmed working: **a genuinely sharp crease** forms and holds, not a curl. See
`results/fold_frame030_sharp_crease.png`.

## What's here

- `patches/` -- the real fixes needed to build this 2013 codebase on Ubuntu 24.04
  (see below). Not guesses -- verified by actually getting `bin/arcsim` to build
  and run.
- `render_obj.py` / `render_cloth_only.py` -- standalone matplotlib scripts to
  turn ARCSim's `.obj` frame output into images without needing a display.
  ARCSim's own screenshot mode (`replay <out> <sshot-dir>`) needs a live
  spacebar keypress via GLUT to start playback -- doesn't work headlessly
  without extra work (xdotool + Xvfb), so these scripts are the fast path.
- `results/` -- frames from two runs (see below).
- `fold.json.stock` -- ARCSim's own bundled paper-folding demo config, used
  as-is for the first test run.

## Runs so far

**`conf/sphere.json`** (ARCSim's own "hello world" -- cloth dropped onto a
sphere, nothing paper-specific): confirms the whole build+run pipeline works.
`sphere_frame000/090/186.png`.

**`conf/fold.json`** (ARCSim's own paper-folding demo -- `paper.json` material,
`yield_curv=200`, `weakening=1`, two roller obstacles creasing a letter-shaped
sheet in sequence): 
- Frame 30: a real sharp crease, not a curl. This is the headline result.
- Frame 60: some relaxation/broadening after the first roller releases.
- Frame 110-157: the second fold. This did NOT go cleanly -- the sheet
  crumples rather than folding flat (`fold_frame157_second_fold_crumpled.png`).
  Likely the stock roller motion/timing wasn't tuned for a clean second
  fold -- it exists in the demo just to show two creases are possible, not
  to produce a clean paper-airplane-style result. Stopped manually at frame
  157/350 after the mesh exploded to ~20k faces and per-substep solve time
  climbed past 1.4s (from ~150ms at the start) -- see "Why it's slow" below.

**Not yet done**: a deliberately-designed multi-fold sequence (own `handles`/
`motions`, not the stock demo) aimed at an actual paper-airplane shape, with
2 "hand" forces per the original ask, per the plan to hand-design node
selections and roller/handle trajectories.

## Build fixes (Ubuntu 24.04, this is a real 2013 C++ codebase)

`INSTALL` only lists BLAS, Boost, freeglut, gfortran, LAPACK, libpng --
incomplete. Also needed: `libeigen3-dev libsuperlu-dev libsuitesparse-dev
liblapacke-dev scons`.

1. **jsoncpp's `SConstruct` is Python 2** (`print` statements, `import
   commands`, `apply()`) -- scons on a modern system needs Python 3. Fixed
   file: `patches/jsoncpp_SConstruct_fixed.py` -- copy over
   `dependencies/jsoncpp/SConstruct`.
2. **`build/release/` and `build/debug/` don't exist** -- the Makefile
   doesn't create them. `mkdir -p build/release build/debug build/dep bin`
   before building.
3. **SuiteSparse headers live in `/usr/include/suitesparse/`**, not on the
   default include path. Add `-I/usr/include/suitesparse` to `CXXFLAGS`.
4. **`liblapacke-dev` isn't in the documented deps at all**, but the code
   calls `LAPACKE_dgesvd` and the Makefile never links `-llapacke`. Install
   the package and add `-llapacke` to `LDFLAGS`.
5. **`NO_OPENGL` is broken in this codebase** -- `display.cpp` wraps its
   *entire* content (including `Annotation::list` and `wait_key()`, both
   referenced unconditionally by other files with no matching guard) in
   `#ifndef NO_OPENGL`. Building with `NO_OPENGL` defined gives unresolved
   link errors. Fix: don't define it -- build with GL/GLUT linked in as
   normal (already in the dependency list above) and just use
   `simulateoffline`/`resumeoffline` at runtime, which never opens a window
   and works fine headless as long as the shared libs are present at load
   time.
6. **`ctags` isn't installed** and the `release` Makefile target depends on
   it. `apt install universal-ctags`.

Full working diff for the two files that needed editing:
`patches/Makefile.linux.patch` and `patches/jsoncpp_SConstruct_fixed.py`
(full file, not a diff -- the diff was noisy from a line-ending artifact).

Also worth knowing: `simulateoffline` does NOT write `conf.json` into the
output directory the way the interactive `simulate` path implies it should
(`init_physics` in `runphysics.cpp` does call `copy_file` to do this, but it
wasn't landing in practice in this setup) -- `bin/arcsim generate <out-dir>`
needs that file to exist to know what scene produced the `.bin` frames.
Workaround: `cp conf/<scene>.json out/<out-dir>/conf.json` manually before
running `generate`.

## Why it's slow

ARCSim uses a *direct* sparse Cholesky/LU solve (TAUCS/CHOLMOD) every
substep -- CPU-bound, doesn't scale across cores the way the GPU work
(Genesis/MPM) did. Worse: the adaptive remeshing that produces the sharp
crease also *grows the mesh* as detail concentrates there, so the linear
system -- and therefore the per-substep cost -- keeps increasing through
the run rather than staying flat. In the `fold.json` run: 32 faces at
frame 0 -> 1003 at frame 30 -> ~20,000 by frame 154, with solve time
climbing from ~150ms/substep to ~1.4s/substep over that span. This is a
known, real limitation of this class of adaptive-remeshing solver (the
same bottleneck the GPU cloth papers referenced in the main repo README
are trying to fix) -- not a misconfiguration on our end.

## Hardware

CPU-only, no GPU involved. Built and run on a 72-core / 503GB RAM box
(much more than needed -- 4-8GB RAM and a handful of cores would suffice
for meshes this size; see the main repo README's earlier spec estimate).
