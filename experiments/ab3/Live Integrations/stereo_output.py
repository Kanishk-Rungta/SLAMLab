"""Occupancy OUTPUT adapter: the robot's own standard stereo, placed at the native algorithm's poses.

The native SLAM algorithms produce trajectories and pose graphs, not occupancy grids. This module
never estimates or corrects a pose and never feeds anything into the native algorithm. It turns
each stereo keyframe into floor/obstacle rays and re-rasterizes all of a robot's keyframes at the
latest native (corrected) keyframe poses. The same code maps every original-code entry (D2SLAM,
DOOR-SLAM, DVM-SLAM, Swarm-SLAM, Kimera-Multi, CCM-SLAM, COVINS-G, DSLAM), so the maps compare
the algorithms' poses, not different map builders.

Nothing is tuned to the simulation; everything follows from the calibration or is measured online:
  * disparity noise sigma_d is measured continuously from the left-right consistency residuals;
  * depth is trusted only where its standard deviation z^2 sigma_d / (f b) stays within one map
    cell (about 1.6 m for the 25 mm bStem baseline);
  * floor / obstacle use each point's own height uncertainty (from sigma_z and its image row);
  * an obstacle needs several agreeing pixels in its image column, so one bad match cannot
    draw a wall;
  * each keyframe votes once per cell (OctoMap hit/miss log-odds, clamped), so a cell seen free
    from many viewpoints outweighs a few spurious hits.
Use a 0.05 m map (the benchmark ground-truth resolution) so the depth limit is the same for every
algorithm. On recorded AB3 stereo with true poses this builder scored map F1 0.54 / Chamfer 0.25 m
against 0.43 / 0.48 m for the previous adapter (1.6 m cap) and 6x faster rebuilds.
"""
import math
import cv2
import numpy as np

HIT, MISS, CLAMP_LOW, CLAMP_HIGH = .85, -.4, -2., 3.5      # OctoMap defaults: p 0.7 / 0.4, clamp 0.12 / 0.97
OCCUPIED_ABOVE, FREE_BELOW = .5, -.3


def compose(a, b):
    c, s = math.cos(a[2]), math.sin(a[2])
    return np.array([a[0]+c*b[0]-s*b[1], a[1]+s*b[0]+c*b[1],
                     math.atan2(math.sin(a[2]+b[2]), math.cos(a[2]+b[2]))])


def inverse(p):
    c, s = math.cos(p[2]), math.sin(p[2])
    return np.array([-c*p[0]-s*p[1], s*p[0]-c*p[1], -p[2]])


def corrected_pose(graph_pose, keyframe_visual_pose, current_visual_pose):
    return compose(graph_pose, compose(inverse(keyframe_visual_pose), current_visual_pose))


