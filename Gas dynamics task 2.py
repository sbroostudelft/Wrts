import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass

#DATACLASS
@dataclass(frozen=True)
class State:
    x: float
    y: float
    M: float
    nu: float
    phi: float

    @property
    def mu(self) -> float:
        return np.arcsin(1.0 / self.M)

    @property
    def P(self):
        return (self.x, self.y)

data: dict[tuple[int,int,int], State] = {}




##########################
# GAS DYNAMICS FUNCTIONS #
##########################
def prandtl_meyer(M, gamma):
    """ν(M) in radians."""
    if M < 1.0:
        raise ValueError("Mach must be >= 1 for Prandtl–Meyer.")
    term1 = np.sqrt((gamma + 1) / (gamma - 1))
    term2 = np.arctan(np.sqrt((gamma - 1) * (M**2 - 1) / (gamma + 1)))
    term3 = np.arctan(np.sqrt(M**2 - 1))
    return term1 * term2 - term3

def nu_inv(target_nu, gamma, M_guess=2.0, tol=1e-10, itmax=50):
    """Invert ν(M)=target_nu (both in radians) using Newton."""
    M = max(1.0001, M_guess)
    for _ in range(itmax):
        # f(M) = ν(M) - target_nu
        nu_M = prandtl_meyer(M, gamma)
        f = nu_M - target_nu
        if abs(f) < tol:
            return M
        # Derivative dν/dM (from standard formula)
        dnudM = (np.sqrt(M**2 - 1) / (1 + 0.5*(gamma - 1)*M**2)) / M
        M -= f / dnudM
        if M < 1.0:
            M = 1.0001
    return M  # best effort

def pe_over_p0_from_M(M, gamma):
    """Isentropic: p/p0 at M."""
    return (1 + 0.5*(gamma-1)*M**2)**(-gamma/(gamma-1))

def M_from_pe_over_p0(p_over_p0, gamma, M_guess=2.0):
    """Invert p/p0 to M with Newton via ν as a robust parameterization."""
    # Use a simple Newton directly on p/p0(M)
    M = max(1.0001, M_guess)
    for _ in range(60):
        f = pe_over_p0_from_M(M, gamma) - p_over_p0
        if abs(f) < 1e-12:
            return M
        # derivative dp/p0 / dM
        g = pe_over_p0_from_M(M, gamma)
        dgdM = g * (-gamma/(gamma-1)) * ( (0.5*(gamma-1)*2*M) / (1 + 0.5*(gamma-1)*M**2) )
        M -= f / dgdM
        if M < 1.0:
            M = 1.0001
    return M

def intersect_with_axis(x0, y0, slope, axis_y=0.0):
    if abs(slope) < 1e-14:
        print("no slope; ERROR")
        return np.inf, axis_y
    x_axis = x0 + (axis_y - y0) / slope
    return x_axis, axis_y

def intersect_two_lines(P, slopeP, Q, slopeQ):
    """Intersect y = yP + (x-xP)*mP with y = yQ + (x-xQ)*mQ."""
    xP, yP = P
    xQ, yQ = Q
    denom = (slopeP - slopeQ)
    if abs(denom) < 1e-14:
        print("found two parallel curves; ERROR")
        return np.nan, np.nan
    x = (yQ - yP + xP*slopeP - xQ*slopeQ) / denom
    y = yP + (x - xP) * slopeP
    return x, y


def compute_node_from_AB(A: State, B: State, gamma: float, M_guess: float, z: int, i: int, j: int):
    #MAIN COMPUTATION FUNCTION
    if z % 2 == 0:
        Kp = A.nu - A.phi  # V+ at A
        Km = B.nu + B.phi  # V- at B

        nu = 0.5 * (Kp + Km)
        phi = 0.5 * (Km - Kp)

        M = nu_inv(nu, gamma, M_guess=M_guess)
        mu = np.arcsin(1.0 / M)

        m_plus = np.tan(0.5 * ((A.phi + A.mu) + (phi + mu)))  # Γ+ slope uses (phi+mu)
        m_minus = np.tan(0.5 * ((B.phi - B.mu) + (phi - mu)))  # Γ- slope uses (phi-mu)


    else: #P_p = P_a -> M = Mb; nu = constant over the boundary

        if i == j: #We retrieve a boundary point, so we enforce the boundary condition
            M = Mb
            nu = nu_b
            phi = nu - A.nu + A.phi
            if i == 0:
                m_minus = np.tan(B.phi) #We want an intersection with the boundary line
            else:
                m_minus = np.tan(0.5*(B.phi+phi)) #We want an intersection with the boundary line

        else: #Normal interior point
            Kp = A.nu - A.phi  # V+ at A
            Km = B.nu + B.phi  # V- at B

            nu = 0.5 * (Kp + Km)
            phi = 0.5 * (Km - Kp)
            M = nu_inv(nu, gamma, M_guess=M_guess)

            m_minus = np.tan(0.5 * ((B.phi - B.mu) + (phi - np.arcsin(1.0 / M))))

        m_plus = np.tan(0.5 * ((A.phi + A.mu) + (phi + np.arcsin(1.0 / M))))


    x, y = intersect_two_lines(A.P, m_plus, B.P, m_minus) #Intersect the two characteristic lines with averaged slopes of BP and AP

    return State(x=x, y=y, M=M, nu=nu, phi=phi)

