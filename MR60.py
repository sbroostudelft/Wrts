import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# --- Constants (toy values, just for a plausible shape) ---
p_tank = 40e5          # tank pressure [Pa]  (40 bar)
V_c    = 0.01          # chamber volume [m^3]
A_max  = 1.0e-4        # max injector area [m^2]
A_t    = 5.0e-5        # nozzle throat area [m^2]
Cd     = 0.8           # injector discharge coefficient [-]
rho_l  = 1200.0        # "liquid" density [kg/m^3] (rough number)
T_c    = 3000.0        # gas temperature in chamber [K]
gamma  = 1.2           # specific heat ratio [-]
R_gas  = 350.0         # gas constant [J/(kg·K)]
t_open = 0.05          # valve opening time [s]

# --- Helper: valve opening law (linear ramp) ---
def A_inj(t):
    if t <= 0.0:
        return 0.0
    elif t < t_open:
        return A_max * (t / t_open)
    else:
        return A_max

# --- Mass flow relations ---
def m_dot_inj(t, p_c):
    """Injector mass flow [kg/s] through orifice."""
    dp = max(p_tank - p_c, 0.0)
    return Cd * A_inj(t) * np.sqrt(2.0 * dp / rho_l)

def m_dot_noz(p_c):
    """Choked nozzle mass flow [kg/s] at throat."""
    if p_c <= 0:
        return 0.0
    factor = np.sqrt(gamma / (R_gas * T_c))
    choked = (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
    return A_t * p_c * factor * choked

# --- ODE: dp_c/dt = (R*T/V) * (m_inj - m_noz) ---
def chamber_ode(t, y):
    p_c = y[0]  # chamber pressure [Pa]
    mdot_in  = m_dot_inj(t, p_c)
    mdot_out = m_dot_noz(p_c)
    dpdt = (R_gas * T_c / V_c) * (mdot_in - mdot_out)
    return [dpdt]

# --- Integrate ---
t_span = (0.0, 0.2)       # simulate 0–0.2 s
t_eval = np.linspace(*t_span, 400)
p0 = [1.0e5]              # initial chamber pressure 1 bar [Pa]

sol = solve_ivp(chamber_ode, t_span, p0, t_eval=t_eval, rtol=1e-6, atol=1e-8)

# --- Plot ---
t = sol.t
p_bar = sol.y[0] / 1e5    # convert Pa -> bar

plt.figure()
plt.plot(t, p_bar)
plt.xlabel("Time [s]")
plt.ylabel("Chamber pressure [bar]")
plt.title("Toy startup transient: injector–chamber–nozzle model")
plt.tight_layout()
plt.show()
