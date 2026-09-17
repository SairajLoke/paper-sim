#!/usr/bin/env python3
"""Square sheet of "paper" (MPM elasto-plastic thin box) with one edge lifted
and folded toward the center. Headless, records an MPM video.

Physical characteristics are all configurable via CLI flags -- run
`python3 paper_fold_sim.py --help` for the full list. Defaults are a rough
first guess for paper (low yield stress = creases easily) and will very
likely need empirical tuning once you see the first video.
"""
import argparse
import os

import torch

import genesis as gs


def main():
    p = argparse.ArgumentParser()
    # Sheet geometry
    p.add_argument("--width", type=float, default=0.20, help="sheet side length (m)")
    p.add_argument("--thickness", type=float, default=0.005, help="sheet thickness (m)")
    p.add_argument("--grid-density", type=int, default=64, help="MPM grid resolution (cells/meter)")
    p.add_argument("--particle-size", type=float, default=0.0015,
                   help="MPM particle diameter (m). Default reference is 0.01 at "
                        "grid_density=64 -- far larger than a paper-thin sheet, which is "
                        "why the first attempt only sampled ~100 particles total.")
    # Material (gs.materials.MPM.ElastoPlastic)
    p.add_argument("--E", type=float, default=5e5, help="Young's modulus (stiffness)")
    p.add_argument("--nu", type=float, default=0.3, help="Poisson ratio")
    p.add_argument("--rho", type=float, default=800.0, help="density kg/m^3 (paper ~700-900)")
    p.add_argument("--yield-stress", type=float, default=100000.0,
                   help="von Mises yield stress -- LOWER = creases more easily. "
                        "200 was far too low (plastic flow/necking, confirmed via "
                        "get_particles_pos()). 10000 held the sheet's width together but "
                        "still curled/sagged smoothly under its own weight rather than "
                        "staying flat and creasing sharply only at the fold -- raising E "
                        "instead of yield_stress does NOT fix this (higher E means MORE "
                        "stress at the same curvature, so it hits the same yield_stress "
                        "sooner, not later). Trying 100000 to resist gravity sag while "
                        "still yielding at the much sharper curvature the handle forces "
                        "at the actual fold.")
    p.add_argument("--grip-stiffness", type=float, default=50.0,
                   help="handle<->particle constraint spring stiffness. The library "
                        "example value (1e5) is orders of magnitude too stiff for "
                        "explicit MPM at these particle masses/dt -- it detonates the "
                        "sheet to full-domain spread on the very first step. 50 was "
                        "empirically confirmed stable (smooth, non-exploding spread) "
                        "through a full lift phase at this sim's default particle_size/dt.")
    # Fold motion: lift phase then fold-toward-center phase
    p.add_argument("--lift-height", type=float, default=0.15, help="how high to lift the edge (m)")
    p.add_argument("--lift-seconds", type=float, default=1.0)
    p.add_argument("--fold-seconds", type=float, default=1.5)
    p.add_argument("--settle-seconds", type=float, default=0.3,
                   help="extra time after folding to see if the crease holds. Kept short: "
                        "once the fold compacts the sheet enough that folded layers land "
                        "within one grid cell of each other/the floor, this thin-sheet MPM "
                        "setup hits a self-contact blowup (confirmed via get_particles_pos() "
                        "-- spread collapses smoothly then jumps to full-domain in one step "
                        "at ~t=2.9s regardless of --grip-stiffness). Fixing that properly "
                        "needs a much finer grid_density (with a correspondingly smaller dt) "
                        "than this sim uses.")
    p.add_argument("--dt", type=float, default=2e-3)
    p.add_argument("--substeps", type=int, default=10)
    # Output / mode
    p.add_argument("--vis", action="store_true", help="show live GUI (default: headless)")
    p.add_argument("--gpu", action="store_true", default=True)
    p.add_argument("--out", default="out/paper_fold.mp4")
    p.add_argument("--fps", type=float, default=30.0)
    args = p.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    gs.init(backend=gs.gpu if args.gpu else gs.cpu)

    W = args.width
    T = args.thickness
    sheet_z = 0.3   # rest height above ground

    scene = gs.Scene(
        sim_options=gs.options.SimOptions(dt=args.dt, substeps=args.substeps),
        mpm_options=gs.options.MPMOptions(
            grid_density=args.grid_density,
            particle_size=args.particle_size,
            lower_bound=(-W, -W, 0.0),
            upper_bound=(W, W, sheet_z + args.lift_height + W),
        ),
        # "recon" (below) OOM-killed the container on an earlier, longer run
        # (settle_seconds=1.0, ~1750 steps) -- its memory grows steadily frame
        # over frame. This run is much shorter (~1400 steps) and stayed under
        # 5GB of the 24.6GB cgroup limit the whole way, so it's back in use.
        vis_options=gs.options.VisOptions(particle_size_scale=1.0),
        show_viewer=args.vis,
    )

    scene.add_entity(gs.morphs.Plane())

    # Explicit lower/upper (unambiguous, unlike pos+size where pos's corner-vs-
    # center convention isn't guaranteed) so the edge-grip bbox below is
    # computed in the exact same frame the sheet was actually built in.
    sheet_lower = (-W / 2.0, -W / 2.0, sheet_z - T / 2.0)
    sheet_upper = (W / 2.0, W / 2.0, sheet_z + T / 2.0)

    sheet = scene.add_entity(
        material=gs.materials.MPM.ElastoPlastic(
            E=args.E,
            nu=args.nu,
            rho=args.rho,
            von_mises_yield_stress=args.yield_stress,
        ),
        morph=gs.morphs.Box(
            lower=sheet_lower,
            upper=sheet_upper,
        ),
        # "visual" (skinned rest-pose mesh) looked clean at rest but its fixed
        # skinning weights break down under this much plastic deformation --
        # it renders a collapsed wedge even though get_particles_pos() confirms
        # the true gripped-edge width stays ~0.2m throughout. "recon" rebuilds
        # the surface from the actual current particle cloud every frame (true
        # to the physics) -- retrying it now that the run is much shorter
        # (settle cut to 0.3s) than when it OOM-killed the container earlier.
        surface=gs.surfaces.Default(color=(0.95, 0.95, 0.9), vis_mode="recon"),
    )

    # Small rigid "handle" that will grip one edge of the sheet.
    handle_start = (sheet_upper[0] - T, 0.0, sheet_z)
    handle = scene.add_entity(
        gs.morphs.Box(pos=handle_start, size=(T * 4, W * 0.2, T * 4), fixed=False),
    )

    # Aim at the center of the whole lift+fold action volume, not the sheet's
    # resting pose -- the previous camera pointed mostly above/past the sheet
    # (lookat biased up by only 0.3*lift_height while sitting at +0.5*W
    # height) and showed nothing but ground for most of the clip. Distance is
    # sized off the actual action extent (sheet width and lift height) so the
    # full motion stays in frame with margin, at a ~25 degree downward angle.
    #
    # The lift+fold motion (handle_start -> straight up -> arc toward center)
    # stays entirely in the X-Z plane, i.e. the sheet pivots about the Y axis
    # as it lifts. A camera sitting at x=0 views that rotation edge-on once
    # the sheet tips up past ~45 degrees -- a real 0.2m-wide sheet visually
    # collapses to a thin blade, which looks identical to a physics bug but
    # isn't one (confirmed via get_particles_pos(): the sheet's actual y-extent
    # stays ~0.2m throughout, only the render angle foreshortens it away).
    # Offsetting the camera off that rotation axis keeps the sheet's face in
    # view for the whole motion.
    action_center_z = sheet_z + args.lift_height * 0.5
    cam_dist = max(W, args.lift_height) * 2.8
    cam = scene.add_camera(
        res=(960, 640),
        pos=(cam_dist * 0.5, -cam_dist * 0.85, action_center_z + cam_dist * 0.5),
        lookat=(0.0, 0.0, action_center_z),
        fov=45,
    )

    scene.build()

    # Sanity-check where the particles actually ended up before trusting the
    # edge-grip bbox -- catches a coordinate-convention mismatch immediately
    # instead of silently gripping zero particles and free-falling.
    all_mask = sheet.get_particles_in_bbox(
        (sheet_lower[0] - 10, sheet_lower[1] - 10, sheet_lower[2] - 10),
        (sheet_upper[0] + 10, sheet_upper[1] + 10, sheet_upper[2] + 10),
    )
    print(f"[paper_fold] total sheet particles: {int(all_mask.sum())}")

    # Grip the particles under the +X edge of the sheet (generous margin on
    # every axis so this doesn't depend on getting the box convention exactly
    # right a second time).
    grip_width = max(4 * T, W * 0.1)
    edge_lo = (sheet_upper[0] - grip_width, sheet_lower[1] - T, sheet_lower[2] - T)
    edge_hi = (sheet_upper[0] + T, sheet_upper[1] + T, sheet_upper[2] + T)
    mask = sheet.get_particles_in_bbox(edge_lo, edge_hi)
    print(f"[paper_fold] gripping {int(mask.sum())} edge particles")
    if int(mask.sum()) == 0:
        raise RuntimeError("gripped 0 particles -- edge bbox does not overlap the sheet, aborting "
                           "before wasting a render on an unconstrained free-fall")
    sheet.set_particle_constraints(mask, handle.links[0].idx, stiffness=args.grip_stiffness)

    cam.start_recording(save_to_filename=args.out, fps=args.fps)

    def n_steps(seconds: float) -> int:
        return max(1, int(seconds / args.dt))

    hx, hy, hz = handle_start
    center = (0.0, 0.0, sheet_z + args.lift_height * 0.6)

    try:
        # Phase 1: lift straight up.
        lift_steps = n_steps(args.lift_seconds)
        for i in range(lift_steps):
            t = i / lift_steps
            z = hz + args.lift_height * t
            target = torch.tensor([hx, hy, z, 1.0, 0.0, 0.0, 0.0], device=gs.device)
            handle.set_qpos(target)
            scene.step()

        # Phase 2: fold the lifted edge over toward the sheet's center.
        fold_steps = n_steps(args.fold_seconds)
        top = (hx, hy, hz + args.lift_height)
        for i in range(fold_steps):
            t = i / fold_steps
            x = top[0] + (center[0] - top[0]) * t
            y = top[1] + (center[1] - top[1]) * t
            z = top[2] + (center[2] - top[2]) * t
            target = torch.tensor([x, y, z, 1.0, 0.0, 0.0, 0.0], device=gs.device)
            handle.set_qpos(target)
            scene.step()

        # Phase 3: hold in place, let the crease (or spring-back) settle and show on camera.
        for _ in range(n_steps(args.settle_seconds)):
            scene.step()

    finally:
        cam.stop_recording()
        print(f"[paper_fold] saved video -> {args.out}")


if __name__ == "__main__":
    main()
