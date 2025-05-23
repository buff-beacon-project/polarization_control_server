
#!/usr/bin/env python
# coding: utf-8
import numpy as np
import os
import pickle
import hashlib
from functools import wraps
from scipy import optimize
from numba import jit
import inspect

def file_cache(func, cache_dir='cache'):
    os.makedirs(cache_dir, exist_ok=True)

    sig = inspect.signature(func)
    valid_args = set(sig.parameters)

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Explicitly remove control keywords BEFORE key computation and function call
        use_cache = kwargs.pop('use_cache', True)
        update_cache = kwargs.pop('update_cache', False)

        # These kwargs are only those accepted by the wrapped function
        actual_kwargs = {k: v for k, v in kwargs.items() if k in valid_args}

        # Generate unique hash from function arguments
        key_data = pickle.dumps((args, actual_kwargs))
        key_hash = hashlib.md5(key_data).hexdigest()
        cache_path = os.path.join(cache_dir, f'{func.__name__}_{key_hash}.pkl')

        if use_cache and os.path.exists(cache_path):
            with open(cache_path, 'rb') as f:
                print(f"[cache] Loaded from {cache_path}")
                return pickle.load(f)

        # Compute and possibly cache
        result = func(*args, **actual_kwargs)

        if (not use_cache and update_cache) or (use_cache and not os.path.exists(cache_path)):
            with open(cache_path, 'wb') as f:
                pickle.dump(result, f)
                print(f"[cache] Saved to {cache_path}")

        return result

    return wrapper


toRad = np.pi/180.
pauli_x = np.array([[0, 1 + 0j], [1, 0]])
pauli_z = np.array([[1 + 0j, 0], [0, -1]])
pauli_y = np.array([[0, -1j], [1j, 0]])


'''Change these if and when you characterize the Pockels cells again.
These constants contain all the information we're using to model the
Pockels cells'''

jones_avg_bob_static = np.array([[1.+0.j, -0.02198908-0.01899806j],
                                 [0.00383058-0.01926662j,  0.99169901+0.02682298j]])
jones_avg_alice_static = np.array([[1. + 0.j,  0.02121528-0.03043852j],
                                   [-0.01101801-0.04069562j,  1.00694941+0.01825613j]])



quarter_wave_bob = 622.12
quarter_wave_alice = 596.82
pc_rot_alice = -toRad*45.66
pc_rot_bob = -toRad*45.64

opt_tol_a = opt_tol_b = 5e-8
'''__________________________end constants___________________'''''


'''___Standard functions___'''


def rhoify(state): return np.outer(np.array(state), np.array(state).conj().T)


def rot(theta):
    r = np.array([[np.cos(theta), np.sin(theta)],
                  [-np.sin(theta), np.cos(theta)]])
    return(r)


# Matrix for an imperfect quarter-waveplate at a given angle
def qwp(theta, imperf=0.):
    h = np.array([[1, 0], [0, -1j]]) * np.exp(-1j*np.pi/4*(1 + imperf))
    jones = rot(-1*theta).dot(h.dot(rot(theta)))
    tol = 1e-13
    jones.real[abs(jones.real) < tol] = 0.
    jones.imag[abs(jones.imag) < tol] = 0.
    return(jones)


# Matrix for an imperfect half-waveplate at a given angle
def hwp(theta, imperf=0.):
    h = np.array([[1, 0], [0, -1]]) * np.exp(-1j*np.pi/2*(1 + imperf))
    jones = rot(-1*theta).dot(h.dot(rot(theta)))
    tol = 1e-13
    jones.real[abs(jones.real) < tol] = 0.
    jones.imag[abs(jones.imag) < tol] = 0.
    return(jones)


'''_________end standard functions_________'''
def what_angles(parameters, pc_static_jones,
                theor_angles, pc_rot, off_state_only=False):
    # WARNING: This does not work for circular polarizations!
    # There are some assumptions that optimize this for the bell-ch 
    # inequality, which only measures in linear polarizations.
    hwp_1 = parameters[0]*toRad
    qwp_1 = parameters[1]*toRad
    hwp_2 = parameters[2]*toRad
    
    for param in parameters:
        if np.abs(param) > 90.:
            # print("Angle out of bounds")
            return 1e10
            
    if off_state_only is False:
        volt = parameters[3]
    Vpol = np.outer([0, 1], [0, 1])
    Hpol = np.outer([1, 0], [1, 0])
    def orth(x): return np.array([x[1], -1*x[0]])  # orthogonal of a 2d vector

    # a HWP preceeding a V polarizer
    #print(off_state_only, theor_angles)
    #sys.stop()
    
    if off_state_only is True:
    # hwp->qwp->PC->hwp->Hpol
        a_1 =  ([0, 1] @ hwp(hwp_2) @ pc_static_jones @ 
                qwp(qwp_1) @ hwp(hwp_1) @ hwp(theor_angles[0]*toRad) @ [1, 0])
    else:
        theor_a = hwp(theor_angles[0]*toRad) @ [0, 1]
        theor_a_orth = orth(theor_a)
        a_1 = hwp(hwp_1) @ qwp(qwp_1) @ pc_static_jones @ hwp(hwp_2) @ [0, 1]

    if off_state_only is False:
        theor_b = hwp(theor_angles[1]*toRad)@[0, 1]
        theor_b_orth = orth(theor_b)

        b_1 = (hwp(hwp_1) @ qwp(qwp_1) @ rot(pc_rot) @ [[1, 0], [0, np.exp(-1j*np.pi/2 * volt)]] 
               @ rot(-pc_rot) @  hwp(hwp_2) @ [0, 1])  # hwp->qwp->PC->hwp->Vpol

    if off_state_only is False:
        # in this case, you want to maximize overlap with theor_a
        # this is because the bridge should act like hwp(ang) @ [0,1]
        return (np.abs(np.dot(theor_a_orth, a_1)) +
                np.abs(np.dot(theor_b_orth, b_1)))
    else:
        # in this case, you want to maximize overlap with theor_a_orth
        # this is because you're going in the opposite direction in constructing a_1
        # should act orthogonal to hwp(ang) @ [0,1]
        return (np.abs( a_1))*5e-1

