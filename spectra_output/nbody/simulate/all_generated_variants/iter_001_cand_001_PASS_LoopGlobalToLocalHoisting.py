# ============================================================
# Iteration: 1
# Operator:  LoopGlobalToLocalHoisting
# Status:    PASS
# ============================================================

PI = 3.141592653589793
SOLAR_MASS = 4 * PI * PI
DAYS_PER_YEAR = 365.24
_INITIAL_BODIES = (((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), SOLAR_MASS), ((4.841431442464721, -1.1603200440274284, -0.10362204447112311), (0.001660076642744037 * DAYS_PER_YEAR, 0.007699011184197404 * DAYS_PER_YEAR, -6.90460016972063e-05 * DAYS_PER_YEAR), 0.0009547919384243266 * SOLAR_MASS), ((8.34336671824458, 4.124798564124305, -0.4035234171143214), (-0.002767425107268624 * DAYS_PER_YEAR, 0.004998528012349172 * DAYS_PER_YEAR, 2.3041729757376393e-05 * DAYS_PER_YEAR), 0.0002858859806661308 * SOLAR_MASS), ((12.894369562139131, -15.111151401698631, -0.22330757889265573), (0.002964601375647616 * DAYS_PER_YEAR, 0.0023784717395948095 * DAYS_PER_YEAR, -2.9658956854023756e-05 * DAYS_PER_YEAR), 4.366244043351563e-05 * SOLAR_MASS), ((15.379697114850917, -25.919314609987964, 0.17925877295037118), (0.0026806777249038932 * DAYS_PER_YEAR, 0.001628241700382423 * DAYS_PER_YEAR, -9.515922545197159e-05 * DAYS_PER_YEAR), 5.1513890204661145e-05 * SOLAR_MASS))

def _fresh_bodies():
    return [([r[0], r[1], r[2]], [v[0], v[1], v[2]], m) for (r, v, m) in _INITIAL_BODIES]

def _combinations(bodies):
    _local_len = len
    _local_range = range
    result = []
    for i in _local_range(_local_len(bodies) - 1):
        for j in _local_range(i + 1, _local_len(bodies)):
            result.append((bodies[i], bodies[j]))
    return result

def simulate(n):
    _local_range = range
    bodies = _fresh_bodies()
    pairs = _combinations(bodies)
    px = py = pz = 0.0
    for (r, v, m) in bodies:
        px -= v[0] * m
        py -= v[1] * m
        pz -= v[2] * m
    sun_v = bodies[0][1]
    sun_m = bodies[0][2]
    sun_v[0] = px / sun_m
    sun_v[1] = py / sun_m
    sun_v[2] = pz / sun_m
    dt = 0.01
    for _ in _local_range(n):
        for (([x1, y1, z1], v1, m1), ([x2, y2, z2], v2, m2)) in pairs:
            dx = x1 - x2
            dy = y1 - y2
            dz = z1 - z2
            mag = dt * (dx * dx + dy * dy + dz * dz) ** (-1.5)
            b1m = m1 * mag
            b2m = m2 * mag
            v1[0] -= dx * b2m
            v1[1] -= dy * b2m
            v1[2] -= dz * b2m
            v2[0] += dx * b1m
            v2[1] += dy * b1m
            v2[2] += dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx
            r[1] += dt * vy
            r[2] += dt * vz
    e = 0.0
    for (((x1, y1, z1), v1, m1), ((x2, y2, z2), v2, m2)) in pairs:
        dx = x1 - x2
        dy = y1 - y2
        dz = z1 - z2
        e -= m1 * m2 / (dx * dx + dy * dy + dz * dz) ** 0.5
    for (r, [vx, vy, vz], m) in bodies:
        e += m * (vx * vx + vy * vy + vz * vz) / 2.0
    return e