def lip_state(j, lip, thetas, nu_e, gamma, Me):
    # Retrieve the state at the nozzle lip for the j-th characteristic
    theta = thetas[j]
    nu    = nu_e + theta
    M     = nu_inv(nu, gamma, M_guess=Me)
    phi   = theta
    return State(x=lip[0], y=lip[1], M=M, nu=nu, phi=phi)

def axis_mirrored_state(state: State):
    #For even z-fans, some states come from the axis, so we need to mirror y and phi, technically not cheating, errors: O(1e-14).
    return State(x=state.x, y=-state.y, M=state.M, nu=state.nu, phi=-state.phi)

def get_B(data, z, i, j, lip, thetas, nu_e, gamma, Me):
    #RETRIEVE THE STATE OF POINT B, which is the C- origin

    if z%2 == 0: #Even z-fans interact with the symmetry axis
        if z == 0: #Special case: first fan from lip
            if i == 0:
                return lip_state(j, lip, thetas, nu_e, gamma, Me) #Initial C- from lip w/ diff theta, verified
            return data[(z, i-1, j)] #= C- from same fan, verified
        else: #z > 0
            if i == 0:
                return data[(z-1, j, n_chars-1)]  #= last point of previous fan, verified
            return data[(z, i-1, j)]   #= C- from same fan, verified


    else:   #Uneven z-fans interact with the boundary, for i=j there is no C- from interior,
            # but we use phi in the node computation function, so we feed it from the previous boundary point.
        if i == 0 and j == 0 and z == 1: #first boundary comes from lip
            return lip_state(n_chars-1, lip, thetas, nu_e, gamma, Me) #last lip state, verified

        elif i == 0 and j == 0 and not z == 1: #subsequent boundaries come from previous uneven fan
            return data[(z-2, n_chars-1, n_chars-1)] #last point of previous uneven fan, verified

        elif i == j: #else the boundary itterates over the i=j points
            return data[(z, i-1, j-1)] #previous boundary point, verified

        return data[(z, i, j-1)] #Finally, C- from own fan, verified

def get_A(data, z, i, j):
    #RETRIEVE THE STATE OF POINT A, which is the C+ origin
    if z % 2 == 0: #even z-fans interact with the axis
        if i == 0 and j == 0 and z == 0:
            # starting node: use the exit state at the lip, with inverted y and phi
            return State(x=lip[0], y=-lip[1], M=Me, nu=nu_e, phi=0.0) #weirdly written, but verified

        elif i == 0 and j == 0 and not z == 0:
            # coming from boundary at previous fan
            return axis_mirrored_state(data[(z-1, i, n_chars-1)]) #verified

        elif i == j:
            # for points at the axis: use previous interior point and mirror (does it enforce phi=0?)
            return axis_mirrored_state(data[(z, i-1, j)])

        return data[(z, i, j-1)] #Otherwise C+ from same fan

    else: #uneven z-fans interact with the boundary
        if i == 0:
            return data[(z-1, j, n_chars-1)] #load last point of previous fan
        return data[(z, i-1, j)] #C+ from same fan







