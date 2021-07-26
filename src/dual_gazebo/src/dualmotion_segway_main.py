from utils.eom import *
from sympy import symbols, factor
from sympy import simplify
from sympy.physics.mechanics import *
from sympy import sin, cos, symbols, Matrix, solve
from sympy.physics.vector import init_vprinting
import pylab as pl
import control
import numpy as np
from scipy.integrate import odeint

from matplotlib import pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation
from IPython.display import HTML

import pickle

with open("src/dual_gazebo/src/save_parameter/sys0.txt",'rb') as inf:
    sys0 = pickle.load(inf)


import time


t1 = time.time()

# Define Symbolic Variables
x,x_l,theta = dynamicsymbols('x,x_l,theta')
phi = dynamicsymbols('phi')
F,F_l = dynamicsymbols('F,F_l')
r,h_c,h_t = symbols('r,h_c,h_t')
I_w,I_c,I_t = symbols('I_w,I_c,I_t')
m_w, m_c, m_t, g, t = symbols('m_w, m_c, m_t, g, t')

# Newtonian Reference Frames
N = ReferenceFrame('N')
No = Point('No') 
No.set_vel(N, 0)

# Wheel Center Point
Wo = No.locatenew('Wo', x*N.x + r*N.z)
Wo.set_vel(N, Wo.pos_from(No).diff(t, N))

# Pendulum 
P = N.orientnew('P', 'Axis', [theta, N.y])
Po = Wo.locatenew('Po', h_c*P.z)
Po.set_vel(P, 0)
J_pend = inertia(P, 0, I_c, 0)
Pend = RigidBody('Pend', Po, P, m_c, (J_pend, Po))

# Torso
T = P.orientnew('T', 'Axis', [0, P.y])
To = Wo.locatenew('To', x_l*P.x + h_t*P.z)
To.set_vel(T, 0)
J_torso = inertia(T, 0, I_t, 0)
Torso = RigidBody('Torso', To, T, m_t, (J_torso, To))

# Wheel 
W = P.orientnew('W', 'Axis', [phi, P.y])
Wo.set_vel(W, 0)
J_wheel = inertia(W, 0, I_w, 0)
Wheel = RigidBody('Wheel', Wo, W, m_w, (J_wheel, Wo))

Wn = Wo.locatenew('Wn', -r*N.z)
Wn.v2pt_theory(Wo, N, W)

constraints = Wn.vel(N).express(N).args[0][0]


con = solve(constraints, [phi.diff()])
con_rhs = Matrix(list(con.values()))
con_lhs = Matrix(list(con.keys()))

# Generalized coordinates
q = Matrix([[x], [x_l], [theta]])
qd = q.diff()
qdd = qd.diff()

flist = [(Wo, -m_w*g*N.z), 
         (Po, -m_c*g*N.z), 
         (To, -m_t*g*N.z), 
         (Wo, F*N.x), 
         (To, F_l*T.x),
         (P, -F_l*h_t*P.y)] 

Lag = Lagrangian(N, Pend, Torso, Wheel)
nonslip_condition = {con_lhs[0]:con_rhs[0]}
Lag_constrainted = msubs(Lag, nonslip_condition)
Le = LagrangesMethod(Lag_constrainted, q, forcelist=flist, frame=N)
eoms = Le.form_lagranges_equations()

eoms_simple = simplify(eoms) ## save point

inv_dyn = get_Simplified_EoM(eoms_simple, q)

linearlize_eq = {sin(theta):theta, cos(theta):1, theta.diff():0, x_l:0}
inv_dyn_linear = msubs(inv_dyn, linearlize_eq)


# Control Input Variable
u = Matrix([[F], [F_l]])

# Inverse Dynamics Equation
# M(q)*qdd + C(q,qd) + G(q) = W*u
M, C, G, W = get_EoM_from_T(inv_dyn,qdd,g,u)

Ml, Cl, Gl, Wl = get_EoM_from_T(inv_dyn_linear,qdd,g,u)  ## save point

# Physical Parameters
#param = {r:0.25, h_c:0.25, h_t:0.25, m_w:30, m_c:370, m_t:300, g:9.8}
param = {r:0.25, h_c:0.25, h_t:0.5, m_w:60, m_c:340, m_t:300, g:9.8}

param['c_width'] = 0.7 #0.5
param['c_height'] = 0.2 #0.25

# torso size
param['t_width'] = 2.5
param['t_height'] = 0.5

# Moment of Inertia
param[I_w] = 1/2*param[m_w]*param[r]**2
param[I_c] = 1/12*param[m_c]*(param['c_width']**2 + param['c_height']**2)
param[I_t] = 1/12*param[m_t]*(param['t_width']**2 + param['t_height']**2)

Mlp = msubs(Ml, param)
Clp = msubs(Cl, param)
Glp = msubs(Gl, param)
Wlp = msubs(Wl, param)

Mlp_inv = simplify(Mlp.inv())
qdd_rhs_A = simplify(Mlp_inv*(-Clp -Glp))
qdd_rhs_B = simplify(Mlp_inv*Wlp*u)

