#!/usr/bin/python3

import argparse
import datetime
import json
import uuid
import logging
import decimal
from copy import deepcopy

from zeep import Client, helpers, exceptions

VERSION = "0.2.0-dev"

system_types = {
    1: "smartnet",
    8: "p25"
}

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return str(o)
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super(DecimalEncoder, self).default(o)

class RR:
    """
    Radio Refrence interface library
    """
    def __init__(self, rr_system_id: str, username: str, password: str):
        """
        Radio Refrence interface library
        """
        self.rr_system_id = rr_system_id
        self.rr_user = username
        self.rr_pass = password
    

    def fetch_site_data(self, site_numbers, use_rr_id=True, add_metadata=False):
        """
        Radio Refrence interface library
        """
        # radio reference authentication
        client = Client("http://api.radioreference.com/soap2/?wsdl&v=15&s=rpc")
        auth_type = client.get_type("ns0:authInfo")
        my_auth_info = auth_type(
            username=self.rr_user,
            password=self.rr_pass,
            appKey="4abd9b6f-bea7-11ec-ba68-0ecc8ab9ccec",
            version="15",
            style="rpc",
        )

        # prompt user for system ID
        system = client.service.getTrsDetails(self.rr_system_id, my_auth_info)
        sysName = system.sName
        sysresult = system.sysid
        sysid = sysresult[0].sysid

        system_json = helpers.serialize_object(system, dict)

        # Read Talkgroup Data for given System ID
        sites_type = client.get_type("ns0:TrsSites")
        sites = sites_type(client.service.getTrsSites(self.rr_system_id, my_auth_info))

        if add_metadata:
            talkgroups_type = client.get_type("ns0:Talkgroups")
            talkgroups_result = talkgroups_type(
                client.service.getTrsTalkgroups(self.rr_system_id, 0, 0, 0, my_auth_info)
            )
            talkgroups_result = helpers.serialize_object(talkgroups_result, dict)

            talkgroup_cat = client.get_type("ns0:TalkgroupCats")
            talkgroup_categories = talkgroup_cat(client.service.getTrsTalkgroupCats(self.rr_system_id, my_auth_info))
            talkgroup_categories = json.loads(json.dumps(helpers.serialize_object(talkgroup_categories, dict), cls=DecimalEncoder))

        if add_metadata:
            logging.warning("[+] Fetching Radio Reference data, this will take a hot sec... You can thank RR's sTuPiD API")
            talkgroups = []
            for talkgroup in json.loads(json.dumps(talkgroups_result, cls=DecimalEncoder)):
                for cat in talkgroup_categories:
                    if cat["tgCid"] == talkgroup["tgCid"]:
                        talkgroup["cat"] = cat["tgCname"]
                        talkgroup["tag"] = ""
                        if len(talkgroup["tags"]) > 0:
                            tag_id = talkgroup["tags"][0]['tagId']
                            tag = client.service.getTag(tag_id, my_auth_info)
                            talkgroup["tag"] = tag[0]["tagDescr"]
                        talkgroups.append(talkgroup)

        results = {}
        results["sites"] = []
        if add_metadata:
            results["talkgroups"] = talkgroups
        results["system"] = json.loads(json.dumps(system_json, cls=DecimalEncoder))

        for site in sites:
            for site_number in site_numbers:
                if use_rr_id:
                    if int(site_number) == int(site["siteId"]):
                        _json = helpers.serialize_object(site, dict)
                        results["sites"].append({ "site": site["siteNumber"], "rr_site_id": site["siteId"],  "data": json.loads(json.dumps(_json, cls=DecimalEncoder))})
                else:
                    if int(site["siteNumber"]) == int(site_number):
                        _json = helpers.serialize_object(site, dict)
                        results["sites"].append({ "site": site["siteNumber"], "rr_site_id":  site["siteId"], "data": json.loads(json.dumps(_json, cls=DecimalEncoder))})
        if len(results["sites"]) == 0:
            raise ValueError("NO SITES RETURNED")
        return results
                