#SHOCK DETECTION DEFINITIONS
#Create polylines per fan and check for intersections between same-family characteristics
def seg_intersect(P, Q, R, S, eps=1e-12):
    """Return (hit, x, y, t, u). P->Q intersects R->S if hit."""
    Px, Py = P; Qx, Qy = Q
    Rx, Ry = R; Sx, Sy = S
    dx1, dy1 = Qx-Px, Qy-Py
    dx2, dy2 = Sx-Rx, Sy-Ry

    denom = dx1*dy2 - dy1*dx2
    if abs(denom) < eps:
        return False, None, None, None, None  # parallel/collinear (ignore)

    # Solve P + t*(Q-P) = R + u*(S-R)
    t = ((Rx-Px)*dy2 - (Ry-Py)*dx2) / denom
    u = ((Rx-Px)*dy1 - (Ry-Py)*dx1) / denom

    if -eps <= t <= 1+eps and -eps <= u <= 1+eps:
        x = Px + t*dx1
        y = Py + t*dy1
        return True, x, y, t, u
    return False, None, None, None, None


def get_Cplus_polyline(data, z, i, n_chars):
    pts = []
    for j in range(i, n_chars):
        s = data.get((z, i, j))
        if s is not None:
            pts.append((s.x, s.y))
    return pts

def get_Cminus_polyline(data, z, j, n_chars):
    pts = []
    for i in range(0, j+1):
        s = data.get((z, i, j))
        if s is not None:
            pts.append((s.x, s.y))
    return pts



def detect_shock_in_fan(data, z, n_chars):
    """
    Detect first C+ self-intersection in fan z.
    Returns (x_shock, y_shock) or None.
    """
    best = None  # (x, y, i, seg_a, seg_b)

    for i in range(0, n_chars-2):
        A = get_Cplus_polyline(data, z, i, n_chars)
        B = get_Cplus_polyline(data, z, i+1, n_chars)
        if len(A) < 2 or len(B) < 2:
            continue

        # test segment pairs (k on A, m on B)
        for k in range(len(A)-1):
            P, Q = A[k], A[k+1]
            for m in range(len(B)-1):
                R, S = B[m], B[m+1]

                hit, x, y, _, _ = seg_intersect(P, Q, R, S)
                if not hit:
                    continue

                # ignore "intersection" at shared start region near axis/boundary nodes
                # (optional): require x to be beyond both segment starts by some margin
                if x is None:
                    continue

                if best is None or x < best[0]:
                    best = (x, y, i, k, m)

    if best is None:
        return None
    return (best[0], best[1])

def detect_shock_Cminus(data, z, n_chars):
    best = None

    for j in range(1, n_chars-1):
        A = get_Cminus_polyline(data, z, j, n_chars)
        B = get_Cminus_polyline(data, z, j+1, n_chars)
        if len(A) < 2 or len(B) < 2:
            continue

        for k in range(len(A)-1):
            for m in range(len(B)-1):
                hit, x, y, *_ = seg_intersect(A[k], A[k+1], B[m], B[m+1])
                if hit:
                    if best is None or x < best[0]:
                        best = (x, y)

    return best






#######################
# PLOTTING FUNCTIONS#
#######################

