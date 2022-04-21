# Trunk-Recorder Configurator
Tunk-Recorder config auto generation with Radio Reference API

**THIS PROGAM IS STILL IS PROGRESS, PLEASE HELP REPORT BUGS. PLEASE NOTE THAT UNTIL THERE IS A STABLE RELEASE THE CLI OPTIONS MAY CHANGE**

## Install
### requirements
1. python 3.8
2. Zeep
3. Radio Reference creds

```bash
git clone https://github.com/AlertPageSDR/tr_configurator.git
cd tr_configurator
pip install -r requirements.txt
python3 main.py -h
```

## Usage
```
usage: main.py [-h] [-r] -s SITES [SITES ...] --system SYSTEM [-o OUTPUT_DIR] -u USERNAME -p PASSWORD [--talkgroups] [-m]
               [--sdr_max_sample_rate SDR_MAX_SAMPLE_RATE] [--sdr_fixed_sample_rate SDR_FIXED_SAMPLE_RATE]
               [--spectrum_bandwidth SPECTRUM_BANDWIDTH] [--print] [-v] [--random_file_name] [--debug]

Generate TR config with RR data

optional arguments:
  -h, --help            show this help message and exit
  -r, --use_rr_site_id  Use RR site ID
  -s SITES [SITES ...], --sites SITES [SITES ...]
                        Sites to generate configs for. space seperated
  --system SYSTEM       System to generate configs for
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR
                        The directory to place the configs
  -u USERNAME, --username USERNAME
                        Radio Refrence Username
  -p PASSWORD, --password PASSWORD
                        Radio Refrence Password
  --talkgroups          Generate talkgroups file for system
  -m, --merge           Merge sites into one config
  --sdr_max_sample_rate SDR_MAX_SAMPLE_RATE
                        The max sample rate of the SDRs in MHz
  --sdr_fixed_sample_rate SDR_FIXED_SAMPLE_RATE
                        Fix the sample rate of the SDRs in MHz
  --spectrum_bandwidth SPECTRUM_BANDWIDTH
                        The badwith of the channels in Khz
  --print               Print config out
  -v, --print_radio_spacing
                        Print radio spacing config out
  --random_file_name    Append UUID to the filename
  --debug               Print debug info out
```

## Example


#### Merge multiple sites to single config
```bash
./main.py --system 6699 -s 33559 17501 -u user -p password  -r  --merge
```

#### Download talkgroups too
```bash
./main.py --system 6699 -s 33559 17501 -u user -p password  -r  --talkgroups
```


#### Varible capped sample rate
```bash
./main.py --system 6699 -s 33559 17501 -u user -p password  -r   --sdr_max_sample_rate 2.048 
```

#### Fixed sample rate
```bash
./main.py --system 6699 -s 33559 17501 -u user -p password  -r  --sdr_fixed_sample_rate 2.048 
```