class tr_autotune:
    # Ya ya... I dont want to always redo the math :|
    class multipliers:
        khz = 1000
        mhz = 1e+6

    def down_convert(self, value, multiplier):
        return (value / multiplier).__round__(4)

    def up_convert(self, value, multiplier):
        return (value * multiplier).__round__(4)

    def clean_frequencies(self, freqs):
        new_freqs = []
        freqs.sort()
        for freq in freqs:
            new_freqs.append(int(self.up_convert(freq, self.multipliers.mhz)))
        return new_freqs

    def validate_coverage(self, radio_list, freq_list):
        results = []
        all_freq_covered = True
        
        for radio in range(1, len(radio_list) + 1):
            covered = False
            for freq in radio_list[radio]["freqs"]:
                if radio_list[radio]["low"]  <= freq <= radio_list[radio]["high"]:
                    covered = True
            results.append({"freq": freq, "covered": covered})

        for result in results:
            if not result["covered"]:
                all_freq_covered = False

        if not all_freq_covered:
            raise ValueError("Not all frequencies are covered!")

        logging.warning(f"[+] Validated all {str(len(freq_list))} channels are covered")

                
    def calculate_center(self, lower_freq, upper_freq, system_freqs):
        center = (lower_freq + upper_freq)/2

        rounding_change = 10000.0 # in HZ
        bad_center = False
        for freq in system_freqs:            
            freq_rounded = self.up_convert(freq, self.multipliers.mhz)
            # Check if our center freq is too close
            if freq_rounded - rounding_change <= center <= freq_rounded + rounding_change:
                bad_center = True

        if bad_center:
            center = center + rounding_change

        return center
    ########################################################################


    def find_freqs(self, SYSTEM_FREQ_LIST, MAX_SDR_BANDWIDTH=3.2, SPECTRUM_BANDWIDTH=12.5):
        # sort our freqs low to high
        SYSTEM_FREQS = self.clean_frequencies(SYSTEM_FREQ_LIST)

        # Get our bandwith's
        # sdr_bandwidth = self.up_convert(SDR_BANDWIDTH, self.multipliers.mhz)
        spectrum_bandwidth = self.up_convert(float(SPECTRUM_BANDWIDTH), self.multipliers.khz)
        half_spectrum_bandwidth = spectrum_bandwidth / 2

        # get our edge freqs
        lower_freq = SYSTEM_FREQS[0]
        upper_freq = SYSTEM_FREQS[-1]

        lower_edge = lower_freq - half_spectrum_bandwidth 
        upper_edge = upper_freq + half_spectrum_bandwidth

        # Get total bandwidth needed
        total_coverage_bandwidth = (upper_edge + half_spectrum_bandwidth) - (lower_edge - half_spectrum_bandwidth)

        # get radios needed
        # sdr_remainder = total_coverage_bandwidth / sdr_bandwidth
        # sdr_needed = int(math.ceil(sdr_remainder))

        # bandwith_per_sdr = total_coverage_bandwidth / sdr_needed
        # #bandwith_per_sdr = spectrum_bandwidth

        # leftover_bandwith = (sdr_bandwidth * sdr_needed) - total_coverage_bandwidth

        
        # Print out info on decoding
        logging.info(f"[+] Highest frequency - {self.down_convert(upper_freq, self.multipliers.mhz)}")
        logging.info(f"[-] Upper Limit - {self.down_convert(upper_edge, self.multipliers.mhz)}")
        logging.info(f"[+] Lowest frequency - {self.down_convert(lower_freq, self.multipliers.mhz)}")
        logging.info(f"[-] Lower Limit - {self.down_convert(lower_edge, self.multipliers.mhz)}")
        logging.info(f"[+] Total bandwidth to cover - {self.down_convert(total_coverage_bandwidth, self.multipliers.mhz)}")
            #logging.warning(f"[+] Total Leftover SDR bandwidth - {self.down_convert(leftover_bandwith, self.multipliers.mhz)}")
    
        # if SDR_BANDWIDTH:
        radios = self.do_a_math(SYSTEM_FREQS, half_spectrum_bandwidth, lower_edge, self.up_convert(float(MAX_SDR_BANDWIDTH), self.multipliers.mhz))
        
        logging.info(f"[+] Total Radios Needed - {str(len(radios))}")
        return {"bandwidth": self.up_convert(MAX_SDR_BANDWIDTH, self.multipliers.mhz), "results": radios}
        # else:           
        #     logging.warning("[+] Tring to find the right SDR bandwidth") 
        #     results = []
        #     for sdr_bandwidth_option in SDR_BANDWIDTH_OPTIONS:
        #         radios = self.do_a_math(SYSTEM_FREQS, half_spectrum_bandwidth, lower_edge, self.up_convert(sdr_bandwidth_option, self.multipliers.mhz))
        #         results.append({"bandwidth": sdr_bandwidth_option, "results": radios})

        #     lowest_radio_count = 1e6
        #     final_result = None
        #     sorted_results = sorted(results, key=lambda item: item["bandwidth"], reverse=True)
        #     for result in sorted_results:
        #         if len(result["results"]) <= lowest_radio_count:
        #             if debug:
        #                 logging.warning(f"[+] Found new best SDR Bandwidth - {self.up_convert(result['bandwidth'], self.multipliers.mhz)} - {len(result['results'])}") 
        #             lowest_radio_count = len(radios)
        #             final_result = result
        #     return final_result



    def do_a_math(self, SYSTEM_FREQS, half_spectrum_bandwidth, lower_edge, sdr_bandwidth):
        
        radio_high_freq, indexed_channels, radio_index = 0, 0, 1
        # System Channel count minux one for zero index
        channels = len(SYSTEM_FREQS) 

        # Dict to hold our results
        radio_matrixes = {}

        # First system Freq minus half the spectrum BW
        lower_freq = int(SYSTEM_FREQS[0] - half_spectrum_bandwidth)
        # End of the useable radio range accounting for the half_spectrum_bandwidth
        max_sdr_useable_freq = int((lower_edge + half_spectrum_bandwidth) + sdr_bandwidth)

        # While loop to track if we have indexed all channels to radios
        while (indexed_channels < channels):

            # Channel Count
            sdr_channel_count = 0
            # Check if frquencies are near each other and assign to radios
            for freq in SYSTEM_FREQS:
                # If our frequency is within the bandwidth tolerance of the SDR
                if (freq > lower_freq) and (freq < max_sdr_useable_freq):
                    # Checks if we have created the radio in the results dict yet (Avoids a key error)
                    if not radio_index in radio_matrixes:
                        radio_matrixes[radio_index] = {}
                        radio_matrixes[radio_index]["freqs"] = []

                    # Add matched frerquency to our radio's list
                    radio_matrixes[radio_index]["freqs"].append(freq)
                    # set last indexed Freq to our loops value
                    radio_high_freq = freq

                    # Increment our tracker counts for radio channels / Channels accounted for
                    sdr_channel_count += 1
                    indexed_channels += 1            

            # Set high and low and center and channel counts values for each radio
            radio_matrixes[radio_index]["high"] = radio_high_freq
            radio_matrixes[radio_index]["low"] = lower_freq
            radio_matrixes[radio_index]["channels"] = len(radio_matrixes[radio_index]["freqs"])
            radio_matrixes[radio_index]["center"] = int(self.calculate_center(lower_freq, radio_high_freq, SYSTEM_FREQS))

            # get the total bandwidth needing covered
            radio_sample_range = (radio_high_freq - lower_freq) + (half_spectrum_bandwidth * 2)


            if radio_sample_range < 900000:
                diff = 900000 - radio_sample_range
                radio_sample_range += diff

            # Check if the sample rate is valid
            is_divisable_by_eight = radio_sample_range % 8 == 0

            # Make the sample rate divisable by eight
            while not is_divisable_by_eight:
                radio_sample_range += 1
                is_divisable_by_eight = radio_sample_range % 8 == 0                


            radio_matrixes[radio_index]["sample_rate"] = radio_sample_range
            # incrment our radios - ie The next channel is beyond our bandwidth
            radio_index += 1

            # Check we havent reacherd the end of our channels
            if indexed_channels < channels:
                # Set to the next freq in the list minus half the spectrum BW
                lower_freq = int(SYSTEM_FREQS[indexed_channels] - half_spectrum_bandwidth)
                # Set to the max sdr reciveable bandwidth from the lower_freq
                max_sdr_useable_freq = int((lower_freq + half_spectrum_bandwidth) + sdr_bandwidth)
                #logging.warning(f"PREV: {lower_freq}  - NEXT: {max_sdr_useable_freq}")
            
        self.validate_coverage(radio_matrixes, SYSTEM_FREQS)
        return radio_matrixes

