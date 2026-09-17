import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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


def render(cloth_path, out_path, title, elev=25, azim=-50):
    cv, cf = load_obj(cloth_path)
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection="3d")
    tris = [cv[f] for f in cf]
    coll = Poly3DCollection(tris, facecolor=(0.92, 0.9, 0.82, 1.0),
                             edgecolor=(0.25, 0.25, 0.25, 0.4), linewidths=0.15)
    ax.add_collection3d(coll)
    mins, maxs = cv.min(axis=0), cv.max(axis=0)
    center = (mins + maxs) / 2
    span = max((maxs - mins).max() / 2 * 1.15, 1e-3)
    ax.set_xlim(center[0] - span, center[0] + span)
    ax.set_ylim(center[1] - span, center[1] + span)
    ax.set_zlim(center[2] - span, center[2] + span)
    ax.set_box_aspect([1, 1, 1])
    ax.view_init(elev=elev, azim=azim)
    ax.set_title(f"{title} ({len(cf)} faces)")
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()
    print(f"saved {out_path}")


if __name__ == "__main__":
    cloth_path, out_path, title = sys.argv[1:4]
    render(cloth_path, out_path, title)
