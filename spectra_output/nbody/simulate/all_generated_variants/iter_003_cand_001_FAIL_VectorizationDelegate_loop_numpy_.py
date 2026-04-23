# ============================================================
# Iteration: 3
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    FAIL
# Reason:    Exception[NameError] on args=(10000,): name 'distance_cub' is not defined
# ============================================================

import numpy as np

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
    initial_positions = np.array([list(body[0]) for body in _INITIAL_BODIES])
    initial_velocities = np.array([list(body[1]) for body in _INITIAL_BODIES])
    initial_masses = np.array([body[2] for body in _INITIAL_BODIES])
    return initial_positions, initial_velocities, initial_masses


def simulate(n):
    positions, velocities, masses = _fresh_bodies()
    num_bodies = len(masses)

    total_momentum = (velocities * masses[:, np.newaxis]).sum(axis=0)
    velocities[0] = -total_momentum / masses[0]

    dt = 0.01
    
    i_indices, j_indices = np.triu_indices(num_bodies, k=1)

    for _ in range(n):
        r_diff = positions[i_indices] - positions[j_indices]
        distance_sq = np.sum(r_diff * r_diff, axis=1)
        distance_cubed = distance_sq * np.sqrt(distance_sq)
        
        mag_factor = dt / distance_cub