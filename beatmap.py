import zipfile
import os
import math


# --- .osz archive handling -------------------------------------------------
def extract_osz(osz_path, extract_to):
    if not os.path.exists(extract_to):
        with zipfile.ZipFile(osz_path, 'r') as z:
            z.extractall(extract_to)


# --- Timing/slider-velocity lookup -----------------------------------------
def _get_beat_length_and_sv(timing_points, time):
    """Finds the beat length (ms per beat) and slider-velocity multiplier in
    effect at a given hit-object time, by scanning timing points up to it."""
    beat_length = 500.0
    sv = 1.0
    for tp_time, tp_beat_length in timing_points:
        if tp_time > time:
            break
        if tp_beat_length > 0:
            beat_length = tp_beat_length
            sv = 1.0
        else:
            sv = -100.0 / tp_beat_length
    return beat_length, sv


# ---------------------------------------------------------------------------
# Slider curve math
#
# osu! slider control points describe a curve, not a polyline: the raw
# points must be turned into an actual Bezier / circular-arc / Catmull-Rom
# path before we can walk along it at constant speed. Doing that with the
# raw control points directly (as if they were points ON the path) makes
# the ball's speed warp wherever the curve bends hard.
# ---------------------------------------------------------------------------

# --- Curve segment splitting -----------------------------------------
def _split_bezier_segments(anchors):
    """osu! encodes a 'red anchor' (hard corner) as a duplicated point, which
    splits one Bezier curve into two independent ones sharing that point."""
    segments = []
    current = [anchors[0]]
    for p in anchors[1:]:
        if p == current[-1]:
            if len(current) >= 2:
                segments.append(current)
            current = [p]
        else:
            current.append(p)
    if len(current) >= 2:
        segments.append(current)
    if not segments:
        segments = [anchors]
    return segments


# --- Bezier curves ('B' sliders) ---------------------------------------
def _bezier_points(control_points, num_points=40):
    """De Casteljau evaluation of a single Bezier segment of any order."""
    if len(control_points) < 2:
        return list(control_points)

    pts = []
    for i in range(num_points + 1):
        t = i / num_points
        temp = list(control_points)
        while len(temp) > 1:
            temp = [
                (temp[j][0] + (temp[j + 1][0] - temp[j][0]) * t,
                 temp[j][1] + (temp[j + 1][1] - temp[j][1]) * t)
                for j in range(len(temp) - 1)
            ]
        pts.append(temp[0])
    return pts


# --- Perfect circle arcs ('P' sliders) ----------------------------------
def _circle_arc_points(p1, p2, p3, num_points=40):
    """'Perfect circle' (P) sliders: the arc through 3 points."""
    ax, ay = p1
    bx, by = p2
    cx, cy = p3

    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-6:
        return [p1, p3]  # collinear, no real circle -> straight line fallback

    ux = ((ax ** 2 + ay ** 2) * (by - cy) + (bx ** 2 + by ** 2) * (cy - ay) +
          (cx ** 2 + cy ** 2) * (ay - by)) / d
    uy = ((ax ** 2 + ay ** 2) * (cx - bx) + (bx ** 2 + by ** 2) * (ax - cx) +
          (cx ** 2 + cy ** 2) * (bx - ax)) / d
    center = (ux, uy)
    radius = math.dist(center, p1)
    if radius < 1e-6:
        return [p1, p3]

    def norm(a):
        return a % (2 * math.pi)

    a0 = norm(math.atan2(ay - uy, ax - ux))
    a1 = norm(math.atan2(by - uy, bx - ux))
    a2 = norm(math.atan2(cy - uy, cx - ux))

    ccw_sweep = norm(a2 - a0)
    a1_rel = norm(a1 - a0)
    sweep = ccw_sweep if a1_rel <= ccw_sweep else ccw_sweep - 2 * math.pi

    return [
        (ux + radius * math.cos(a0 + sweep * (i / num_points)),
         uy + radius * math.sin(a0 + sweep * (i / num_points)))
        for i in range(num_points + 1)
    ]


# --- Catmull-Rom curves ('C' sliders) -----------------------------------
def _catmull_rom_points(anchors, per_segment=16):
    if len(anchors) < 2:
        return list(anchors)
    pts = [anchors[0]] + anchors + [anchors[-1]]
    result = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for j in range(per_segment):
            t = j / per_segment
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            result.append((x, y))
    result.append(anchors[-1])
    return result


# --- Curve type dispatch -------------------------------------------------
def _generate_curve_path(curve_type, anchors):
    """Turns a slider's raw anchor points into a walkable, densely-sampled
    path, using whichever curve algorithm the beatmap specifies ('L'inear,
    'P'erfect circle, 'C'atmull-Rom, or 'B'ezier/unknown)."""
    if len(anchors) < 2:
        return list(anchors)

    if curve_type == 'P' and len(anchors) == 3:
        return _circle_arc_points(anchors[0], anchors[1], anchors[2])

    if curve_type == 'L':
        return list(anchors)

    if curve_type == 'C':
        return _catmull_rom_points(anchors)

    # 'B' (Bezier) and unknown types default to Bezier, which is what osu!
    # itself falls back to.
    path = []
    for seg in _split_bezier_segments(anchors):
        seg_points = _bezier_points(seg)
        if path and seg_points and path[-1] == seg_points[0]:
            path.extend(seg_points[1:])
        else:
            path.extend(seg_points)
    return path if len(path) >= 2 else list(anchors)


