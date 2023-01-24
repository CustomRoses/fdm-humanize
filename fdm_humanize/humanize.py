import json
import os
from dataclasses import dataclass

try:
    from fdm_humanize.util import get_sub_dicts_with_key_and_not_value, extract_from_tar_file, json_to_html, \
        summarize_FDM_health_report
except ImportError:
    from util import get_sub_dicts_with_key_and_not_value, extract_from_tar_file, json_to_html, \
        summarize_FDM_health_report
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

ANALYSABLE_LOGS = ["dump_info/LogDump/fdm_health_report.json", "dump_info/LogDump/maintenance_log",
                   "dump_info/LogDump/operate_log", "dump_info/LogDump/PD_SMART_INFO_C0"]


@dataclass
class FDMResult:
    faulty_parts: list
    messages: list
    num_errors: int
    summary: dict

class FDMHealthReport:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.json_data = json.load(open(filepath))

    def summarize(json_dict: dict):
        """
        Make a short summary of the FDM health report. Take every part that has HealthStatus != "Good" and get the key "Suggestion" from it.
        """
        # Get all the sub-dictionaries that have a key "HealthStatus" with a value that is not "Healthy"
        sub_dicts = get_sub_dicts_with_key_and_not_value(json_dict, "HealthStatus", "Good")
        # Get the values of the key "Suggestion" from all the sub-dictionaries
        for sub_dict in sub_dicts:
            print(sub_dict)
        result = {}
        for sub_dict in sub_dicts:
            if "Suggestion" in sub_dict or "MaintenceHistroy" in sub_dict:
                suggestion = sub_dict["Suggestion"] if "Suggestion" in sub_dict else ""
                history = sub_dict["History"] if "History" in sub_dict else ""
                if "MaintenceHistroy" in sub_dict:
                    history = sub_dict["MaintenceHistroy"]
                component = sub_dict["ComponentType"]
                sn = sub_dict["SN"] if "SN" in sub_dict else ""
                for event in history:
                    print(event)
                    if "SN" in event:
                        sn = event["SN"]
                result[(component, sn)] = suggestion

        # Return the suggestions as a string
        return result

    def get_faulty_parts(self) -> list:
        """Get a list of faulty parts from the health report"""

        return [json_to_html(part) for part in self.json_data["HealthReport"]]


def analyse_file(filename) -> FDMResult:
    """Analyse a file and return a list of faulty parts, a list of messages, the number of errors, and a summary of the FDM health report"""

    # initialize empty lists to store faulty parts and messages
    faulty_parts = []
    messages = []
    num_errors = 0

    # if the filename is a tar.gz file and has not yet been extracted, extract it to the "extracted" directory
    if filename.endswith(".tar.gz") and not os.path.exists(os.path.join("./extracted", filename[:-7])):
        logger.info("Extracting %s", filename)
        extract_logs(os.path.join("./uploaded_files", filename), os.path.join("./extracted", filename[:-7]))

    # if the file has been extracted, open all relevant files in the extracted directory
    if os.path.exists(os.path.join("./extracted", filename[:-7])):
        logger.info("Analysing %s", filename)
        for root, dirs, files in os.walk(os.path.join("./extracted", filename[:-7])):
            logger.info("Analysing %s", root)
            for file in files:
                # if the file is the FDM health report, analyze it and get a list of faulty parts
                if file == "fdm_health_report.json":
                    logger.info("Analysing %s", os.path.join(root, file))
                    report = FDMHealthReport(os.path.join(root, file))
                    faulty_parts = report.get_faulty_parts()
                    num_errors += len(faulty_parts)
                # if the file is the SMART info, analyze it and get a list of messages
                if file == "PD_SMART_INFO_C0":
                    with open(os.path.join(root, file)) as f:
                        messages.extend(analyze_SMART_info(f))

    # convert messages to HTML and get a summary of the FDM health report
    messages = [json_to_html(message) for message in messages]
    summary = summarize_FDM_health_report(report.json_data)
    return FDMResult(faulty_parts, messages, num_errors, summary)



def analyze_SMART_info(f):
    # initialize an empty dictionary to store the information
    info_dict = {}

    # split the file into blocks
    for block in f.read().split("\n\n\n"):
        # split each block into lines
        for line in block.split("\n"):
            # if the line contains "Device Id", extract the device id and store it in the dictionary
            if "Device Id" in line:
                device_id = line.split(":")[1].strip()
                info_dict["Device Id"] = device_id
            # if the line contains "Slot Number", extract the slot number and store it in the dictionary
            elif "Slot Number" in line:
                slot_number = line.split(":")[1].strip()
                info_dict["Slot Number"] = slot_number
            # if the line contains "Interface Type", extract the interface type and store it in the dictionary
            elif "Interface Type" in line:
                interface_type = line.split(":")[1].strip()
                info_dict["Interface Type"] = interface_type
            # if the line is not one of the above, it must contain SMART attribute information
            else:
                # if the line is empty or contains certain phrases, skip it
                if line in ["Vender Specific SMART Attributes with Thresholds:", ""] \
                        or "Physical Drive SMART information attached to RAID Controller" in line \
                        or "SMART Attributes Data Revision Number" in line:
                    continue
                # if the line ends with ")", remove the last three words
                if line.endswith(")"):
                    line = " ".join(line.split()[:-3])
                # split the line into pieces and store the information in the dictionary
                _, attr_name, flag, value, worst, threshhold, type, updated, when_failed, raw_value = line.split()
                info_dict[attr_name] = {"flag": flag, "value": value, "worst": worst,
                                        "threshhold": threshhold, "type": type, "updated": updated,
                                        "when_failed": when_failed, "raw_value": raw_value}
    # return the dictionary containing all of the information
    return info_dict


def extract_logs(filepath: str, destination: str):
    """Extract all analysable log files from a tar file"""
    logger.info("Extracting logs from %s to %s", filepath, destination)
    extract_from_tar_file(filepath, ANALYSABLE_LOGS, destination)


if __name__ == "__main__":
    filepath = "2288HV5_2106194MKDX3N7000001_20221212-0833.tar.gz"
    # analyze the log file at the given filepath
    faulty_parts, messages, num_errors = analyse_file(filepath)
    print(faulty_parts)
    print(messages)
    print(num_errors)
