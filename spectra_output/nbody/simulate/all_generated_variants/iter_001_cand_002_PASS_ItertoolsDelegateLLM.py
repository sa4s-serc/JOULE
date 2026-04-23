# ============================================================
# Iteration: 1
# Operator:  ItertoolsDelegateLLM
# Status:    PASS
# ============================================================

import itertools

PI = 3.14159265358979323
SOLAR_MASS = 4 * PI * PI
DAYS_PER_YEAR = 365.24

# Initial state stored as immutable tuples so each simulate() call gets a fresh copy.
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
    return itertools.combinations(bodies, 2)


def simulate(n):
    bodies = _fresh_bodies()
    pairs = _combinations(bodies)

    # Offset momentum so centre-of-mass velocity is zero (applied to sun).
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

    # Symplectic integrator.
    dt = 0.01
    for _ in range(n):
        # Re-create pairs for each iteration if _combinations returns an iterator
        # or if bodies are modified in place and combinations need to reflect that.
        # In this specific case, bodies are modified in place, but the *structure*
        # of the pairs (which bodies are paired) remains the same.
        # However, the values within the bodies (r, v) are modified.
        # itertools.combinations creates an iterator that yields tuples of references
        # to the original list elements. So, if the elements themselves are mutable
        # (like the lists [r[0], r[1], r[2]] and [v[0], v[1], v[2]]),
        # the references in the yielded tuples will point to the *same* mutable objects.
        # Therefore, re-creating the iterator is not strictly necessary for correctness
        # if the original `pairs` was an iterator, but it's harmless.
        # If `pairs` was a list, it would not need to be re-created.
        # Given the original `_combinations` returned a list, we should ensure
        # the new one behaves similarly or that the change is semantically equivalent.
        # itertools.combinations returns an iterator, so we need to convert it to a list
        # if the original code relied on `pairs` being a list that could be iterated
        # multiple times without re-computation.
        # However, the loop `for _ in range(n)` iterates `n` times, and inside it,
        # `for ... in pairs:` is called. If `pairs` is an iterator, it would be exhausted
        # after the first `_` iteration. So, `pairs` *must* be re-created or be a list.
        # The original `_combinations` returned a list, so we must preserve that.
        current_pairs = list(itertools.combinations(bodies, 2))
        for (([x1, y1, z1], v1, m1),
             ([x2, y2, z2], v2, m2)) in current_pairs:
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

    # Total energy (kinetic + potential).
    e = 0.0
    # The energy calculation also iterates over pairs. If `pairs` was an iterator
    # and not re-created, it would be exhausted. So, it must be re-created here too.
    # Or, if `current_pairs` was stored, it could be reused.
    # To match the original semantics where `pairs` was a list, we'll re-create it.
    final_pairs = list(itertools.combinations(bodies, 2))
    for (((x1, y1, z1), v1, m1),
         ((x2, y2, z2), v2, m2)) in final_pairs:
        dx = x1 - x2
        dy = y1 - y2
        dz = z1 - z2
        e -= (m1 * m2) / ((dx * dx + dy * dy + dz * dz) ** 0.5)
    for (r, [vx, vy, vz], m) in bodies:
        e += m * (vx * vx + vy * vy + vz * vz) / 2.0
    return e