@file_cache
def set_bridge_to_hwp(hwp_ang, alice=True, off_state_only=False):
    '''given a hwp angle 'x', computes the angles for the
    the bridge to mimic a hwp at angle 'x' preceeding
    a V polarizer.'''
    optimized = False

    if alice:
        while not optimized:
            if off_state_only is False:
                guess = np.array([1.0, 0.0, 0.0, 0.1]) +\
                    np.hstack([10*np.random.random(3), [0]])
            else:
                guess = np.array([1.0, 0.0, 0.0]) + 10*np.random.random(3)
            res =\
                optimize.minimize(what_angles, guess,
                                  args=(jones_avg_alice_static, [hwp_ang, 0],
                                        pc_rot_alice, off_state_only))
            #print(res.fun)
            if res.fun < opt_tol_a * 1e-1:
                optimized = True
    else:
        while not optimized:
            if off_state_only is False:
                guess = np.array([1.0, 0.0, 0.0, 0.1]) +\
                    np.hstack([10*np.random.random(3), [0]])
            else:
                guess = np.array([1.0, 0.0, 0.0]) + 10*np.random.random(3)
            res =\
                optimize.minimize(what_angles, guess,
                                  args=(jones_avg_bob_static, [hwp_ang, 0],
                                        pc_rot_bob, off_state_only))
            if res.fun < opt_tol_b * 1e-1:
                optimized = True

    return res.x[:3]

@file_cache
def angles_bell_test(hwp_angs):

    hwp_angs_alice = hwp_angs  # [-2.73387745,14.00312409]
    hwp_angs_bob = [-i for i in hwp_angs_alice]  # [2.73387745,-14.00312409]

    optimized_a = False
    optimized_b = False
    redo_a = False
    redo_b = False
    while not optimized_a:
        guess_a = np.array([1.0, 0.0, 0.0, 0.1]) +\
            np.hstack([10*np.random.random(3), [0]])
        res_a = \
            optimize.minimize(what_angles, guess_a,
                              args=(jones_avg_alice_static, hwp_angs_alice,
                                    pc_rot_alice))
        if res_a.x[3] < 0:  # negative pockels voltage or more than 1/2
            guess_a[1] += 90  # flip qwp 90 degrees to get a positive voltage
            redo_a = True
        elif res_a.x[3] > 2:
            redo_a = True
            guess_a[2] -= 45  # try to flip a hwp to try and get a lower voltage
            guess_a[1] += 90
        if redo_a:
            redo_a = False
            res_a = \
                optimize.minimize(what_angles, guess_a,
                                  args=(jones_avg_alice_static, hwp_angs_alice,
                                        pc_rot_alice))
            if res_a.x[3] < 0 or  res_a.x[3] > 2:
                res_a.fun += 2*opt_tol_a 
           
        if res_a.fun < opt_tol_a:
            optimized_a = True

    print("Set the Alice PC driver to: ", res_a.x[3]*quarter_wave_alice,
          " turns")

    while not optimized_b:
        guess_b = np.array([1.0, 0.0, 0.0, 0.1]) +\
            np.hstack([10*np.random.random(3), [0]])

        res_b = \
            optimize.minimize(what_angles, guess_b,
                              args=(jones_avg_bob_static, hwp_angs_bob,
                                    pc_rot_bob))
        if res_b.x[3] < 0:  # negative pockels voltage
            # flip qwp 90 degrees to get a positive voltage
            guess_b[1] += 90
            redo_b = True
        elif res_b.x[3] > 2:
            guess_b[2] -= 45  # flip a hwp to try and get a lower voltage
            guess_b[1] += 90
            redo_b = True
        if redo_b:
            redo_b = False
            res_b = \
                optimize.minimize(what_angles, guess_b,
                                  args=(jones_avg_bob_static, hwp_angs_bob,
                                        pc_rot_bob))
            if res_b.x[3] < 0 or  res_b.x[3] > 2:
                res_b.fun += 2*opt_tol_b

        if res_b.fun < opt_tol_b:
            optimized_b = True

    print("Set the Bob PC driver to:  ", res_b.x[3]*quarter_wave_bob,
          " turns")
    print(res_a.fun, res_b.fun)

    return (res_a.x[:3], res_b.x[:3])