class trunk_recorder_helper:
    source_template = {
        "center": 0,
        "rate": 0,
        "ppm": 0,
        "gain": 49,
        "agc": False,
        "digitalRecorders": 4,
        "analogRecorders": 0,
        "driver": "osmosdr",
        "device": "rtl=00000101"
    }
    system_template =  {
        "control_channels": [
        ],
        "type": "",
        "digitalLevels": 1,
        "talkgroupsFile": "",
        "shortName": "",
        "modulation": "",
        "hideEncrypted": False,
        "uploadScript": "",
        "talkgroupDisplayFormat": "id_tag",
        "compressWav": False,
    }
    base = {
        "ver": 2,
        "sources": [         
        ],
        "systems": [           
        ],
        "captureDir": "",
        "logLevel": "info",
        "broadcastSignals": True,
        "frequencyFormat": "mhz",
        "logFile": True,
        }

def fetchSystemData(SYSTEMS, DOWNLOAD_TALKGROUPS, RR_USER, RR_PASS, USE_RR_SITE_ID):

    SYSTEM_RESULTS = []
    TR = tr_autotune()

    # Get Sites radio configs and list frequencies and channels
    for SYSTEM in SYSTEMS:
        System = RR(SYSTEM["system_id"], RR_USER, RR_PASS)
        results = System.fetch_site_data(SYSTEM["sites"], use_rr_id=USE_RR_SITE_ID, add_metadata=DOWNLOAD_TALKGROUPS)

        if DOWNLOAD_TALKGROUPS:
            talkgroups = results["talkgroups"]
            with open(f"tr_trs_tg_{SYSTEM['system_id']}.csv", 'w') as f:
                f.write("Decimal,Hex,Alpha Tag,Mode,Description,Tag,Category\n")
                for talkgroup in talkgroups:
                    hex_dec = hex(int(talkgroup["tgDec"])).strip("0x")
                    f.write(f'{talkgroup["tgDec"]},{hex_dec},{talkgroup["tgAlpha"]},{talkgroup["tgMode"].upper().replace("DE","E")},{talkgroup["tgDescr"]},{talkgroup["tag"]},{talkgroup["cat"]}\n')

        sites = []
        for site in results["sites"]:
            freqs = [float(freq["freq"]) for freq in site["data"]["siteFreqs"]]
            control_channels = []
            for freq in site["data"]["siteFreqs"]:
                if freq["use"]: control_channels.append(int(TR.up_convert(float(freq['freq']), TR.multipliers.mhz)))

            payload = {
                "id": site["data"]["siteNumber"],
                "rr_site_id": site["rr_site_id"],
                "freqs": freqs,
                "control_channels": control_channels,
                "modulation": site["data"]["siteModulation"]
                }
            sites.append(payload)

        SYSTEM_RESULTS.append({
            "system_id": SYSTEM["system_id"],
            "sites": sites,
            "system_type": results["system"]["sType"]
        })
    return SYSTEM_RESULTS