Mp = msubs(M, param)
Cp = msubs(C, param)
Gp = msubs(G, param)
Wp = msubs(W, param)

Mp_inv = (Mp.inv())
qdd_rhs_A_nonL = (Mp_inv*(-Cp -Gp))
qdd_rhs_B_nonL = (Mp_inv*Wp*u)


sys0_output = sys0[3,0]
tf_20 = tf_clean(control.minreal(control.ss2tf(sys0_output)))


#Q = pl.eye(sys0.A.shape[0])
#R = pl.eye(sys0.B.shape[1])*0.00001

# state : [x, x_l, theta, xdot, x_ldot, thetadot]
Q = Matrix([ [1,0,0,0,0,0],
             [0,5,0,0,0,0],
             [0,0,1,0,0,0],
             [0,0,0,1,0,0],
             [0,0,0,0,1,0],
             [0,0,0,0,0,1] ])
R = Matrix([ [0.0000001,0],
             [0,0.00001] ])


K, S, E = control.lqr(sys0.A, sys0.B, Q, R)
sysc = sys0.feedback(K)


x0 = [0, 0, 0.1, 0, 0, 0]
u = 0
dt = 0.01
tf = 10

t, y = control.forced_response(sysc, X0=x0, T=pl.linspace(0,tf), transpose=True)

vmax_ = 22/3.6
t_ = 20# sec

target_pos = vmax_*t_
v = vmax_/target_pos
a = v/4

t_s, traj_s = Trapezoidal_Traj_Gen_Given_Amax_and_T(a,t_,0.01)

x_des = traj_s[:,0]*target_pos
xdot_des = traj_s[:,1]*target_pos
xl_des = traj_s[:,2]*target_pos/4 # using acceleration as xl_des
zeros = np.zeros(len(traj_s))
Xdes = x_des
Xdes = np.vstack((Xdes, xl_des))
#Xdes = np.vstack((Xdes, zeros))
Xdes = np.vstack((Xdes, zeros)) 
Xdes = np.vstack((Xdes, xdot_des))
Xdes = np.vstack((Xdes, zeros))
Xdes = np.vstack((Xdes, zeros))


ss = sys0

rad2deg = 180/np.pi

def simulate_model_closed(X0, Xdes, K_gain, time_array, dt):
    Aop = ss.A
    Bop = ss.B
        
    t = 0
    j = 0
    X = Xref = Xd_prev = Xd = X0
    
    t_save = [0]
    x_save = xref_save = np.array([0,0,0,0,0,0])
    u_save = np.array([0,0])
    
    for i in range(len(time_array)):
        t = time_array[i]
         
        if t<2:
            Xref = X0       
        elif t>=2 and j<(Xdes.shape[1]):
            Xref = Xdes[:,j]
            j+=1
        else:
            Xdes_final = Xdes[:,Xdes.shape[1]-1]
            Xdes_final[1] = 0 # force to set xl_des as 0
            Xref = Xdes_final

        # full-state feedback
        #u = K@(Xgoal - X)

        # partial feedback
        u1 = K_gain[0][1:]@(Xref[1:] - X[1:])
        u2 = K_gain[1][1:]@(Xref[1:] - X[1:])
        
        # Forward Dynamics
        Xd_prev = Xd
        # Linear Model
        #u = [u1, u2]
        #Xd = Aop@X + Bop@u # Xd = [xd, x_ld, thetad, xdd, x_ldd, thetadd]
        # NonLinear Model
        q_qd = {x:X[0], x_l:X[1], theta:X[2], x.diff():X[3], x_l.diff():X[4], theta.diff():X[5]}
        q_qd[F] = u1
        q_qd[F_l] = u2
        qdd = msubs(qdd_rhs_A_nonL,q_qd) + msubs(qdd_rhs_B_nonL,q_qd)
        Xd = np.array([X[3], X[4], X[5], float(qdd[0]), float(qdd[1]), float(qdd[2])])
        
        t_save = np.vstack((t_save, t))
        x_save = np.vstack((x_save, X))
        xref_save = np.vstack((xref_save, Xref))
        u_save = np.vstack((u_save, np.array([u1,u2])))
        
        X = X + Xd*dt
        t = t + dt
        i+=1
        
        #limit setting
        xl_limit = 0.5
        if X[1] >= xl_limit:
            X[1] = xl_limit
        elif X[1] <= -xl_limit:
            X[1] = -xl_limit
                 
    return t_save, x_save, xref_save, u_save

# initial condition
# [x, x_l, theta, x_dot,x_l_dot, theta_dot]
X0 = np.array([0,0,0,0,0,0])

tf = 20 + 7
dt = 0.01
N = int(tf/dt)

# time points
t = np.linspace(0,tf,N)

# simulation
t_sim, x_sim, xref_sim, u_sim = simulate_model_closed(X0, Xdes, K, t, dt)

print(time.time() - t1)