def plot_characteristics_multi_fan(data, n_chars, lip, R_exit, z_max=None):
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm

    # Determine number of fans (z values) present in data if not given
    if z_max is None:
        z_vals = sorted({key[0] for key in data})
        z_max = max(z_vals)
    else:
        z_vals = list(range(z_max + 1))

    fig, ax = plt.subplots(figsize=(10, 5.5))



    # --- Plot extended boundary line (from lip through all (z,i,i) for all z) ---
    boundary_xs = [lip[0]]
    boundary_ys = [lip[1]]
    for z in z_vals:
        if z % 2 == 0:
            continue  # skip even z
        for i in range(n_chars):
            state = data.get((z, i, i))
            if state is not None:
                boundary_xs.append(state.x)
                boundary_ys.append(state.y)
    ax.plot(boundary_xs, boundary_ys, color='k', lw=2.5, alpha=0.85, label="Boundary (all fans)", zorder=20)


    # --- Plot each fan ---
    color_map = cm.get_cmap('tab10', len(z_vals))
    for idx, z in enumerate(z_vals):
        c_minus = color_map(idx)
        c_plus = color_map((idx+1) % len(z_vals))
        pt_color = color_map(idx)
        fan_label = f"Fan z={z}"

        # Initial C− rays
        for j in range(n_chars):
            state = data.get((z, 0, j))
            if state is not None:
                if z == 0:
                    ax.plot([lip[0], state.x], [lip[1], state.y], color=c_minus, lw=1.2, alpha=0.7, ls=':', label="Initial $C^-$ (z=0)" if j == 0 and z == 0 else None)
                else:
                    prev = data.get((z - 1, j, n_chars - 1))  # last mesh point of previous fan
                    if prev is not None:
                        ax.plot([prev.x, state.x], [prev.y, state.y],
                                color=c_minus, lw=1.2, alpha=0.7, ls=':',
                                label=f"Initial $C^-$ (z={z})" if j == 0 else None)
        # C− characteristics
        for j in range(n_chars):
            xs = []
            ys = []
            for i in range(j + 1):
                state = data.get((z, i, j))
                if state is not None:
                    xs.append(state.x)
                    ys.append(state.y)
            if xs and ys:
                ax.plot(xs, ys, color=c_minus, lw=1.2, alpha=0.8, label=r"$C^-$ (z={})".format(z) if j == 0 else None)

        # C+ characteristics
        for i in range(n_chars):
            xs = []
            ys = []
            for j2 in range(i, n_chars):
                state = data.get((z, i, j2))
                if state is not None:
                    xs.append(state.x)
                    ys.append(state.y)
            if xs and ys:
                ax.plot(xs, ys, color=c_plus, lw=1.2, ls='--', alpha=0.8, label=r"$C^+$ (z={})".format(z) if i == 0 else None)

        # All points for this fan
        xs_all = [state.x for key, state in data.items() if key[0] == z]
        ys_all = [state.y for key, state in data.items() if key[0] == z]
        ax.scatter(xs_all, ys_all, c=[pt_color], s=18, zorder=6, label=fan_label)

    # Plot nozzle lip
    ax.scatter([lip[0]], [lip[1]], c='k', s=40, zorder=30, label="Nozzle lip")

    # Plot axis (centerline)
    ax.axhline(0.0, color='k', lw=1.2, alpha=0.6, label="Centerline")

    # Plot shock point if provided
    if shock_point is not None:
        ax.scatter([shock_point[0]], [shock_point[1]], c='r', s=80, marker='*', zorder=50, label="Shock point")

    # Set limits and labels
    all_xs = [state.x for state in data.values()] + [lip[0]]
    all_ys = [state.y for state in data.values()] + [lip[1], 0.0]
    xmax = max(all_xs) * 1.1
    ymax = max(all_ys) * 1.1
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title(f"Characteristic net, Me={Me}, underexpanded jet (p_e/p_a={pe_pa})")
    ax.legend(loc="best", fontsize=8, ncol=2)
    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.show()

def plot_flow_field(data, gamma, R_exit):
    import matplotlib.pyplot as plt
    import numpy as np

    # 1. Extract data from your dictionary
    states = list(data.values())
    x_half = np.array([s.x for s in states])
    y_half = np.array([s.y for s in states])
    m_half = np.array([s.M for s in states])
    # Calculate p/p0 for each point using your existing function
    p_half = np.array([pe_over_p0_from_M(s.M, gamma) for s in states])

    # 2. Mirror the data to show the full jet (top and bottom)
    x = np.concatenate([x_half, x_half])
    y = np.concatenate([y_half, -y_half])
    m = np.concatenate([m_half, m_half])
    p = np.concatenate([p_half, p_half])

    # 3. Create the plots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)

    # Mach Number Plot
    # levels=100 makes the coloring smooth within the "tiles"
    cntr1 = ax1.tricontourf(x, y, m, levels=100, cmap='jet')
    fig.colorbar(cntr1, ax1, label='Mach Number')
    ax1.set_title("Mach Number Distribution")

    # Static Pressure Plot (p/p0)
    cntr2 = ax2.tricontourf(x, y, p, levels=100, cmap='RdYlBu_r')
    fig.colorbar(cntr2, ax2, label='$p/p_0$')
    ax2.set_title("Static Pressure Distribution ($p/p_0$)")

    # 4. Formatting to match your jet shape
    for ax in [ax1, ax2]:
        ax.set_aspect('equal')
        ax.set_ylabel("y / R")
        ax.axhline(0, color='black', lw=1, ls='--') # Centerline
        # Plot the nozzle exit plane
        ax.plot([0, 0], [-R_exit, R_exit], color='black', lw=4)

    ax2.set_xlabel("x / R")
    plt.tight_layout()
    plt.show()




# ---------------------------
# Problem setup
# ---------------------------