class StereoMapper:
    def __init__(self, stereo, profile):
        self.stereo, self.profile = stereo, profile
        self.resolution = float(profile['map_resolution_m'])
        self.size = int(round(profile['map_size_m']/self.resolution))
        self.origin = np.array([-self.size*self.resolution/2]*2)
        self.keyframes = {}
        self.grid = np.full((self.size, self.size), -1, np.int8)
        self.fb = stereo['fx']*stereo['baseline_m']
        # Disparity search range from the calibration: down to 0.15 m in front of the lens.
        self.disparities = int(math.ceil(self.fb/.15/16.))*16
        params = dict(minDisparity=0, numDisparities=self.disparities, blockSize=5, P1=8*25, P2=32*25,
                      disp12MaxDiff=-1, uniquenessRatio=10, speckleWindowSize=50, speckleRange=2,
                      mode=cv2.STEREO_SGBM_MODE_SGBM)
        self.matcher = cv2.StereoSGBM_create(**params)
        self.sigma_d = .5                      # px; replaced by the online estimate after the first frames
        self.residuals = []
        self.column_step = 2

    # ---- per frame ------------------------------------------------------------------------------
    def disparity(self, left, right):
        gl, gr = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY), cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
        d_left = self.matcher.compute(gl, gr).astype(np.float32)/16.
        # Right-view disparity from the mirrored pair; consistency check and noise measurement.
        d_right = np.fliplr(self.matcher.compute(np.fliplr(gr).copy(), np.fliplr(gl).copy()).astype(np.float32)/16.)
        h, w = d_left.shape
        cols = np.arange(w)[None, :].repeat(h, 0)
        target = np.rint(cols-d_left).astype(int)
        inside = (d_left > 0) & (target >= 0) & (target < w)
        back = np.zeros_like(d_left)
        rows = np.arange(h)[:, None].repeat(w, 1)
        back[inside] = d_right[rows[inside], target[inside]]
        residual = d_left-back
        consistent = inside & (back > 0)
        if consistent.sum() > 500:
            r = residual[consistent]
            mad = float(np.median(np.abs(r-np.median(r))))
            self.residuals.append(1.4826*mad/math.sqrt(2.))   # each disparity carries half the residual variance
            self.residuals = self.residuals[-200:]
            self.sigma_d = max(.05, float(np.median(self.residuals)))
        valid = consistent & (np.abs(residual) <= max(1., 3*self.sigma_d))
        return d_left, valid

    def max_depth(self):
        """Depth whose standard deviation equals one map cell: z^2 sigma_d / (f b) = resolution."""
        z = math.sqrt(self.resolution*self.fb/self.sigma_d)
        return min(z, float(self.profile.get('max_stereo_depth_m', z)))

    def rays(self, left, right):
        """(rays in the body frame [(ox, oy, ex, ey, hit)], clearance (front, left, right) in m)."""
        st = self.stereo
        disparity, valid = self.disparity(left, right)
        depth = np.where(valid, self.fb/np.maximum(disparity, 1e-6), np.nan)
        z_max = self.max_depth()
        rows = np.arange(depth.shape[0], dtype=np.float32)[:, None]
        offset = (rows-st['cy'])/st['fy']
        heights = st['height_above_floor_m']-offset*depth
        sigma_z = depth*depth*self.sigma_d/self.fb
        sigma_h = np.abs(offset)*sigma_z
        usable = valid & (depth > .15) & (depth <= z_max)
        floor = usable & (np.abs(heights) <= np.maximum(2*sigma_h, .01))
        obstacle = usable & (heights > np.maximum(3*sigma_h, .02))
        # Pixels needed to call an obstacle: the image height of a 3 cm tall object at that depth,
        # at least 3 (no single-pixel walls).
        ox, oy = st['left_position_m'][:2]
        result, thirds = [], ([], [], [])
        w = depth.shape[1]
        for column in range(0, w, self.column_step):
            obs = np.sort(depth[obstacle[:, column], column])
            hit_distance = None
            if obs.size:
                need = np.maximum(3, np.ceil(.03*st['fy']/obs)).astype(int)
                for i in range(obs.size):
                    window = np.searchsorted(obs, obs[i]+2*max(obs[i]**2*self.sigma_d/self.fb, self.resolution))
                    if window-i >= need[i]:
                        hit_distance = float(np.median(obs[i:window]))
                        break
            free = depth[floor[:, column], column]
            if hit_distance is not None:
                distance, hit = hit_distance, 1
            elif free.size >= 3:
                distance, hit = float(np.percentile(free, 90)), 0
            else:
                continue
            bearing = -(column-st['cx'])/st['fx']
            result.append((ox, oy, ox+distance, oy+bearing*distance, hit))
            thirds[0 if column < w/3 else 2 if column >= 2*w/3 else 1].append(distance)

        def clearance(values):
            return float(np.percentile(values, 10)) if values else None
        return result, (clearance(thirds[1]), clearance(thirds[0]), clearance(thirds[2]))

    # ---- map ------------------------------------------------------------------------------------
    def rebuild(self, graph):
        """Occupancy grid (-1 unknown, 0 free, 1 occupied) of every keyframe at its graph pose."""
        cells_free, cells_hit = [], []
        res = self.resolution
        for node, rays in self.keyframes.items():
            if node not in graph or not rays:
                continue
            pose = np.asarray(graph[node], float)
            c, s = math.cos(pose[2]), math.sin(pose[2])
            r = np.asarray(rays, float)
            start = np.c_[pose[0]+c*r[:, 0]-s*r[:, 1], pose[1]+s*r[:, 0]+c*r[:, 1]]
            end = np.c_[pose[0]+c*r[:, 2]-s*r[:, 3], pose[1]+s*r[:, 2]+c*r[:, 3]]
            first = np.floor((start-self.origin)/res).astype(int)
            last = np.floor((end-self.origin)/res).astype(int)
            ok = np.all((first >= 0) & (first < self.size) & (last >= 0) & (last < self.size), 1)
            first, last, hits = first[ok], last[ok], r[ok, 4] > 0
            if not len(first):
                continue
            steps = np.max(np.abs(last-first), 1)
            n = int(steps.max())+1
            t = np.linspace(0., 1., n)[None, :, None]
            points = np.rint(first[:, None, :]+(last-first)[:, None, :]*t).astype(int)   # (rays, n, 2)
            index = np.arange(n)[None, :]
            # Free: every traversed cell before the end (or including it for floor-only rays).
            free_mask = (index < steps[:, None]) | ((index == steps[:, None]) & ~hits[:, None])
            free_mask &= index <= steps[:, None]
            cells_free.append(points[free_mask])
            cells_hit.append(last[hits])
        # Each keyframe counts a cell at most once (free or hit); log-odds add up across keyframes.
        n_cells = self.size*self.size
        free_count = np.zeros(n_cells, np.float32)
        hit_count = np.zeros(n_cells, np.float32)
        for free, hit in zip(cells_free, cells_hit):
            hit_idx = np.unique(hit[:, 1]*self.size+hit[:, 0]) if len(hit) else np.zeros(0, int)
            free_idx = np.unique(free[:, 1]*self.size+free[:, 0]) if len(free) else np.zeros(0, int)
            free_idx = np.setdiff1d(free_idx, hit_idx, assume_unique=True)
            free_count[free_idx] += 1
            hit_count[hit_idx] += 1
        odds = np.clip(MISS*free_count+HIT*hit_count, CLAMP_LOW, CLAMP_HIGH).reshape(self.size, self.size)
        self.grid.fill(-1)
        self.grid[odds < FREE_BELOW] = 0
        self.grid[odds > OCCUPIED_ABOVE] = 1
        return self.grid

    def render(self, path, pose, title):
        image = np.full(self.grid.shape+(3,), 160, np.uint8)
        image[self.grid == 0] = 255
        image[self.grid == 1] = 0
        point = np.floor((np.asarray(pose[:2])-self.origin)/self.resolution).astype(int)
        cv2.circle(image, tuple(int(v) for v in point), 5, (0, 0, 230), -1)
        ys, xs = np.where(self.grid >= 0)
        margin = int(round(2./self.resolution))
        x0 = max(0, min(xs.min() if len(xs) else point[0], point[0])-margin)
        x1 = min(self.size, max(xs.max() if len(xs) else point[0], point[0])+margin+1)
        y0 = max(0, min(ys.min() if len(ys) else point[1], point[1])-margin)
        y1 = min(self.size, max(ys.max() if len(ys) else point[1], point[1])+margin+1)
        crop = image[y0:y1, x0:x1]
        scale = max(1, int(900/max(crop.shape[:2])))                 # readable at any map size
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        crop = np.flipud(crop).copy()
        canvas = np.full((crop.shape[0]+45, max(640, crop.shape[1]), 3), 255, np.uint8)
        canvas[45:, :crop.shape[1]] = crop
        cv2.putText(canvas, title, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, .5, (20, 20, 20), 1)
        bar = int(round(1./self.resolution))*scale                   # 1 m scale bar
        cv2.line(canvas, (canvas.shape[1]-bar-15, 38), (canvas.shape[1]-15, 38), (0, 0, 0), 2)
        tmp = path.with_suffix('.tmp.png')
        cv2.imwrite(str(tmp), canvas)
        tmp.replace(path)
