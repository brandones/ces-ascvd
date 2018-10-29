#! env/bin/python3

import argparse
import re
from pathlib import Path

from dateutil.parser import parse
import ezcsv


# Constants ###

INPUT_DIR = Path(".") / "Input CSVs"
PATIENTS_CSV = "Pacientes.csv"
CONSULTS_CSV = "Consultas.csv"

INTERMEDIATES_DIR = Path(".") / "Intermediates"
HAS_DM_OR_HTN_FILENAME = "has-dm-or-htn.csv"
CONSULTS_FOR_FOCUS_PTS_FILENAME = "all-focus-pt-consults.csv"
WITH_HDL_DATA_FILENAME = "has-hdl-data.csv"

OUTPUT_DIR = Path(".") / "Output"
OUTPUT_FILE = "ascvd-input.csv"
OUTPUT_STATS = "col-stats.txt"
OUTPUT_NO_COL_DATA_FILE = "no-colesterol-data.csv"

PATIENT_OUTPUT_FIELDS = [
    "Apellido",
    "Nombre",
    "Sexo",
    "Comunidad",
    "FN_Ano",
    "Diabetes",
    "Hipertensión",
]
CONSULT_OUTPUT_FIELDS = ["Fecha", "Nota", "PA Sistólica", "CESid", "HDL", "Colesterol"]