#PARAMETERS
gamma = 1.4
Me = 3
pe_pa = 2.0      # underexpanded: exit pressure twice ambient
theta_e = 0.0    # flow parallel to x at exit
n_chars = 10   # number of rays in initial fan (discretize θ or ν)
R_exit = 1.0     # arbitrary scaling for exit half-height (lip y-position)
lip = np.array([0.0, R_exit])   # place nozzle lip at (0, R_exit)
axis_y = 0.0     # centerline y=0

#INITIAL CALCULATION
# Exit ν and μ (in radians)
nu_e = prandtl_meyer(Me, gamma)
mu_e = np.arcsin(1/Me)

# Stagnation pressure scaling (we work up to a factor; ratios matter)
pe_over_p0 = pe_over_p0_from_M(Me, gamma)
pb_over_p0 = pe_over_p0/pe_pa

# Boundary (free jet) condition p = pa on the outer streamline:
Mb = M_from_pe_over_p0(pb_over_p0, gamma, M_guess=max(Me, 2.5))
nu_b = prandtl_meyer(Mb, gamma)

# Total turning of the centered fan at the lip that would relax to p=pa:
theta_b = nu_b - nu_e   # radians, >0 for underexpanded jet
delta_theta = theta_b / (n_chars - 1)

print(f"Exit: Me={Me:.3f}, νe(deg)={np.degrees(nu_e):.3f}, μe(deg)={np.degrees(mu_e):.3f}")
print(f"Target boundary: Mb={Mb:.3f}, νb(deg)={np.degrees(nu_b):.3f}, total turn θb(deg)={np.degrees(theta_b):.3f}")


# ---------------------------
# Initial centered fan (C− family from the lip)
# ---------------------------

#Discretize θ including the endpoints
thetas = np.linspace(0.0, theta_b, n_chars)           # shape: (n_characs,)
nus     = nu_e + thetas                                  # ν = ν_e + theta
Ms  = np.array([nu_inv(nu_i, gamma, M_guess=Me) for nu_i in nus])
mus = np.arcsin(1.0 / Ms)
#print("thetas (deg):", np.degrees(thetas),"\nnus (deg):", np.degrees(nus),"\nMs:", Ms,"\nmus (deg):", np.degrees(mus))

slopes_Cm = np.tan(thetas - mus)
axis_intersection_points = np.array([intersect_with_axis(lip[0], lip[1], s, axis_y=axis_y)
                        for s in slopes_Cm])



def solve_intersections(data, n_chars, z, *, lip, thetas, nu_e, gamma, Me):
    for i in range(0, n_chars):
        for j in range(i, n_chars):
            if (z, i, j) in data:
                continue

            A = get_A(data, z, i, j)
            B = get_B(data, z, i, j, lip, thetas, nu_e, gamma, Me)

            Pp = compute_node_from_AB(A, B, gamma=gamma, M_guess=Me, z=z, i=i, j=j)

            data[(z, i, j)] = Pp

    #Apply the shock detection after the full fan is computed
    if z%2 == 0:
        shock_point = detect_shock_in_fan(data, z, n_chars)
    else:
        shock_point = detect_shock_Cminus(data, z, n_chars)

    return data, shock_point

if __name__ == "__main__":
    z = 0
    shock_detected = False
    shock_point = None
    z_max = 10

    while (not shock_detected) and (z < z_max):
        z_curr = z
        data, shock_point = solve_intersections(
            data, n_chars, z_curr,
            lip=lip, thetas=thetas, nu_e=nu_e, gamma=gamma, Me=Me
        )
        print(z_curr)

        if shock_point is not None:
            print(f"Shock detected in fan z={z_curr} at x={shock_point[0]:.4f}, y={shock_point[1]:.4f}")
            shock_detected = True
            break

        z += 1

    if not shock_detected:
        raise RuntimeError("Shock not detected")

    #plot_characteristics_multi_fan(data, n_chars, lip, R_exit)
    plot_flow_field(data, gamma, R_exit)


# ---------------------------
# Notes / Next steps:
# 1) Enforce the free boundary (p=pa) by creating a boundary node where a C− hits the boundary
#    and setting that node's state to Mb (so ν=ν_b, θ=θ_b local tangent), then march with that.
# 2) After introducing boundary nodes, K+ ≠ K− at interior intersections => nontrivial (ν,θ).
# 3) Add shock detection: neighboring same-family slope intersections (or dθ/ds→compression).
# ---------------------------
