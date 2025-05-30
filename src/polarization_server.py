import beacon_bridge_optimizations as bc_opt
from scipy.optimize import minimize
import time
from thorlabs_apt_motor_controller import MotorController
import numpy as np
import threading
import yaml as yaml
from zmqhelper import ZMQServiceBase
import json
from datetime import datetime, date
import redis_read as r_read
import os

class MotorConnectionError(Exception):
        pass
    
class PolarizationServer(ZMQServiceBase):
    '''
    Bit authentication server for a verifier. The verifier waits for a start signal from a prover and then executes the authentication protocol using only the local computer time.
    '''
        
    def __init__(self, config, configFName, n_workers=6):
        # global logger
        
        self.config = config
        self.configFName = configFName
        self.time_start = datetime.now()
        cParams = config['config_setup']
        
        if 'redis_host' not in cParams or cParams['register_redis'] is False:
            cParams['redis_host'] = None
            
        if 'loki_host' not in cParams:
            cParams['loki_host'] = None
            
        if 'redis_port' not in cParams:
            cParams['redis_port'] = None
        
        if 'loki_port' not in cParams:
            cParams['loki_port'] = None
        
        super().__init__(rep_port = cParams['req_port'], 
            n_workers= n_workers,
            http_port = cParams['http_port'],
            service_name = cParams['name'],
            loki_host = cParams['loki_host'],
            loki_port = cParams['loki_port'],
            redis_host = cParams['redis_host'],
            redis_port = cParams['redis_port']
        )

        self.motorInfo = config['motor_servers']
        self.logger.info("")
        self.logger.info(f'Polarization server Started at {self.time_start}')
        self.logger.info(f"Config: {config}")
        
        # self.get_positions()
        
    def get_positions(self):
        self.logger.info(f"Getting motor positions: {self.motorInfo}")
        motorInfo = self.motorInfo
        for party in motorInfo:
            ip = motorInfo[party]['ip']
            port = motorInfo[party]['port']
            mc = self.connect_to_motor(ip, port)
            angles = mc.getAllPos()
            self.logger.info(f"Motor positions for {party}: {angles}")
        return angles
        
    def handle_request(self, message):
        '''
        Process the message received from the client.
        '''
        received_time = datetime.now()  # Use datetime.now() correctly
        res = {}
        resp = {}
        self.config = load_config_from_file(self.configFName)
        # print("Received message: ", str(message))

        
        # try:
        inputs = json.loads(message)
        cmd = inputs['cmd']
        params = inputs['params']
        cmd = cmd.lower()
        print(f"Command received: {cmd}, {params}")
        self.logger.info(f"Command received: {cmd} with params: {params}")
        if cmd == 'set_polarization':
            setting = str(params['setting']).lower()
            resp = self.set_polarization(self.config, **params)
            
        elif cmd == 'calibrate':
            party = params['party'].lower()
            resp = self.optimize_wvplts(party, self.config)
            if party == 'source':
                print(f"Finished source calibration with positions: {resp}")
                new_source_HWP_zero = float(resp['source_Power_1']-360.)
                self.config['source']['source_power_angle'] = new_source_HWP_zero
                self.logger.info(f"Setting new source power angle: {new_source_HWP_zero}")
                write_config_to_file(self.config, self.configFName)
                
        elif cmd == 'set_pc_to_bell_angles':
            if 'angles' not in params:
                angles = self.config['bell_angles']
                params['angles'] = angles
            self.logger.info(f"Setting PC angles to: {params['angles']}")
            resp = self.set_ch_waveplates(self.config, **params)
            
        elif cmd == 'set_power':
            power = float(params['power'])
            if power < 0. or power > 1.:
                res['error'] = "Power must be between 0 and 1"
                self.logger.error("Power must be between 0 and 1")
            else:
                source_pow = float(self.config['source']['source_power_angle'])
                resp = self.set_power(power, source_pow)
                self.logger.info(f"Setting power to: {power}")
            
        elif cmd == 'home':
            party = params['party'].lower()
            if party == 'alice':
                self.home(ip=self.motorInfo['alice']['ip'], port=self.motorInfo['alice']['port'])
                self.logger.info("Homing Alice motor")
            elif party == 'bob':
                self.home(ip=self.motorInfo['bob']['ip'], port=self.motorInfo['bob']['port'])
                self.logger.info("Homing Bob motor")
            if party == 'source':
                self.home(ip=self.motorInfo['source']['ip'], port=self.motorInfo['source']['port'])
                self.logger.info("Homing Source motor")
            elif party == 'all':
                self.homeAll()
                self.logger.info("Homing all motors")
            else:
                res['error'] = "Invalid Party"
        
        elif cmd == 'get_positions':
            resp = self.get_positions()
            
        elif cmd == 'test':
            resp = "Test successful"
            self.logger.info("Test successful") 
            
        elif cmd == 'commands':
            resp = self.config['commands']

        elif cmd == 'info':
            resp = {}
            resp['status'] = "Running"
            resp['name'] = self.config['config_setup']['name']
            resp['description'] = self.config['config_setup']['description']
            resp['settings'] = self.config['settings']
            resp['uptime'] = str(datetime.now() - self.time_start)
            
        else:
            res['error'] = "Invalid Command"

        # except Exception as e:
        #     self.logger.error(f"Error: {e}")
        #     res ={}
        #     res['error'] = "Error: "+str(e)
        #     resp = f"An error occurred while processing the command: {inputs}"
            
        res['message'] = resp
        res = self.encode_message(res)
        print("\n Sending message", res)
        self.logger.info(f"Sending message: {res}")
        return res
    
        return msgout
    
    def encode_message(self, message):
        # Convert any numpy arrays in the message to lists of strings for JSON serialization
        def convert(obj):
            if isinstance(obj, np.ndarray):
                return [x for x in obj.tolist()]
            if isinstance(obj, np.integer):
                return int(obj.item())
            if isinstance(obj, np.floating):
                return float(obj.item())
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert(i) for i in obj]
            return obj

        msgout = json.dumps(convert(message))
        # msgout = msgout.encode('utf-8')
        return msgout 
    #############

    def connect_to_motor(self, ip: str, port: int):
        return MotorController(ip, port)

    def home(self, ip: str, port: int):
        old_health_fail_threshold = self.health_fail_threshold
        self.health_fail_threshold = 20  # Increase threshold to allow for motor homing
        self.logger.debug(f"Setting health fail threshold to {self.health_fail_threshold}")
        mc = self.connect_to_motor(ip, port)
        self.logger.debug("Homing motor at {ip}:{port}")
        for motor in mc.id_dict:
            self.logger.debug(f"Homing motor {motor} at {ip}:{port}")
            mc.home(motor)
            self.logger.debug(f"Finished homing {motor} at {ip}:{port}")
            print(f"Homing {motor}")
        self.health_fail_threshold = old_health_fail_threshold  # Reset threshold
        self.logger.debug(f"Setting health fail threshold back to {self.health_fail_threshold}")
        return

    def homeAll(self):
        motorInfo = self.motorInfo
        for party in motorInfo:
            self.home(motorInfo[party]['ip'], motorInfo[party]['port'])

    def set_power(self, power, source_pow=0):
        '''Set the power of the source. The power is set by rotating the HWP'''
        # global logger
        motorInfo = self.motorInfo
        power = float(power)
        if power > 1. or power < 0.:
            return ('Improper setting. Must be between 0..1.')
        theta = np.arcsin(power ** .5) * 180. / np.pi / 2.
        mc_source = self.connect_to_motor(motorInfo['source']['ip'], motorInfo['source']['port'])
        mc_source.goto('source_Power_1', theta + source_pow)
        self.logger.info('Setting power to: ', theta)
        return theta

    def set_polarization(self, config, setting='1', use_cache=True, update_cache=False):
        # global logger
        setting = str(setting).lower()
        if setting in config['settings']:
            PHWP = config['settings'][setting]['PHWP']
            AHWP1 = config['settings'][setting]['AHWP1']
            BHWP1 = config['settings'][setting]['BHWP1']
        else:
            valid_settings = ", ".join(str(k) for k in config['settings'].keys())
            msg = f"Invalid setting: {setting}. Must be one of: {valid_settings}"
            print(msg)
            self.logger.info(msg)
            return msg

        aAlice = {}
        a_angs = bc_opt.set_bridge_to_hwp(AHWP1, alice=True, off_state_only=True, use_cache=use_cache, update_cache=update_cache)
        print("Alice bridge angles are: ", a_angs, " (hwp1, qwp1, hwp2)")
        self.logger.info(f"Alice bridge angles are: {a_angs} (hwp1, qwp1, hwp2)")
        aAlice['alice_HWP_1'] = a_angs[0]
        aAlice['alice_QWP_1'] = a_angs[1]
        aAlice['alice_HWP_2'] = a_angs[2]

        aBob = {}
        b_angs = bc_opt.set_bridge_to_hwp(BHWP1, alice=False, off_state_only=True, use_cache=use_cache, update_cache=update_cache)
        print("Bob bridge angles are: ", b_angs, " (hwp1, qwp1, hwp2)")
        self.logger.info(f"Bob bridge angles are: {b_angs} (hwp1, qwp1, hwp2)")
        aBob['bob_QWP_1'] = b_angs[1]
        aBob['bob_HWP_1'] = b_angs[0]
        aBob['bob_HWP_2'] = b_angs[2]

        aSource = {'source_HWP_1': PHWP}

        ang = {'alice': aAlice, 'bob': aBob, 'source': aSource}
        self.setBridgeWPs(ang, config)
        return ang

    def set_ch_waveplates(self, config, angles=None, use_cache=True, update_cache=False):
        '''given an array of 2 hwp settings and 1 pump waveplate setting,
        set the appropriate waveplates for a CH violation. Pockels cell
        characterization is hard coded into the bc_opt file'''
        arr = angles
        PHWP = arr[2]
        print("Starting optimization with angles: ", arr)
        self.logger.info(f"Starting optimization with angles: {arr}")
        angs_a, angs_b = bc_opt.angles_bell_test([arr[0], arr[1]], use_cache=use_cache, update_cache=update_cache)
        # print(f"Finished ch optimization. Alice angles: {angs_a}, Bob angles: {angs_b}")
        aAlice = {}
        aAlice['alice_HWP_1'] = angs_a[0]
        aAlice['alice_QWP_1'] = angs_a[1]
        aAlice['alice_HWP_2'] = angs_a[2]

        aBob = {}
        aBob['bob_QWP_1'] = angs_b[1]
        aBob['bob_HWP_1'] = angs_b[0]
        aBob['bob_HWP_2'] = angs_b[2]

        aSource = {'source_HWP_1': PHWP}

        ang = {'alice': aAlice, 'bob': aBob, 'source': aSource}
        self.setBridgeWPs(ang, config=config)
        return ang

    def setBridgeWPs(self, params, config):
        motorInfo = self.motorInfo
        t = []
        mc = []

        for party in params.keys():
            ip = motorInfo[party]['ip']
            port = motorInfo[party]['port']
            mc.append(self.connect_to_motor(ip, port))
            try:
                angles = params[party]
                for wp in angles:
                    ang = angles[wp]
                    mc.append(self.connect_to_motor(ip, port=port))
                    t.append(threading.Thread(target=mc[-1].goto, args=(wp, ang,)))
                    t[-1].start()
            except Exception as e:
                print(f'No {party} angles to set', e)
                pass
        for th in t:
            th.join()

    def get_power(self, intTime, COUNTTYPE='effAB', windowtype='no_PC'):
        time.sleep(.2 + intTime)
        COUNTTYPE = COUNTTYPE.lower()
        windowtype = windowtype.lower()
        redis_host = self.config['config_setup']['redis_host']
        redis_port = self.config['config_setup']['redis_port']
        counts = r_read.get_power(intTime, redis_host, port=redis_port)
        if windowtype == 'no_pc':
            counts = counts['VV']
        else:
            counts =counts['VV_PC']
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

    def waveplate_optimization_function(self, pos, params, int_time=1):
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
        time.sleep(.5)
        counts = self.get_power(int_time, count_type, window_type)
        if (counts < best_counts):
            best_pos = []
            for waveplate in waveplates:
                best_pos.append(float(mc_obj.getPos(waveplate)))
            params['best_pos'] = np.array(best_pos)
            params['best_counts'] = counts
        print((counts, params['best_counts']))
        return counts

    def optimize_wvplt_scipy(self, arm='Bob', count_type='Coinc',
                            wvplt='', int_time=1,
                            window_type='no_PC', custom=False, method='NM'):
        '''
        If you need to pass a custom list of waveplates, set custom = true and pass 
        an array of waveplate names to the wvplt kwarg. 
        '''
        motorInfo = self.motorInfo
        # global logger
        arm = arm.lower()
        if arm == 'bob':
            mc_obj = self.connect_to_motor(motorInfo['bob']['ip'], motorInfo['bob']['port'])
        elif arm == 'alice':
            mc_obj = self.connect_to_motor(motorInfo['alice']['ip'], motorInfo['alice']['port'])
        elif arm == 'source':
            mc_obj = self.connect_to_motor(motorInfo['source']['ip'], motorInfo['source']['port'])
        if custom:
            waveplates = wvplt
        else:
            mc_obj = self.connect_to_motor(motorInfo['source']['ip'], motorInfo['source']['port'])
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

        self.logger.info(f"The list of waveplates to be optimized is: {waveplates}")
        best_counts = np.inf
        start_pos = []
        for waveplate in waveplates:
            start_pos.append(float(mc_obj.getPos(waveplate)))

        scale = 1  # Amount to scale the step size by

        niter = 30
        params = {'count_type': count_type,
                'scale': scale,
                'start_pos': start_pos,
                'best_counts': best_counts,
                'best_pos': start_pos,
                'mc_obj': mc_obj,
                'waveplate': waveplates,
                'int_time': int_time,
                'window_type': window_type}
        options = {'xtol': 0.2, 'maxiter': niter, 'maxfev':niter}
        x0 = np.zeros_like(start_pos)

        res = minimize(self.waveplate_optimization_function, x0, params,
                    method='Powell', options=options)

        # print('')
        print(("Finished  optimization", params['best_pos'], params['best_counts']))
        self.logger.info(f"Finished  optimization with positions: {params['best_pos']} and counts: {params['best_counts']} for {waveplates}")

        for i, waveplate in enumerate(waveplates):
            mc_obj.goto(waveplate, params['best_pos'][i])
        # print(mc_obj.getAllPos(), params['best_counts'])
        optimized_positions = dict(zip(waveplates, params['best_pos']))
        return optimized_positions, params['best_counts']

    def optimize_wvplts(self, party, config):
        party = party.lower()
        twait = 3.
        if party == 'alice':
            self.set_polarization(config, 'a_calib')
            time.sleep(twait)
            pos, counts = self.optimize_wvplt_scipy('Source', 'Coinc', 'a', 2.)
        if party == 'bob':
            self.set_polarization(config, 'b_calib')
            time.sleep(twait)
            pos, counts = self.optimize_wvplt_scipy('Source', 'Coinc', 'b', 2.)
        if party == 'source':
            self.set_polarization(config, '2')
            time.sleep(twait)
            source_pow = float(self.config['source']['source_power_angle'])
            self.set_power(0., source_pow)
            time.sleep(twait)
            pos, counts = self.optimize_wvplt_scipy('Source', 'Coinc', 'sp', 2.)

        return pos

def load_config_from_file(fname):
    config_fp = open(fname, 'r')
    config = yaml.load(config_fp, Loader=yaml.SafeLoader)
    config_fp.close()
    return config

def write_config_to_file(config, fname='client.yaml'):
    config_fp = open(fname, 'w')
    yaml.dump(config, config_fp, default_flow_style=False)
    config_fp.close()
    return config

def save_config_to_file(config, fname='client.yaml'):
    config_fp = open(fname, 'w')
    yaml.dump(config, config_fp, default_flow_style=False)
    config_fp.close()

def main():
    configFName = 'config/polarization.yaml'
    config = load_config_from_file(configFName)

    polarization_server = PolarizationServer(config, configFName)
    polarization_server.start()

    
if __name__ == '__main__':
      main()
