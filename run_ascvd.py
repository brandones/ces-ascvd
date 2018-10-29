#! env/bin/python3

import argparse
from datetime import datetime
from pathlib import Path

import ascvd
import ezcsv

OUTPUT_DIR = Path(".") / "Output"
ASCVD_INPUT_FILENAME = "ascvd-input.csv"
OUTPUT_FILENAME = "ascvd-output.csv"

COMMUNITY = None


def main(community):
    COMMUNITY = community
    input_file = OUTPUT_DIR / COMMUNITY / ASCVD_INPUT_FILENAME
    input_data = ezcsv.read_dicts(input_file)
    output_data = []
    for p in input_data:
        try:
            ascvd_10yr = ascvd.compute_ten_year_score(
                isMale=(p["Sexo"] == "1"),
                isBlack=False,
                smoker=False,
                hypertensive=(p["Hipertensión"] == "true"),
                diabetic=(p["Diabetes"] == "true"),
                age=(datetime.now().year - int(p["FN_Ano"])),
                systolicBloodPressure=int(p["PA Sistólica"]),
                totalCholesterol=int(p["Colesterol"]),
                hdl=int(p["HDL"]),
            )
            p["ASCVD 10 year"] = ascvd_10yr
        except ValueError:  # expected for patients who are missing some data
            pass
        output_data.append(p)
    output_data_file = OUTPUT_DIR / COMMUNITY / OUTPUT_FILENAME
    ezcsv.write_dicts(output_data, output_data_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("community")
    args = parser.parse_args()
    main(args.community)