# --- Fitting the sampled curve to the beatmap's declared length -----------
def _path_with_cumulative_length(path_points, target_length):
    """Trims (or slightly extends) the sampled curve so its total length
    matches the beatmap's declared slider length exactly, and returns the
    running distance at each point so a caller can walk it at constant
    speed regardless of how the curve bends."""
    if len(path_points) < 2 or target_length <= 0:
        return path_points, [0.0] * len(path_points)

    cum = [0.0]
    for i in range(1, len(path_points)):
        cum.append(cum[-1] + math.dist(path_points[i - 1], path_points[i]))

    total = cum[-1]
    if total <= 0:
        return path_points, cum

    if total > target_length:
        trimmed = [path_points[0]]
        trimmed_cum = [0.0]
        for i in range(1, len(path_points)):
            if cum[i] >= target_length:
                seg_len = cum[i] - cum[i - 1]
                t = (target_length - cum[i - 1]) / seg_len if seg_len > 0 else 0
                t = max(0.0, min(1.0, t))
                p0, p1 = path_points[i - 1], path_points[i]
                trimmed.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
                trimmed_cum.append(target_length)
                return trimmed, trimmed_cum
            trimmed.append(path_points[i])
            trimmed_cum.append(cum[i])
        return trimmed, trimmed_cum

    if total < target_length:
        dx = path_points[-1][0] - path_points[-2][0]
        dy = path_points[-1][1] - path_points[-2][1]
        seg_len = math.hypot(dx, dy) or 1.0
        extra = target_length - total
        extended = (path_points[-1][0] + dx / seg_len * extra,
                    path_points[-1][1] + dy / seg_len * extra)
        return path_points + [extended], cum + [target_length]

    return path_points, cum


def load_beatmap(path):
    """Parses one .osu file into a list of raw hit-object dicts (circles,
    sliders, spinners) plus the audio filename. Reads the file in two
    passes: first General/Difficulty/TimingPoints (needed to compute
    slider durations), then HitObjects (which needs that data already
    available)."""
    hit_objects = []
    audio_filename = None
    slider_multiplier = 1.4
    timing_points = []
    section = None

    with open(path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    # --- Pass 1: General / Difficulty / TimingPoints ------------------
    for line in lines:
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
            continue

        if section == 'General' and line.startswith('AudioFilename'):
            audio_filename = line.split(':', 1)[1].strip()

        if section == 'Difficulty' and line.startswith('SliderMultiplier'):
            slider_multiplier = float(line.split(':', 1)[1].strip())

        if section == 'TimingPoints':
            parts = line.split(',')
            if len(parts) >= 2:
                timing_points.append((float(parts[0]), float(parts[1])))

    timing_points.sort(key=lambda t: t[0])

    # --- Pass 2: HitObjects ----------------------------------------------
    section = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
            continue

        if section != 'HitObjects':
            continue

        parts = line.split(',')
        x = int(parts[0])
        y = int(parts[1])
        time = int(parts[2])
        obj_type = int(parts[3])
        new_combo = bool(obj_type & 4)  # bit 2 = new combo start

        if obj_type & 8:  # spinner
            end_time = int(parts[5])
            hit_objects.append({
                'type': 'spinner', 'x': x, 'y': y,
                'time': time, 'end_time': end_time,
                'new_combo': new_combo,
            })

        elif obj_type & 2:  # slider
            curve_data = parts[5]
            curve_parts = curve_data.split('|')
            curve_type = curve_parts[0] if curve_parts and curve_parts[0] else 'B'
            anchors = [(x, y)]
            for p in curve_parts[1:]:
                px, py = p.split(':')
                anchors.append((int(float(px)), int(float(py))))

            slides = int(parts[6])
            length = float(parts[7])

            raw_path = _generate_curve_path(curve_type, anchors)
            path_points, path_cum = _path_with_cumulative_length(raw_path, length)

            beat_length, sv = _get_beat_length_and_sv(timing_points, time)
            px_per_beat = slider_multiplier * 100 * sv
            duration_per_slide = (length / px_per_beat) * beat_length if px_per_beat else 0
            end_time = time + int(duration_per_slide * slides)

            hit_objects.append({
                'type': 'slider', 'x': x, 'y': y,
                'time': time, 'end_time': end_time,
                'points': anchors,
                'path_points': path_points,
                'path_cum_lengths': path_cum,
                'path_length': path_cum[-1] if path_cum else length,
                'slides': slides,
                'duration_per_slide': duration_per_slide,
                'new_combo': new_combo,
            })

        elif obj_type & 1:  # circle
            hit_objects.append({
                'type': 'circle', 'x': x, 'y': y,
                'time': time, 'new_combo': new_combo,
            })

    # HitObjects in a .osu file are already time-ordered, but sort
    # defensively in case a mapset ever isn't.
    hit_objects.sort(key=lambda o: o['time'])
    return hit_objects, audio_filename
