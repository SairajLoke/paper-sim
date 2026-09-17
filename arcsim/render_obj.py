import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def load_obj(path):
    verts = []
    faces = []
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                parts = line.split()
                verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith("f "):
                parts = line.split()[1:]
                idx = [int(p.split("/")[0]) - 1 for p in parts]
                faces.append(idx)
    return np.array(verts), faces


def render(cloth_path, obs_path, out_path, title):
    cv, cf = load_obj(cloth_path)
    ov, of = load_obj(obs_path)

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection="3d")

    cloth_tris = [cv[f] for f in cf]
    cloth_coll = Poly3DCollection(cloth_tris, facecolor=(0.9, 0.9, 0.85, 1.0),
                                   edgecolor=(0.3, 0.3, 0.3, 0.3), linewidths=0.2)
    ax.add_collection3d(cloth_coll)

    obs_tris = [ov[f] for f in of]
    obs_coll = Poly3DCollection(obs_tris, facecolor=(0.6, 0.65, 0.9, 0.25), edgecolor="none")
    ax.add_collection3d(obs_coll)

    all_v = np.vstack([cv, ov])
    mins, maxs = all_v.min(axis=0), all_v.max(axis=0)
    center = (mins + maxs) / 2
    span = (maxs - mins).max() / 2 * 1.1
    ax.set_xlim(center[0] - span, center[0] + span)
    ax.set_ylim(center[1] - span, center[1] + span)
    ax.set_zlim(center[2] - span, center[2] + span)
    ax.set_box_aspect([1, 1, 1])
    ax.view_init(elev=20, azim=-60)
    ax.set_title(title)
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()
    print(f"saved {out_path}")


if __name__ == "__main__":
    cloth_path, obs_path, out_path, title = sys.argv[1:5]
    render(cloth_path, obs_path, out_path, title)
