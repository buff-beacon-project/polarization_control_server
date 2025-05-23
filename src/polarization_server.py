import beacon_bridge_optimizations as bc_opt
from scipy.optimize import minimize
import time
from bellMotors import MotorController
import numpy as np
import threading
import os
import yaml as yaml
import logging
from zmqhelper import Server
import json
from datetime import datetime, date

motorInfo = {}
logger = None
# set_ch_waveplates([41.6383456, 59.62867712, 45-22.49767973/2])

def get_current_date_string():
    # Get the current date
    current_date = date.today()
    # Format the date as a string in the format YYYY-MM-DD
    date_string = current_date.strftime('%Y-%m-%d')
    return date_string

def ensure_directory_exists(file_path):
    # Extract the directory path from the file path
    directory = os.path.dirname(file_path)
    
    # Check if the directory exists
    if not os.path.exists(directory):
        # Create the directory if it doesn't exist
        os.makedirs(directory)
        
def setup_logger():
    # Set up the logger
    logger = logging.getLogger('PolarizationServer')
    logger.setLevel(logging.DEBUG)
    
    # Create a file handler
    curr_date = get_current_date_string()
    f_name = 'logs/'+curr_date+'_'+'_polarization_logger.log'
    ensure_directory_exists(f_name)
    fh = logging.FileHandler(f_name)
    fh.setLevel(logging.DEBUG)
    
    # Create a console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    
    # Create a formatter and set it for the handlers
    formatter = logging.Formatter('%(asctime)s: %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    # Add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

class PolarizationServer(Server):
    '''
    Bit authentication server for a verifier. The verifier waits for a start signal from a prover and then executes the authentication protocol using only the local computer time.
    '''
    def __init__(self, config, configFName, port, n_workers=1):
        global logger
        self.config = config
        self.configFName = configFName
        self.time_start = datetime.now()
        self.logger = logger
        self.logger.info("")
        self.logger.info(f'Polarization server Started at {self.time_start}')
        self.logger.info(f"Config: {config}")
        self.get_positions()
        # Call the constructor of the parent class
        super().__init__(port, n_workers=n_workers)
        
    def get_positions(self):
        for party in motorInfo:
            ip = motorInfo[party]['ip']
            port = motorInfo[party]['port']
            mc = MotorController(ip, port)
            angles = mc.getAllPos()
            self.logger.info("Motor positions for %s: %s", party, angles)
        return angles
        
    def handle(self, message):
        '''
        Process the message received from the client.
        '''
        received_time = datetime.now()  # Use datetime.now() correctly
        res = {}
        resp = {}
        self.config = load_config_from_file(self.configFName)
        print("Received message: ", str(message))
        # try:
        inputs = json.loads(message)
        cmd = inputs['cmd']
        params = inputs['params']
        cmd = cmd.lower()
        print("Command received: ", str(cmd), str(params))
        self.logger.info("Command received: %s", str(cmd))
        
        if cmd == 'set_polarization':
            setting = str(params['setting']).lower()
            # resp = set_polarization(setting, self.config)
            resp = set_polarization(self.config, **params)
            
        elif cmd == 'calibrate':
            party = params['party'].lower()
            resp = optimize_wvplts(party, self.config)
            if party == 'source':
                new_source_HWP_zero = 360. - resp['source']['source_HWP_1']
                self.config['source_power_angle'] = new_source_HWP_zero
                self.logger.info("Setting new source power angle: %s", str(new_source_HWP_zero))
                write_config_to_file(self.config, self.configFName)
                
        elif cmd == 'set_pc_to_bell_angles':
            if 'angles' not in params:
                angles = self.config['bell_angles']
                params['angles'] = angles
            self.logger.info("Setting PC angles: %s", str(params['angles']))
            resp = set_ch_waveplates(self.config, **params)
            
        elif cmd == 'set_power':
            power = float(params['power'])
            if power < 0. or power > 1.:
                res['error'] = "Power must be between 0 and 1"
                self.logger.error("Power must be between 0 and 1")
            else:
                source_pow = float(self.config['source']['source_power_angle'])
                resp = set_power(power, source_pow)
                logger.info("Setting power to: %s", str(power))
            
        elif cmd == 'home':
            party = params['party'].lower()
            if party == 'alice':
                home(ip=motorInfo['alice']['ip'], port=motorInfo['alice']['port'])
                self.logger.info("Homing Alice motor")
            elif party == 'bob':
                home(ip=motorInfo['bob']['ip'], port=motorInfo['bob']['port'])
                self.logger.info("Homing Bob motor")
            elif party == 'source':
                home(ip=motorInfo['source']['ip'], port=motorInfo['source']['port'])
                self.logger.info("Homing Source motor")
            elif party == 'all':
                homeAll()
                self.logger.info("Homing all motors")
            else:
                res['error'] = "Invalid Party"
        
        elif cmd == 'get_positions':
            resp = self.get_positions()
            
        elif cmd == 'test':
            resp = "Test successful"
            self.logger.info("Test successful") 

        elif cmd == 'info':
            resp = {}
            resp['status'] = "Polarization server is running"
            resp['commands'] = ['set_polarization setting', 'calibrate alice/bob/source', 'set_pc_to_bell_angles angles_array', 'set_power 0..1', 'home alice/bob/source/all', 'get_positions', 'test', 'info']
            resp['description'] = "List of commands available"
            resp['settings'] = self.config['settings']
            resp['uptime'] = str(datetime.now() - self.time_start)
            
        else:
            res['error'] = "Invalid Command"

        # Catch errors and return them
        # except Exception as e:
            # print("Error: %r" % e)
            # self.logger.error("Error: %r", e)
            # res ={}
            # res['error'] = "Error: "+str(e)
            # self.logger.error("Error: %r", e)
        res['message'] = resp
        print("\n Sending message", res)
        # msgout = json.dumps(res)
        # msgout = msgout.encode('utf-8')
        return self.encode_message(res)
    
    def encode_message(self, message):
        # Convert any numpy arrays in the message to lists for JSON serialization
        def convert(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert(i) for i in obj]
            return obj

        msgout = json.dumps(convert(message))
        msgout = msgout.encode('utf-8')
        return msgout 

def connect_to_motor(ip:str, port:int):
    mc = MotorController(ip, port)
    return mc

def home(ip:str, port:int):
    mc =connect_to_motor(ip, port)
    for motor in mc.id_dict:    
        mc.home(motor)
        print(f"Homing {motor}")
    return

def homeAll():
    global motorInfo
    for party in motorInfo:
        home(motorInfo[party]['ip'], motorInfo[party]['port'])

def set_power(power, source_pow=0):
    '''Set the power of the source. The power is set by rotating the HWP
    '''
    global logger
    global motorInfo
    power = float(power)
    if power >1. or power<0.:
        return('Improper setting. Must be between 0..1.')
    theta = np.arcsin(power**.5) *180./np.pi /2.
    mc_source = connect_to_motor(motorInfo['source']['ip'], motorInfo['source']['port'])
    mc_source.goto('source_Power_1', theta +source_pow)
    print('Setting power to: ', theta)
    return(theta)

def set_polarization(config, setting='1', use_cache = True, update_cache = False):
    global logger
    setting = str(setting).lower()
    if setting in config['settings']:
        PHWP = config['settings'][setting]['PHWP']
        AHWP1 = config['settings'][setting]['AHWP1']
        BHWP1 = config['settings'][setting]['BHWP1']
    else:
        print('Invalid path setting.')
        logger.info('Invalid path setting.')

    aAlice = {}
    a_angs = bc_opt.set_bridge_to_hwp(AHWP1, alice=True, off_state_only=True, use_cache=use_cache, update_cache=update_cache)
    print("Alice bridge angles are: ", 
          a_angs, " (hwp1, qwp1, hwp2)")
    logger.info("Alice bridge angles are: %s", str(a_angs))
    aAlice['alice_HWP_1'] = a_angs[0]
    aAlice['alice_QWP_1'] = a_angs[1]
    aAlice['alice_HWP_2'] = a_angs[2]

    aBob = {}
    b_angs = bc_opt.set_bridge_to_hwp(BHWP1, alice=False, off_state_only=True, use_cache=use_cache, update_cache=update_cache)
    print("Bob bridge angles are: ", 
          b_angs, " (hwp1, qwp1, hwp2)")
    logger.info("Bob bridge angles are: %s", str(b_angs))
    aBob['bob_QWP_1'] =  b_angs[1]
    aBob['bob_HWP_1'] =  b_angs[0]
    aBob['bob_HWP_2'] =  b_angs[2]

    aSource = {'source_HWP_1':  PHWP}

    ang = {'alice': aAlice, 'bob': aBob, 'source': aSource}
    setBridgeWPs(ang, config)
    return ang

def set_ch_waveplates(config, angles = None, use_cache = True, update_cache = False):
    '''given an array of 2 hwp settings and 1 pump waveplate setting,
    set the appropriate waveplates for a CH violation. Pockels cell
    characterization is hard coded into the bc_opt file'''
    # global aH1, aH2, aQ1, aQ2
    # global bH1, bH2, bQ1, bQ2
    # PumpOffset = pOffset + po
    arr = angles
    PHWP = arr[2]
    print("Starting optimization with angles: ", arr)
    angs_a, angs_b = bc_opt.angles_bell_test( [arr[0], arr[1]], use_cache=use_cache, update_cache=update_cache)
    print(f"Finished ch optimization. Alice angles: {angs_a}, Bob angles: {angs_b}")
    aAlice = {}
    aAlice['alice_HWP_1'] = angs_a[0] 
    aAlice['alice_QWP_1'] = angs_a[1] 
    aAlice['alice_HWP_2'] =  angs_a[2] 

    aBob = {}
    aBob['bob_QWP_1'] =  angs_b[1] 
    aBob['bob_HWP_1'] = angs_b[0] 
    aBob['bob_HWP_2'] =  angs_b[2] 

    aSource = {'source_HWP_1':  PHWP}

    ang = {'alice': aAlice, 'bob': aBob, 'source': aSource}
    # print(ang)
    setBridgeWPs(ang, config=config)
    return ang

def setBridgeWPs(params, config):
    global motorInfo
    t = []
    mc = []
    
    for party in params.keys():
        ip = motorInfo[party]['ip']
        port = motorInfo[party]['port']
        mc.append(MotorController(ip, port))
        try:
            angles = params[party]
            for wp in angles:
                ang = angles[wp]
                mc.append(MotorController(ip, port=port))
                t.append(threading.Thread(target=mc[-1].goto, args=(wp, ang,)))
                t[-1].start()
        except Exception as e:
            print(f'No {party} angles to set', e )
            pass
    for th in t:
        th.join()


def get_power(intTime, COUNTTYPE = 'effAB', windowtype='no_PC'):
    time.sleep(.2 + intTime)
    COUNTTYPE= COUNTTYPE.lower()
    windowtype = windowtype.lower()
    if windowtype == 'no_pc':    
        counts = r_read.get_power(intTime)['VV']
    else:
        counts = r_read.get_power(intTime)['VV_PC']
    #print(counts)
    if COUNTTYPE == 'sa':
        val = counts['As']
    elif COUNTTYPE == 'sb':
        val = counts['Bs']
    elif COUNTTYPE == 'coinc':
        val = counts['C']
    elif COUNTTYPE == 'effa':
        val = counts['effA']
    elif COUNTTYPE == 'effb':
        val = counts['effB']
    elif COUNTTYPE == 'all':
        val = counts
    elif COUNTTYPE == 'sum':
        val = counts[0] + counts[2] + counts[1]
    else:
        val = counts['effAB']

    return val

def waveplate_optimization_function(pos, params, int_time=1):
    mc_obj = params['mc_obj']
    waveplates = params['waveplate']
    count_type = params['count_type']
    scale = params['scale']
    start_pos = params['start_pos']
    best_counts = params['best_counts']
    window_type = params['window_type']
    
    pos = pos * scale + start_pos


    for i, waveplate in enumerate(waveplates):
        mc_obj.goto(waveplate, pos[i])
    #move_all_to_position(pos.tolist())
    time.sleep(.5)
    counts = get_power(int_time, count_type, window_type)
    #print(counts)
    #counts = counts[countIndxToOptimize]
    if (counts < best_counts):
        best_pos = []
        for waveplate in waveplates:   
            best_pos.append(float(mc_obj.getPos(waveplate)))
        params['best_pos'] = np.array(best_pos)
        params['best_counts'] = counts
    print((counts, params['best_counts']))
    return counts
#

def optimize_wvplt_scipy(arm='Bob', count_type = 'Coinc' ,
                       wvplt = '', int_time=1,
                       window_type= 'no_PC', custom=False, method = 'NM'):
    '''
    If you need to pass a custom list of waveplates, set custom = true and pass 
    an array of waveplate names to the wvplt kwarg. 
    '''
    global motorInfo
    global logger
    arm = arm.lower()
    if arm == 'bob':
        mc_obj = connect_to_motor(motorInfo['bob']['ip'], motorInfo['bob']['port'])
    elif arm == 'alice':
        mc_obj = connect_to_motor(motorInfo['alice']['ip'], motorInfo['alice']['port'])
    elif arm == 'source':
        mc_obj = connect_to_motor(motorInfo['source']['ip'], motorInfo['source']['port'])
    if custom:
        waveplates = wvplt
    else:
        mc_obj = connect_to_motor(motorInfo['source']['ip'], motorInfo['source']['port'])
        waveplates = list(mc_obj.id_dict.keys())
        if 's' not in wvplt:
            waveplates = [i for i in waveplates if not 'source' in i]
        else:
            waveplates = [i for i in waveplates if 'source' in i]
        if 'a' in wvplt:
            waveplates = [i for i in waveplates if 'alice' in i]
        if 'b' in wvplt:
            waveplates = [i for i in waveplates if 'bob' in i]
        if 'h' in wvplt:
            waveplates = [i for i in waveplates if 'HWP' in i]
        if 'q' in wvplt:
            waveplates = [i for i in waveplates if 'QWP' in i]
        if '1' in wvplt:
             waveplates = [i for i in waveplates if '1' in i]
        if '2' in wvplt:
            waveplates = [i for i in waveplates if '2' in i]
        if 'p' in wvplt:
            waveplates = [i for i in waveplates if 'Power' in i]
            
    print("\n The list of waveplates to be optimized is: ", waveplates)
    best_counts = np.inf
    start_pos = []
    for waveplate in waveplates:
        print(waveplate)
        start_pos.append(float(mc_obj.getPos(waveplate)))
        
    scale = 1 # Amount to scale the step size by

    niter = 25
    params = {'count_type': count_type, 
              'scale': scale,
              'start_pos' : start_pos,
              'best_counts' : best_counts,
              'best_pos' : start_pos,
              'mc_obj' : mc_obj,
              'waveplate' : waveplates,
              'int_time' : int_time,
              'window_type' : window_type}
    options = {'xtol': 0.2, 'maxiter': niter}
    x0 = np.zeros_like(start_pos)

    res = minimize(waveplate_optimization_function, x0, params, 
                    method = 'Powell', options = options)

    #move_all_to_position(BESTPOS)
    print('')
    print(("Finished  optimization", params['best_pos'], params['best_counts']))
    logger.info("Finished  optimization %s %s %s %s", arm, wvplt, str(params['best_pos']), str(params['best_counts']))
    print('')


    for i,waveplate in enumerate(waveplates):
        mc_obj.goto(waveplate, params['best_pos'][i])
    print(mc_obj.getAllPos(), params['best_counts'])
    return params['best_pos'], params['best_counts']
    

def optimize_wvplts(party, config):
    party = party.lower()
    twait = 3.
    if party == 'alice':
        set_polarization('a_calib', config)
        time.sleep(twait)
        pos, counts = optimize_wvplt_scipy('Source', 'Coinc', 'a', 2.)
    if party == 'bob':
        set_polarization('b_calib', config)
        time.sleep(twait)
        pos, counts = optimize_wvplt_scipy('Source', 'Coinc', 'b', 2.)
    if party == 'source':
        set_polarization(2, config)
        time.sleep(twait)
        pos, counts = optimize_wvplt_scipy('Source', 'Coinc', 'sp', 2.)
        
    return pos

def load_config_from_file(fname):
    config_fp = open(fname,'r')
    config = yaml.load(config_fp, Loader=yaml.SafeLoader)
    config_fp.close()
    return config 

def write_config_to_file(config, fname='client.yaml'):
    config_fp = open(fname,'w')
    yaml.dump(config, config_fp, default_flow_style=False)
    config_fp.close()
    return config 

def save_config_to_file(config, fname='client.yaml'):
    config_fp = open(fname,'w')
    yaml.dump(config, config_fp, default_flow_style=False)
    config_fp.close()

def main():
    global motorInfo
    global logger
    logger = setup_logger()
    configFName = '../config/polarization.yaml'
    config = load_config_from_file(configFName)
    motorInfo = config['server']

    polarization_server = PolarizationServer(config, configFName, port=config['port'], n_workers=1)
    
if __name__ == '__main__':
      main()  
