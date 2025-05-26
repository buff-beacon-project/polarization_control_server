# -*- coding: utf-8 -*-
"""
Created on Fri Oct 22 15:42:44 2021

@author: qittlab
"""

import redis 
import json
import time
import numpy as np 
import yaml


CHANNELCOUNTS = 'monitor:counts'
CHANNELHIST = 'monitor:histograms'
CHANNELSTATS = 'monitor:stats'
LASTTIMESTAMP = '0-0'
CHANNELVIOLATION = 'monitor:violationstats'




def get_config(r,key):
    msg = r.get(key)
    config = json.loads(msg)
    return config

def redis_config(fname, ip, port=6379):    
    # ip = 'bellamd1.campus.nist.gov'
    # port = 6379
    r = connect_to_redis(ip, port)
    configKey = 'config:timetaggers'
    config = get_config(r,configKey)
    with open("" + fname + ".yaml", 'w') as file:
        yaml.dump(config, file)

    
def get_latest_data(r, channel):
    ret = r.xrevrange(channel, count=1)[0]
    if not ret:
        return None
    ret = decode_dict(ret[1])
    return ret

def get_last_timestamp(r, channel, count=1):
    '''returns a list of entries'''
    ret = r.xrevrange(channel, count=count)
    if not ret:
        return None
    ret = [ele[0].decode() for ele in ret]
    return ret


def decode_data(rawdata):  
    retChannel = rawdata[0]
    encodedData = rawdata[1]

    msgDecode = []
    for m in encodedData:
        timeStamp = m[0].decode()
        data = decode_dict(m[1])
        msgDecode.append((timeStamp,data))
    return msgDecode

def decode_dict(dict):
    retDict = {}
    for key in dict.keys():
        val = dict[key].decode()
        try: 
            val = json.loads(val)
        except:
            val = dict[key].decode()
        key = key.decode()
        retDict[key] = val
    return retDict 

def get_data(r, channel, lastTimeStamp):
    stream = {}
    stream = {channel: lastTimeStamp}
    msg = r.xread(stream)
    if len(msg)==0:
        return None
    msgDecode = decode_data(msg[0])
    return msgDecode

def connect_to_redis(host, port, db=0):
    r = redis.Redis(host=host, port=port, db=db)
    return r


def get_power_pockels(int_time, ip, port=6379):
    LASTTIMESTAMP = '0-0'
    CHANNELVIOLATION = 'monitor:violationstats'
    CHANNELCOUNTS = 'monitor:counts'
    # ip = 'bellamd1.campus.nist.gov'
    # port = 6379
    r = connect_to_redis(ip, port)  
    trial = get_data(r,CHANNELVIOLATION, LASTTIMESTAMP)[-1][-1]
    num_queries = int(np.ceil(int_time//trial['integrationTime'] ))
    print("integration time in software is :" , trial['integrationTime'])
    ret_dict = {'VV': [[0,0,0,0],
                       [0,0,0,0],
                       [0,0,0,0],
                       [0,0,0,0]]} 

    msgCounts = None
    ret = {'isTrim':0}
    k = 0
    start = time.time()
    while k <= num_queries:
        while msgCounts is None or (ret['isTrim'] == 0):
            msgCounts = get_data(r,CHANNELVIOLATION, LASTTIMESTAMP)
            #print(msgCounts)
            if msgCounts is not None:
                ret['VV'] = (msgCounts[-1][1])['VV']
                ret['isTrim'] = msgCounts[-1][-1]['isTrim']
                if ret['isTrim'] == 1 and LASTTIMESTAMP < msgCounts[-1][0]:
                    LASTTIMESTAMP = msgCounts[-1][0]
                    #print(ret['VV']['As'])
                    for i in range(len(ret['VV'])):
                        for j in range(len((ret['VV'])[i])):
                            (ret_dict['VV'][i])[j] += ((ret['VV'])[i])[j]
                    k += 1
                else:
                    pass
        #print(i < num_queries)
        msgCounts = None
    end = time.time()
    # print(end - start, 'time \n')
    r.close()
    return ret_dict    





def get_power(int_time, ip, port=6379):
    LASTTIMESTAMP = '0-0'

    CHANNELCOUNTS = 'monitor:counts'
    # ip = 'bellamd1.campus.nist.gov'
    # port = 6379
    r = connect_to_redis(ip, port)  
    trial = get_data(r,CHANNELCOUNTS, LASTTIMESTAMP)[-1][-1]
    num_queries = int(np.ceil(int_time//trial['integrationTime'] ))

    ret_dict = {'isTrim': 0, 'integrationTime': 0,
                'VV': {'As': 0, 'Bs': 0, 'C': 0}, 
                'VV_PC': {'As': 0, 'Bs': 0, 'C': 0}, 
                'VV_Background': {'As': 0, 'Bs': 0, 'C': 0}} 

    msgCounts = None
    ret = {'isTrim':0}
    i = 0
    start = time.time()
    while i <= num_queries:
        while msgCounts is None or (ret['isTrim'] == 0):
            msgCounts = get_data(r,CHANNELCOUNTS, LASTTIMESTAMP)
            #print(msgCounts)
            if msgCounts is not None:
                ret = msgCounts[-1][1]
                if ret['isTrim'] == 1 and LASTTIMESTAMP < msgCounts[-1][0]:
                    LASTTIMESTAMP = msgCounts[-1][0]
                    #print(ret['VV']['As'])
                    for key_1, value_1 in ret.items():
                        if type(ret[key_1]) is dict:
                            for key_2, value_2 in ret[key_1].items():
                                ret_dict[key_1][key_2] += value_2
                        else:
                            ret_dict[key_1] += value_1
                    i += 1
                else:
                    pass
        #print(i < num_queries)
        ret = {'isTrim':0}
        msgCounts = None
    end = time.time()
    # print(end - start, 'time \n')
    try:
        ret_dict['VV']['effA'] = ret_dict['VV']['C']/ret_dict['VV']['Bs']
        ret_dict['VV']['effB'] = ret_dict['VV']['C']/ret_dict['VV']['As']
        ret_dict['VV']['effAB'] = ret_dict['VV']['C']/np.sqrt(ret_dict['VV']['As']
                                                           *ret_dict['VV']['Bs'])
    except ZeroDivisionError:
        ret_dict['VV']['effA'] = np.inf
        ret_dict['VV']['effB'] = np.inf
        ret_dict['VV']['effAB'] = np.inf
    try:
        ret_dict['VV_PC']['effA'] = ret_dict['VV_PC']['C']/ret_dict['VV_PC']['Bs']
        ret_dict['VV_PC']['effB'] = ret_dict['VV_PC']['C']/ret_dict['VV_PC']['As']
        ret_dict['VV_PC']['effAB'] = ret_dict['VV_PC']['C']/np.sqrt(ret_dict['VV_PC']['As']
                                                           *ret_dict['VV_PC']['Bs'])
    except ZeroDivisionError:
        ret_dict['VV_PC']['effA'] = np.inf
        ret_dict['VV_PC']['effB'] = np.inf
        ret_dict['VV_PC']['effAB'] = np.inf
        
    r.close()
    return ret_dict
    
def main():
    global CHANNELCOUNTS, LASTTIMESTAMP
    ip = 'bellamd1.campus.nist.gov'
    port = 6379

    r = connect_to_redis(ip, port)

    msgCounts = get_data(r,CHANNELVIOLATION, LASTTIMESTAMP)
    if msgCounts is not None:
        LASTTIMESTAMP = msgCounts[-1][0]
        counts = msgCounts[-1][1]
        print(msgCounts[-1][1])


if __name__ == '__main__':
    main()