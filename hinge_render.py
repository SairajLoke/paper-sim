import os
import torch
import genesis as gs

gs.init(backend=gs.gpu)

W = 0.20
T = 0.005
sheet_z = T / 2.0 + 0.0005
grid_density = 64
particle_size = 0.0015
lift_height = 0.15
HINGE_YIELD = float(os.environ.get("HINGE_YIELD", "8000"))
BASE_YIELD = float(os.environ.get("BASE_YIELD", "1e6"))
hinge_half = float(os.environ.get("HINGE_HALF", "0.01"))
OUT = os.environ.get("OUT", "out/hinge_test.mp4")

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

scene = gs.Scene(
    sim_options=gs.options.SimOptions(dt=2e-3, substeps=10),
    mpm_options=gs.options.MPMOptions(
        grid_density=grid_density,
        particle_size=particle_size,
        lower_bound=(-W, -W, -0.1),
        upper_bound=(W, W, sheet_z + lift_height + W),
    ),
    show_viewer=False,
)
scene.add_entity(gs.morphs.Plane())

y_lo, y_hi = -W / 2.0, W / 2.0
z_lo, z_hi = sheet_z - T / 2.0, sheet_z + T / 2.0

base = scene.add_entity(
    material=gs.materials.MPM.ElastoPlastic(E=5e5, nu=0.3, rho=800.0, von_mises_yield_stress=BASE_YIELD),
    morph=gs.morphs.Box(lower=(-W / 2.0, y_lo, z_lo), upper=(-hinge_half, y_hi, z_hi)),
    surface=gs.surfaces.Default(color=(0.95, 0.95, 0.9), vis_mode="particle"),
)
hinge = scene.add_entity(
    material=gs.materials.MPM.ElastoPlastic(E=5e5, nu=0.3, rho=800.0, von_mises_yield_stress=HINGE_YIELD),
    morph=gs.morphs.Box(lower=(-hinge_half, y_lo, z_lo), upper=(hinge_half, y_hi, z_hi)),
    surface=gs.surfaces.Default(color=(0.95, 0.95, 0.9), vis_mode="particle"),
)
flap = scene.add_entity(
    material=gs.materials.MPM.ElastoPlastic(E=5e5, nu=0.3, rho=800.0, von_mises_yield_stress=BASE_YIELD),
    morph=gs.morphs.Box(lower=(hinge_half, y_lo, z_lo), upper=(W / 2.0, y_hi, z_hi)),
    surface=gs.surfaces.Default(color=(0.95, 0.95, 0.9), vis_mode="particle"),
)

handle_start = (W / 2.0 - T, 0.0, sheet_z)
handle = scene.add_entity(gs.morphs.Box(pos=handle_start, size=(T * 4, W * 0.2, T * 4), fixed=False))

anchor_start = (-W / 2.0 + T, 0.0, sheet_z)
anchor = scene.add_entity(gs.morphs.Box(pos=anchor_start, size=(T * 4, W * 0.2, T * 4), fixed=True))

action_center_z = sheet_z + lift_height * 0.5
cam_dist = max(W, lift_height) * 2.8
cam = scene.add_camera(
    res=(960, 640),
    pos=(cam_dist * 0.5, -cam_dist * 0.85, action_center_z + cam_dist * 0.5),
    lookat=(0.0, 0.0, action_center_z),
    fov=45,
)

scene.build()

grip_width = max(4 * T, W * 0.1)
edge_lo = (W / 2.0 - grip_width, y_lo - T, z_lo - T)
edge_hi = (W / 2.0 + T, y_hi + T, z_hi + T)
gmask = flap.get_particles_in_bbox(edge_lo, edge_hi)
print("gripped on flap:", int(gmask.sum()))
flap.set_particle_constraints(gmask, handle.links[0].idx, stiffness=50.0)

anchor_edge_lo = (-W / 2.0 - T, y_lo - T, z_lo - T)
anchor_edge_hi = (-W / 2.0 + grip_width, y_hi + T, z_hi + T)
amask = base.get_particles_in_bbox(anchor_edge_lo, anchor_edge_hi)
print("gripped on base (anchor):", int(amask.sum()))
base.set_particle_constraints(amask, anchor.links[0].idx, stiffness=50.0)

cam.start_recording(save_to_filename=OUT, fps=30.0)

hx, hy, hz = handle_start
dt = 2e-3
center = (0.0, 0.0, sheet_z + lift_height * 0.6)


def n_steps(seconds):
    return max(1, int(seconds / dt))


try:
    lift_steps = n_steps(1.0)
    for i in range(lift_steps):
        t = i / lift_steps
        z = hz + lift_height * t
        handle.set_qpos(torch.tensor([hx, hy, z, 1.0, 0.0, 0.0, 0.0], device=gs.device))
        scene.step()

    fold_steps = n_steps(1.5)
    top = (hx, hy, hz + lift_height)
    for i in range(fold_steps):
        t = i / fold_steps
        x = top[0] + (center[0] - top[0]) * t
        y = top[1] + (center[1] - top[1]) * t
        z = top[2] + (center[2] - top[2]) * t
        handle.set_qpos(torch.tensor([x, y, z, 1.0, 0.0, 0.0, 0.0], device=gs.device))
        scene.step()

    for _ in range(n_steps(0.05)):
        scene.step()
finally:
    cam.stop_recording()
    print(f"[hinge_render] saved video -> {OUT}")
