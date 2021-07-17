#!/usr/bin/env python3
from datetime import timedelta, datetime
from os import error
from time import sleep
from requests import get, post
import re
import json

######### META DATA #################
# For data collection organizational purposes
USER_ID = ''            # e.g. Discord handle
PRINTER_MODEL = ''      # e.g. 'voron_v2_350'
MEASURE_TYPE = ''       # e.g. 'nozzle_pin', 'microswitch_probe', etc.
NOTES = ''              # anything note-worthy about this particular run, no "=" characters
#####################################

######### CONFIGURATION #############
BASE_URL = 'http://127.0.0.1'       # printer URL (e.g. http://192.168.1.15)
                                    # leave default if running locally
BED_TEMPERATURE = 105               # bed temperature for measurements
HE_TEMPERATURE = 100                # extruder temperature for measurements
PREHEAT_TIME = 10                   # Min time to preheat before homing and QGL, in minutes
HOT_DURATION = 2                    # time after bed temp reached to continue
                                    # measuring, in hours
QGL_CMD = "QUAD_GANTRY_LEVEL"       # command for QGL

# chamber thermistor config name. Change to match your own, or "" if none
# will also work with temperature_fan configs
CHAMBER_CONFIG = "temperature_sensor chamber"
#####################################


MCU_Z_POS_RE = re.compile(r'(?P<mcu_z>(?<=stepper_z:)-*[0-9.]+)')
DATA_FILENAME = "gantry_flex_test_%s_%s.csv" % (USER_ID,
    datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
start_time = datetime.now() + timedelta(days=1)
index = 0
BASE_URL = BASE_URL.strip('/') # remove any errant "/" from the address


def gather_metadata():
    resp = get(BASE_URL + '/printer/objects/query?configfile').json()
    config = resp['result']['status']['configfile']['settings']
    
    # Gather Z axis information
    config_z = config['stepper_z']
    if 'rotation_distance' in config_z.keys():
        rot_dist = config_z['rotation_distance']
        steps_per = config_z['full_steps_per_rotation']
        micro = config_z['microsteps']
        if 'gear_ratio' in config_z.keys():
            gear_ratio_conf = config_z['gear_ratio'].split(':')
            gear_ratio = float(gear_ratio_conf[0])/float(gear_ratio_conf[1])
        else:
            gear_ratio = 1.
        step_distance = (rot_dist / (micro * steps_per))/gear_ratio
    elif 'step_distance' in config_z.keys():
        step_distance = config_z['step_distance']
    else:
        step_distance = "NA"
    max_z = config_z['position_max']
    if 'second_homing_speed' in config_z.keys():
        homing_speed = config_z['second_homing_speed']
    else:
        homing_speed = config_z['homing_speed']

    # Organize
    meta = {
        'user': {
            'id': USER_ID,
            'printer': PRINTER_MODEL,
            'measure_type': MEASURE_TYPE,
            'notes': NOTES,
            'timestamp': datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S")
        },
        'script':{
            'data_structure': 3,
            'hot_duration': HOT_DURATION,
            'cool_duration': COOL_DURATION
        },
        'z_axis': {
            'step_dist' : step_distance,
            'max_z' : max_z,
            'homing_speed': homing_speed
        }
    }
    return meta

def write_metadata(meta):
    with open(DATA_FILENAME, 'w') as dataout:
        dataout.write('### METADATA ###\n')
        for section in meta.keys():
            print(section)
            dataout.write("## %s ##\n" % section.upper())
            for item in meta[section]:
                dataout.write('# %s=%s\n' % (item, meta[section][item]))
        dataout.write('### METADATA END ###\n')

def send_gcode(cmd='', retries=1):
    url = BASE_URL + "/printer/gcode/script?script=%s" % cmd
    resp = post(url)
    success = None
    for i in range(retries):
        try: 
            success = 'ok' in resp.json()['result']
        except KeyError:
            print("G-code command '%s', failed. Retry %i/%i" % (cmd, i+1, retries))
        else:
            return True
    return False

def qgl(cmd):
    gantry_leveled = False
    gantry_leveled = send_gcode(cmd, retries=3)
    if not gantry_leveled:
        raise RuntimeError("Gantry not leveled")

def set_bedtemp(t=0):
    temp_set = False
    cmd = 'SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=%.1f' % t
    temp_set = send_gcode(cmd, retries=3)
    if not temp_set:
        raise RuntimeError("Bed temp could not be set.")

def set_hetemp(t=0):
    temp_set = False
    cmd = 'SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f' % t
    temp_set = send_gcode(cmd, retries=3)
    if not temp_set:
        raise RuntimeError("HE temp could not be set.")

def clear_bed_mesh():
    mesh_cleared = False
    cmd = 'BED_MESH_CLEAR'
    mesh_cleared = send_gcode(cmd, retries=3)
    if not mesh_cleared:
        raise RuntimeError("Could not clear mesh.")

def take_bed_mesh():
    mesh_sent = False
    cmd = 'BED_MESH_CALIBRATE'
    mesh_sent = send_gcode(cmd, retries=3)
    if not mesh_sent:
        raise RuntimeError("Could not calibrate bed.")

def query_bed_mesh():
    url = BASE_URL + '/printer/objects/query?bed_mesh'
    mesh_received = False
    for attempt in range(3):
        resp = get(url).json()['result']
        mesh = resp['probed_matrix']
        if mesh != [[]]:
            mesh_received = True
            return mesh
        else:
            sleep(60)
    if not mesh_received:
        raise RuntimeError("Could not retrieve mesh")

def query_temp_sensors():
    url = BASE_URL + '/printer/objects/query?extruder&heater_bed&%s' % CHAMBER_CONFIG
    resp = get(url).json()['result']['status']
    try:
      chamber_current = resp[CHAMBER_CONFIG]['temperature']
    except KeyError:
      chamber_current = -180.
    bed_current = resp['heater_bed']['temperature']
    bed_target = resp['heater_bed']['target']
    he_current = resp['extruder']['temperature']
    he_target = resp['extruder']['target']
    return {
        'chamber_temp': chamber_current,
        'bed_temp': bed_current,
        'bed_target': bed_target,
        'he_temp': he_current,
        'he_target': he_target}

def wait_for_bedtemp():
    global start_time
    at_temp = False
    print('Heating started')
    while(1):
        temps = query_temp_sensors()
        if temps['bed_temp'] >= BED_TEMPERATURE-0.5:
            at_temp = True
            break
    start_time = datetime.now()
    print('\nBed temp reached')

def main():
    global last_measurement, start_time
    metadata = gather_metadata()
    print("Starting!\nHoming...", end='')
    # Home all
    if send_gcode('G28'):
        print("DONE")
    else:
        raise RuntimeError("Failed to home. Aborted.")

    clear_bed_mesh()
    qgl(QGL_CMD)

    send_gcode('SET_FRAME_COMP enable=0')

    set_bedtemp(BED_TEMPERATURE)
    set_hetemp(HE_TEMPERATURE)

    wait_for_bedtemp()

    # Take cold mesh    
    take_bed_mesh()
    cold_time = datetime.now()
    cold_mesh = query_bed_mesh()
    cold_temps = query_temp_sensors()

    cold_data = {'time': cold_time,
                 'temps': cold_temps,
                 'mesh': cold_mesh}

    print('Cold mesh taken, waiting for %s minutes' % (HOT_DURATION / 60))
    # wait for heat soak

    sleep(3600*HOT_DURATION)

    # Take hot mesh
    take_bed_mesh()
    hot_time = datetime.now()
    hot_mesh = query_bed_mesh()
    hot_temps = query_temp_sensors()

    hot_data = {'time': hot_time,
                 'temps': hot_temps,
                 'mesh': hot_mesh}

    print('Hot mesh taken, writing to file')
    
    # write output
    output = {'metadata': metadata,
              'cold_mesh': cold_data,
              'hot_mesh': hot_data}

    with open(DATA_FILENAME, "w") as out_file:
        json.dump(output, out_file)

    set_bedtemp()
    set_hetemp()
    send_gcode('SET_FRAME_COMP enable=1')
    print('Measurements complete!')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        set_bedtemp()
        set_hetemp()
        send_gcode('SET_FRAME_COMP enable=1')
        print("\nAborted by user!")