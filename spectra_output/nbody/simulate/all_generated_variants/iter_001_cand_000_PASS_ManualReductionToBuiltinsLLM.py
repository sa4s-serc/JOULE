# ============================================================
# Iteration: 1
# Operator:  ManualReductionToBuiltinsLLM
# Status:    PASS
# ============================================================

PI = 3.14159265358979323
SOLAR_MASS = 4 * PI * PI
DAYS_PER_YEAR = 365.24

_INITIAL_BODIES = (
    ((0.0, 0.0, 0.0),
     (0.0, 0.0, 0.0),
     SOLAR_MASS),

    ((4.84143144246472090e+00,
      -1.16032004402742839e+00,
      -1.03622044471123109e-01),
     (1.66007664274403694e-03 * DAYS_PER_YEAR,
      7.69901118419740425e-03 * DAYS_PER_YEAR,
      -6.90460016972063023e-05 * DAYS_PER_YEAR),
     9.54791938424326609e-04 * SOLAR_MASS),

    ((8.34336671824457987e+00,
      4.12479856412430479e+00,
      -4.03523417114321381e-01),
     (-2.76742510726862411e-03 * DAYS_PER_YEAR,
      4.99852801234917238e-03 * DAYS_PER_YEAR,
      2.30417297573763929e-05 * DAYS_PER_YEAR),
     2.85885980666130812e-04 * SOLAR_MASS),

    ((1.28943695621391310e+01,
      -1.51111514016986312e+01,
      -2.23307578892655734e-01),
     (2.96460137564761618e-03 * DAYS_PER_YEAR,
      2.37847173959480950e-03 * DAYS_PER_YEAR,
      -2.96589568540237556e-05 * DAYS_PER_YEAR),
     4.36624404335156298e-05 * SOLAR_MASS),

    ((1.53796971148509165e+01,
      -2.59193146099879641e+01,
      1.79258772950371181e-01),
     (2.68067772490389322e-03 * DAYS_PER_YEAR,
      1.62824170038242295e-03 * DAYS_PER_YEAR,
      -9.51592254519715870e-05 * DAYS_PER_YEAR),
     5.15138902046611451e-05 * SOLAR_MASS),
)


def _fresh_bodies():
    return [([r[0], r[1], r[2]], [v[0], v[1], v[2]], m)
            for r, v, m in _INITIAL_BODIES]


def _combinations(bodies):
    result = []
    for i in range(len(bodies) - 1):
        for j in range(i + 1, len(bodies)):
            result.append((bodies[i], bodies[j]))
    return result


def simulate(n):
    bodies = _fresh_bodies()
    pairs = _combinations(bodies)

    px = -sum(v[0] * m for (r, v, m) in bodies)
    py = -sum(v[1] * m for (r, v, m) in bodies)
    pz = -sum(v[2] * m for (r, v, m) in bodies)

    sun_v = bodies[0][1]
    sun_m = bodies[0][2]
    sun_v[0] = px / sun_m
    sun_v[1] = py / sun_m
    sun_v[2] = pz / sun_m

    dt = 0.01
    for _ in range(n):
        for (([x1, y1, z1], v1, m1),
             ([x2, y2, z2], v2, m2)) in pairs:
            dx = x1 - x2
            dy = y1 - y2
            dz = z1 - z2
            mag = dt * ((dx * dx + dy * dy + dz * dz) ** (-1.5))
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

    e_potential = sum(-(m1 * m2) / (((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2) ** 0.5)
                      for (((x1, y1, z1), v1, m1),
                           ((x2, y2, z2), v2, m2)) in pairs)
    
    e_kinetic = sum(m * (v[0]*v[0] + v[1]*v[1] + v[2]*v[2]) / 2.0
                    for (r, v, m) in bodies)

    e = e_potential + e_kinetic
    return e