def startup():
    parser = argparse.ArgumentParser(description='Generate TR config with RR data')
    parser.add_argument('-s','--system', nargs='+', help='List of Systems : site pairs "SystemID:siteID,siteID"', required=True)
    parser.add_argument('-r','--use_rr_site_id', help='Use RR DB site ids', action='store_true')
    parser.add_argument('-u','--username', help='Radio Reference Username', required=True)
    parser.add_argument('-p','--password', help='Radio Reference Password', required=True)
    parser.add_argument('-o','--output_dir', help='The directory to place the configs', default='')
    parser.add_argument('-t','--talkgroups', help='Generate talkgroups file for system', action='store_true')
    parser.add_argument('-m','--merge', help='Merge systems into one config', action='store_true')
    parser.add_argument('-l','--loglevel', help='Set log level [debug, info, warning]', default='warning')
    parser.add_argument('-P','--print', help='Print generated config(s) out', action='store_true')
    # Advanced 
    parser.add_argument('-sm','--sdr_max_sample_rate', help='The max sample rate of the SDRs in MHz')
    parser.add_argument('-sf','--sdr_fixed_sample_rate', help='Fix the sample rate of the SDRs in MHz')
    parser.add_argument('-sb','--spectrum_bandwidth', help='The badwith of the channels in Khz', default='12.5')    
    parser.add_argument('-rs','--print_radio_spacing', help='Print radio spacing config out', action='store_true')
    parser.add_argument('-rf','--random_file_name', help='Append UUID to the filename', action='store_true')
    

    print(
        f"""
___ ____ _  _ _  _ _  _    ____ ____ ____ ____ ____ ___  ____ ____ 
 |  |__/ |  | |\ | |_/  __ |__/ |___ |    |  | |__/ |  \ |___ |__/ 
 |  |  \ |__| | \| | \_    |  \ |___ |___ |__| |  \ |__/ |___ |  \ 
                                                                   
____ ____ _  _ ____ _ ____ _  _ ____ ____ ___ ____ ____            
|    |  | |\ | |___ | | __ |  | |__/ |__|  |  |  | |__/            
|___ |__| | \| |    | |__] |__| |  \ |  |  |  |__| |  \            
                                                                                                                        
By AlertPage
ver. {VERSION}                                            
        """
    )
    return parser.parse_args()