class ExtractCholesterolRecords:
    def __init__(self, community):
        self.community = community

    def run(self):
        if not self.community:
            raise ValueError('Please supply a value for "community"')
        patients_csv_file = INPUT_DIR / self.community / PATIENTS_CSV
        patients_data = ezcsv.read_dicts(patients_csv_file)
        focus_patients = self.extract_focus_patients(patients_data)
        col_consults = self.extract_col_consults(focus_patients)
        self.extract_output_fields(focus_patients, col_consults)
        self.extract_missing_data_patients(focus_patients, col_consults)

    def extract_focus_patients(self, patients_data):
        with_dm_or_htn = [
            p
            for p in patients_data
            if (p["Diabetes"] == "true" or p["Hipertensión"] == "true")
        ]
        with_dm_or_htn_dir = INTERMEDIATES_DIR / self.community
        with_dm_or_htn_file = with_dm_or_htn_dir / HAS_DM_OR_HTN_FILENAME
        ezcsv.write_dicts(
            with_dm_or_htn, with_dm_or_htn_file, mkdir=True, silent_fail=True
        )
        print(
            "Out of {} total patients, found {} with DM or HTN.".format(
                len(patients_data), len(with_dm_or_htn)
            )
        )
        print("Writing list of these patients to {}".format(with_dm_or_htn_file))
        return with_dm_or_htn

    def extract_col_consults(self, focus_pts):
        focus_pts_cesids = set(p["CesID"] for p in focus_pts)

        consults_data = ezcsv.read_dicts(INPUT_DIR / self.community / CONSULTS_CSV)
        consults_for_focus_pts = [
            c for c in consults_data if c["CESid"] in focus_pts_cesids
        ]
        print()
        print(
            "Found {} consults for those patients.".format(len(consults_for_focus_pts))
        )
        consults_for_focus_pts_file = (
            INTERMEDIATES_DIR / self.community / CONSULTS_FOR_FOCUS_PTS_FILENAME
        )
        print(
            "Writing list of these consults to {}".format(consults_for_focus_pts_file)
        )
        ezcsv.write_dicts(
            consults_for_focus_pts,
            consults_for_focus_pts_file,
            mkdir=True,
            silent_fail=True,
        )

        with_hdl_data = []
        for c in consults_for_focus_pts:
            hdl = c["HDL"] if c["HDL"] != "" else _extract_hdl_from_note(c)
            col = (
                c["Colesterol"] if c["Colesterol"] != "" else _extract_col_from_note(c)
            )
            if hdl:  # check merely that it's not None
                c["HDL"] = hdl
                c["Colesterol"] = col
                with_hdl_data.append(c)
        with_hdl_data_file = INTERMEDIATES_DIR / self.community / WITH_HDL_DATA_FILENAME
        print()
        print("Found {} consults mentioning 'hdl'.".format(len(with_hdl_data)))
        print(
            "Of these, extracted HDL for {} of them, and Total Cholesterol for {} of them.".format(
                len([1 for l in with_hdl_data if l["HDL"] != ""]),
                len([1 for l in with_hdl_data if l["Colesterol"] != ""]),
            )
        )
        print("Writing these consults to {}".format(with_hdl_data_file))
        ezcsv.write_dicts(
            with_hdl_data, with_hdl_data_file, mkdir=True, silent_fail=True
        )
        return with_hdl_data

    def extract_output_fields(self, patients, consults):
        output_data = []
        patient_by_cesid = {p["CesID"]: p for p in patients}
        for c in consults:
            patient = patient_by_cesid[c["CESid"]]
            output_line = {f: c[f] for f in CONSULT_OUTPUT_FIELDS}
            output_line.update({f: patient[f] for f in PATIENT_OUTPUT_FIELDS})
            output_data.append(output_line)
        pruned_output_data = self.extract_last_records_per_patient(output_data)
        output_data_file = OUTPUT_DIR / self.community / OUTPUT_FILE
        print()
        print("Writing output data to {}".format(output_data_file))
        ezcsv.write_dicts(
            pruned_output_data, output_data_file, mkdir=True, silent_fail=True
        )
        return pruned_output_data

    def extract_missing_data_patients(self, patients, consults):
        cesids_with_col_data = set([c["CESid"] for c in consults])
        no_col_data = [p for p in patients if p["CesID"] not in cesids_with_col_data]
        print()
        print(
            "Found {} patients with DM or HTN but no Cholesterol data".format(
                len(no_col_data)
            )
        )
        (OUTPUT_DIR / self.community).mkdir(parents=True, exist_ok=True)
        stats_file = OUTPUT_DIR / self.community / OUTPUT_STATS
        with open(stats_file, "w", encoding="utf-8") as stats:
            stats.write(
                "Patients with DM or HTN but no cholesterol data: {}\n".format(
                    len(no_col_data)
                )
            )
        no_col_data_file = OUTPUT_DIR / self.community / OUTPUT_NO_COL_DATA_FILE
        print("Writing this list of patients to {}".format(no_col_data_file))
        ezcsv.write_dicts(no_col_data, no_col_data_file, mkdir=True, silent_fail=True)
        return no_col_data

    def extract_last_records_per_patient(self, data):
        output_by_patient = {}
        for consult in data:
            if consult["CESid"] in output_by_patient:
                existing = output_by_patient[consult["CESid"]].copy()
                try:
                    consult_is_newer = parse(consult["Fecha"]) > parse(
                        existing["Fecha"]
                    )
                except ValueError:
                    consult_is_newer = True
                newer = consult if consult_is_newer else existing
                older = existing if consult_is_newer else consult
                for k, v in newer.items():
                    if not v:
                        newer[k] = older[k]
                output_by_patient[consult["CESid"]] = newer
            else:
                output_by_patient[consult["CESid"]] = consult
        return list(output_by_patient.values())


def _extract_hdl_from_note(consult):
    """ Returns None if the note doesn't contain the string 'hdl' """
    hdl_after_regex = re.compile(r"hdl:? (\d+)")
    nota = consult["Nota"].lower()
    if "hdl" in nota:
        hdl_match = re.search(hdl_after_regex, nota)
        return hdl_match.group(1) if hdl_match else ""
    else:
        return None


def _extract_col_from_note(consult):
    col_after_regex = re.compile(r"(col|coles|colesterol|col total|total):? (\d+)")
    nota = consult["Nota"].lower()
    col_match = re.search(col_after_regex, nota)
    return col_match.group(2) if col_match else ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("community")
    args = parser.parse_args()
    ExtractCholesterolRecords(args.community).run()
