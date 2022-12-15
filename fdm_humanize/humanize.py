import json
import os

try:
    from .util import get_sub_dicts_with_key_and_not_value, extract_from_tar_file, json_to_html
except ImportError:
    from util import get_sub_dicts_with_key_and_not_value, extract_from_tar_file, json_to_html
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

ANALYSABLE_LOGS = ["dump_info/LogDump/fdm_health_report.json", "dump_info/LogDump/maintenance_log",
                   "dump_info/LogDump/operate_log", "dump_info/LogDump/PD_SMART_INFO_C0"]


class FDMHealthReport:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.json_data = json.load(open(filepath))

    def get_faulty_parts(self) -> list:
        """Get a list of faulty parts from the health report"""

        return [json_to_html(part) for part in self.json_data["HealthReport"]]



def analyse_file(filename) -> tuple[list, list, int]:
    """Analyse a file and return a list of faulty parts and a list of messages"""
    faulty_parts = []
    messages = []
    num_errors = 0
    # untar the provided file to a subdirectory of the "extracted" directory, if it is a tar file and if it is not
    # already extracted

    print(os.path.join("./extracted", filename[:-7]))
    if filename.endswith(".tar.gz") and not os.path.exists(os.path.join("./extracted", filename[:-7])):
        logger.info("Extracting %s", filename)
        extract_logs(os.path.join("./uploaded_files", filename), os.path.join("./extracted", filename[:-7]))
    # open all relevant files in the extracted directory
    if os.path.exists(os.path.join("./extracted", filename[:-7])):
        logger.info("Analysing %s", filename)
        for root, dirs, files in os.walk(os.path.join("./extracted", filename[:-7])):
            logger.info("Analysing %s", root)
            for file in files:
                if file == "fdm_health_report.json":
                    logger.info("Analysing %s", os.path.join(root, file))
                    # analyse the health report
                    faulty_parts = FDMHealthReport(os.path.join(root, file)).get_faulty_parts()
                    num_errors += len(faulty_parts)
                if file == "PD_SMART_INFO_C0":
                    with open(os.path.join(root, file)) as f:
                        messages.extend(analyze_SMART_info(f))
    messages = [json_to_html(message) for message in messages]
    return faulty_parts, messages, num_errors

def analyze_SMART_info(f):
    out = []
    for block in f.read().split("\n\n\n"):
        info_dict = {}
        for line in block.split("\n"):
            if "Device Id" in line:
                device_id = line.split(":")[1].strip()
                info_dict["Device Id"] = device_id
            elif "Slot Number" in line:
                slot_number = line.split(":")[1].strip()
                info_dict["Slot Number"] = slot_number
            elif "Interface Type" in line:
                interface_type = line.split(":")[1].strip()
                info_dict["Interface Type"] = interface_type
            else:
                if line in ["Vender Specific SMART Attributes with Thresholds:",
                            ""] or "Physical Drive SMART information attached to RAID Controller" in line or "SMART Attributes Data Revision Number" in line:
                    continue
                if line.endswith(")"):
                    line = " ".join(line.split()[:-3])
                _, attr_name, flag, value, worst, threshhold, type, updated, when_failed, raw_value = line.split()
                info_dict[attr_name] = {"flag": flag, "value": value, "worst": worst,
                                        "threshhold": threshhold, "type": type, "updated": updated,
                                        "when_failed": when_failed, "raw_value": raw_value}
        out.append(info_dict)
    return out


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
