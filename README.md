# Thermal Profiling

## Measuring gantry deflection and frame expansion

This script runs a series of defined homing and probing routines designed to
characterize how the perceived Z height of the printer changes as the printer
frame heats up. It does this by interfacing with the Moonraker API, so you will need to ensure you have Moonraker running.

First, download the script `measure_thermal_behavior.py` to your printer's Pi. My favorite way to do this is to ssh into the Pi and just clone this git repository:

`git clone https://github.com/tanaes/measure_thermal_behavior.git`


### Edit script for your printer

You'll need to edit the script (please use a vanilla text editer, such as Nano, that doesn't fuck with line endings) to include parameters appropriate for your printer. Please also fill in the `META DATA` section - this will help us find patterns across printer configurations!

```
######### META DATA #################
# For data collection organizational purposes
USER_ID = ''            # e.g. Discord handle
PRINTER_MODEL = ''      # e.g. 'voron_v2_350'
HOME_TYPE = ''          # e.g. 'nozzle_pin', 'microswitch_probe', etc.
PROBE_TYPE = ''         # e.g. 'klicky', 'omron', 'bltouch', etc.
X_RAILS = ''            # e.g. '1x_mgn12_front', '2x_mgn9'
BACKERS = ''            # e.g. 'steel_x_y', 'Ti_x-steel_y', 'mgn9_y'
NOTES = ''              # anything note-worthy about this particular run,
                        #     no "=" characters
#####################################

######### CONFIGURATION #############
BASE_URL = 'http://127.0.0.1'       # printer URL (e.g. http://192.168.1.15)
                                    # leave default if running locally
BED_TEMPERATURE = 105               # bed temperature for measurements
HE_TEMPERATURE = 100                # extruder temperature for measurements
MEASURE_INTERVAL = 1
N_SAMPLES = 3
HOT_DURATION = 3                    # time after bed temp reached to continue
                                    # measuring, in hours
COOL_DURATION = 0                   # hours to continue measuring after heaters
                                    # are disabled
SOAK_TIME = 5                       # minutes to wait for bed to heatsoak after reaching temp
MEASURE_GCODE = 'G28 Z'             # G-code called on repeated measurements, single line/macro only
QGL_CMD = "QUAD_GANTRY_LEVEL"       # command for QGL; e.g. "QUAD_GANTRY_LEVEL" or None if no QGL.
MESH_CMD = "BED_MESH_CALIBRATE"

# Full config section name of the frame temperature sensor
FRAME_SENSOR = "temperature_sensor frame"
# chamber thermistor config name. Change to match your own, or "" if none
# will also work with temperature_fan configs
CHAMBER_SENSOR = "temperature_sensor chamber"
# Extra temperature sensors to collect. Use same format as above but seperate
# quoted names with commas (if more than one).
EXTRA_SENSORS = {"frame1": "temperature_sensor frame1",
                 "z_switch": "temperature_sensor z_switch"}

#####################################
```

Note that if you want to calculate your printers frame expansion coefficient, you will need to include a frame temperature sensor definition.

If you haven't already, copy the modified `measure_thermal_behavior.py` to the Pi running Klipper/Moonraker.

## Modify printer config

You may want to adjust a few elements of your printer configuration to give the most accurate results possible. 

In particular, we have found that long/slow bed probing routines can influence results as the bed heats up the gantry extrusion over the course of the mesh probing! This often manifests as an apparent front-to-back slope in the mesh.

For our purposes, a quick probe is usually sufficient. Below are some suggested settings:

```
[probe]
##  Inductive Probe - If you use this section , please comment the [bltouch] section
##  This probe is not used for Z height, only Quad Gantry Leveling
##  In Z+ position
##  If your probe is NO instead of NC, add change pin to ^PA3
pin: ^PA3
x_offset: 0
y_offset: 18.0
z_offset: 8
speed: 10.0
lift_speed: 10.0
samples: 1
samples_result: median
sample_retract_dist: 1.5
samples_tolerance: 0.05
samples_tolerance_retries: 10


[bed_mesh]
speed: 500
horizontal_move_z: 10
mesh_min: 30,30
mesh_max: 320,320
probe_count: 7,7
mesh_pps: 2,2
relative_reference_index: 24
algorithm: bicubic
bicubic_tension: 0.2
move_check_distance: 3.0
split_delta_z: .010
fade_start: 1.0 
fade_end: 5.0
```

## Adjust printer hardware

There are a couple hardware tips we've found that help to yield repeatable and accurate results. 

#### Make sure nozzle is clean

If you are using a nozzle switch style endstop (as in stock Voron V1/V2), plastic boogers can ruin a profiling run. Make sure it is clean before the run!

#### Loosen bed screws

We have seen that over-constraint of the bed can severely impact mesh reliability at different temperatures. For optimal results, we suggest only having a single tight bed screw during profiling. 


## Run data collection

For accurate results, ensure the *entire* printer is at ambient temp. It can take a couple hours for the frame to cool down completely after a run!

Run the script with Python3:

`python3 measure_thermal_behavior.py`

You may want to run it using `nohup` so that closing your ssh connection doesn't kill the process:

`nohup python3 measure_thermal_behavior.py > out.txt &`

The script will run for about 3 hours. It will home, QGL, home again, then heat the bed up.

While the bed is heating, the toolhead will move up to 80% of maximum Z height. This is to reduce the influence of the bed heater on the X gantry extrusion as much as possible while the bed heats.

Once the bed is at temp, it will take the first mesh. Then it will collect z expansion data once per minute for the next two hours. Finally, it will do one more mesh and then cooldown.

## Processing data

The script will write the data to the folder from which it is run. 

You have two options to generate plots: run the plotting scripts on the Pi, or run them on your PC.

### Running on the RPi

You'll need to install some additional libraries to run the plotting scripts on the Pi. First, use apt-get to install pip for python3 and libatlas, which is a requirement for Numpy:

```
sudo apt-get update
sudo apt-get install python3-pip
sudo apt-get install libatlas-base-dev
```

Then, you can use pip via python3 to install the plotting script dependencies using the `requirements.txt` file from this repository:

`python3 -m pip install -r requirements.txt`

Finally, to generate the plots, just call:

`process_meshes.py thermal_quant_{}.json`.

You can include as many json-formatted datafiles as you want as positional arguments.

### Running on the PC

To run on your PC, download the `thermal_quant_{}.json` results file. 

The rest is left as an exercise to the reader.