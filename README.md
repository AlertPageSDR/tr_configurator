# tr_configurator
Tunk-Recorder config auto generation with Radio Reference

```
usage: main.py [-h] [-r] -s SITES [SITES ...] --system SYSTEM [-o OUTPUT_DIR] -u USERNAME -p PASSWORD [--talkgroups] [--sdr_sample_rate SDR_SAMPLE_RATE] [-g SDR_GAIN_VALUE] [--sdr_ppm_value SDR_PPM_VALUE] [--sdr_agc] [--spectrum_bandwidth SPECTRUM_BANDWIDTH] [--print] [-v] [--random_file_name] [--debug]

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
  --sdr_sample_rate SDR_SAMPLE_RATE
                        The sample rate of the SDRs in MHz
  -g SDR_GAIN_VALUE, --sdr_gain_value SDR_GAIN_VALUE
                        The SDR gain value
  --sdr_ppm_value SDR_PPM_VALUE
                        The SDR PPM value
  --sdr_agc             Enable SDR ACG
  --spectrum_bandwidth SPECTRUM_BANDWIDTH
                        The badwith of the channels in Khz
  --print               Print config out
  -v, --print_radio_spacing
                        Print radio spacing config out
  --random_file_name    Append data to the filename
  --debug               Print debug info out
```