def main():
    args = startup()

    if args.loglevel.lower() == "debug":
        logging.basicConfig(level=logging.DEBUG)
    elif args.loglevel.lower() == "info":
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    
    if args.sdr_max_sample_rate and args.sdr_fixed_sample_rate:
        logging.critical("[!] You can only use '--sdr_max_sample_rate' or '--sdr_fixed_sample_rate' ")
        exit()

    TR = tr_autotune()

    OUTPUT_DIR = args.output_dir
    SPECTRTUM_BANDWIDTH = args.spectrum_bandwidth

    RR_USER = args.username
    RR_PASS = args.password

    DOWNLOAD_TALKGROUPS = args.talkgroups
    USE_RR_SITE_ID = args.use_rr_site_id
    PRINT_RADIO_SPACING = args.print_radio_spacing
    PRINT_DATA = args.print
    RANDOM_FILE_NAME = args.random_file_name
    MERGE_SITES = args.merge

    SAMPLE_RATE = 3.2
    FIXED_SAMPLE_RATE = None
    if args.sdr_fixed_sample_rate:
        FIXED_SAMPLE_RATE = float(args.sdr_fixed_sample_rate)
        SAMPLE_RATE =  FIXED_SAMPLE_RATE

    if args.sdr_max_sample_rate:
        SAMPLE_RATE = float(args.sdr_max_sample_rate)
        
    try:
        SYSTEMS = []
        for system_pair in args.system:
            data = {
                "system_id": system_pair.split(":")[0],
                "sites": system_pair.split(":")[1].split(",")
            }
            SYSTEMS.append(data)
    except:
        logging.critical("[!] Systems must be in '--system <SYSTEM ID>:<SITE ID>,<SITE ID> <SYSTEM ID>:<SITE ID>' notation")

    try:
        SYSTEM_RESULTS = fetchSystemData(
            SYSTEMS,
            DOWNLOAD_TALKGROUPS,
            RR_USER,
            RR_PASS,
            USE_RR_SITE_ID
        )
    except exceptions.Fault:
        logging.critical("[!] Invalid Radio Reference Username or Password")

    if MERGE_SITES:
        systems = []
        main_freq_list = []
        for system in SYSTEM_RESULTS:          
            for site in system["sites"]:
                system_json = deepcopy(trunk_recorder_helper.system_template)
                
                main_freq_list.extend(site["freqs"])
        
                site_type = system_types[system["system_type"]]
                if site_type == "p25":
                    if site["modulation"] == "CPQSK":
                        modulation = "qpsk"
                    else:
                        modulation = "fsk4"
                else:
                    modulation = "fsk4"

                system_json["type"] = site_type
                system_json["rrsysid"] = system["system_id"]            
                system_json["rrsiteid"]["system_id"] = str(site["rr_site_id"])   
                system_json["modulation"] = modulation
                system_json["control_channels"].extend(site["control_channels"])
                systems.append(system_json)

        result = TR.find_freqs(main_freq_list, SAMPLE_RATE, SPECTRTUM_BANDWIDTH)
        if PRINT_RADIO_SPACING:            
            print(json.dumps(result, indent=4))

        sources = []
        for radio_index in result["results"]:
            payload = deepcopy(trunk_recorder_helper.source_template)

            payload["center"] = result["results"][radio_index]["center"]
            if FIXED_SAMPLE_RATE:
                payload["rate"] = int(TR.up_convert(FIXED_SAMPLE_RATE, TR.multipliers.mhz))
            else:
                payload["rate"] = int(result["results"][radio_index]["sample_rate"])
            payload["device"] = f"rtl={str(radio_index-1)}"
            payload["digitalRecorders"] = result["results"][radio_index]["channels"]

            sources.append(payload)

        config = deepcopy(trunk_recorder_helper.base)
        config["systems"].extend(systems) 
        config["sources"].extend(sources) 

        system_id_string = ".".join([system["system_id"] for system in SYSTEMS])
        if OUTPUT_DIR:
            filename = f"{OUTPUT_DIR}/{system_id_string}.merged.config.json"            
        else:
            filename = f"{system_id_string}.merged.config.json"

        if RANDOM_FILE_NAME:
            filename = filename.strip('.json') + '.' + str(uuid.uuid4()) + '.json'

        with open(filename, 'w') as f:
            json.dump(config, f, indent=4)
        logging.warning(f"[+] Wrote config - {filename}")

        if PRINT_DATA:
            print(json.dumps(config, indent=4))
                
        
    else:
        for system in SYSTEM_RESULTS:
            systems = []
            main_freq_list = []
            

            for site in system["sites"]:
                system_json = deepcopy(trunk_recorder_helper.system_template)
                
                main_freq_list.extend(site["freqs"])                
                
                site_type = system_types[system["system_type"]]
                if site_type == "p25":
                    if site["modulation"] == "CPQSK":
                        modulation = "qpsk"
                    else:
                        modulation = "fsk4"
                else:
                    modulation = "fsk4"

                system_json["type"] = site_type
                system_json["rrsysid"] = system["system_id"]            
                system_json["rrsiteid"] = str(site["rr_site_id"])
                system_json["modulation"] = modulation
                system_json["control_channels"].extend(site["control_channels"])
                systems.append(system_json)

            result = TR.find_freqs(main_freq_list, SAMPLE_RATE, SPECTRTUM_BANDWIDTH)
            if PRINT_RADIO_SPACING:
                print(json.dumps(result, indent=4))

            sources = []
            for radio_index in result["results"]:
                payload = deepcopy(trunk_recorder_helper.source_template)

                payload["center"] = result["results"][radio_index]["center"]
                if FIXED_SAMPLE_RATE:
                    payload["rate"] = int(TR.up_convert(FIXED_SAMPLE_RATE, TR.multipliers.mhz))
                else:
                    payload["rate"] = int(result["results"][radio_index]["sample_rate"])
                payload["device"] = f"rtl={str(radio_index-1)}"
                payload["digitalRecorders"] = result["results"][radio_index]["channels"]

                sources.append(payload)

            config = deepcopy(trunk_recorder_helper.base)
            config["systems"].extend(systems) 
            config["sources"].extend(sources) 

            if OUTPUT_DIR:
                filename = f"{OUTPUT_DIR}/{system['system_id']}.config.json"            
            else:
                filename = f"{system['system_id']}.config.json"
            if RANDOM_FILE_NAME:
                filename = filename.strip('.json') + '.' + str(uuid.uuid4()) + '.json'

            with open(filename, 'w') as f:
                json.dump(config, f, indent=4)
            logging.warning(f"[+] Wrote config - {filename}")

            if PRINT_DATA:
                print(json.dumps(config, indent=4))
                
    logging.warning("[+] TR CONFIGURATOR HAS FINISHED")

if __name__ == "__main__":
    main()
