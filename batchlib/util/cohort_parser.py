import glob
import os
import re

import pandas as pd

SUPPORTED_WELL_ROWS = [c for c in 'ABCDEFGH']
DEFAULT_EXCEL_DIR = os.path.join(os.path.split(__file__)[0], '../../misc/cohort_ids')

PLATE_NAME_MAP = {
    # manuscript plates
    "Plate 1": ["plate1rep3_20200505_100837_821", "plate1_IgM_20200527_125952_707", "plate1rep4_20200526_083626_191"],
    "Plate 2": ["plate2rep3_20200507_094942_519", "plate2_IgM_20200527_155923_897", "plate2rep4_20200526_101902_924"],
    "Plate 3": "plate3",
    "Plate 4": "plate4",
    "Plate 5": ["plate5rep3_20200507_113530_429", "plate5_IgM_20200528_094947_410", "plate5rep4_20200526_120907_785"],
    "Plate 6": ["plate6rep2_wp_20200507_131032_010", "plate6_IgM_20200528_111507_585",
                "plate6rep4_20200526_133304_599"],
    "Plate 7": "plate7rep1_20200426_103425_693",
    "Plate 8": ["plate8rep1_20200425_162127_242", "plate8rep2_20200502_182438_996"],
    "Plate 9": "plate9rep1_20200430_144438_974",
    "Plate 9_2": ["plate9_2rep1_20200506_163349_413", "plate9_2rep2_20200515_230124_149"],
    "Plate 9_3": "plate9_3rep1_20200513_160853_327",
    "Plate 9_4": ["plate9_4_IgM_20200604_212451_328", "plate9_4rep1_20200604_175423_514"],
    "Plate 9_5": ["plate9_5_IgM_20200605_084742_832", "plate9_5rep1_20200604_225512_896"],
    # K plates
    "Plate K10": "plateK10rep1_20200429_122048_065",
    "Plate K11": "plateK11rep1_20200429_140316_208",
    "Plate K12": "plateK12rep1_20200430_155932_313",
    "Plate K13": "plateK13rep1_20200430_175056_461",
    "Plate K14": "plateK14rep1_20200430_194338_941",
    "Plate K15": "plateK15rep1_20200502_134503_016",
    "Plate K16": "plateK16rep1_20200502_154211_240",
    "Plate K17": "plateK17rep1_20200505_115526_825",
    "Plate K18": "plateK18rep1_20200505_134507_072",
    "Plate K19": "PlateK19rep1_20200506_095722_264",
    "Plate K20": "PlateK20rep1_20200506_114059_490",
    "Plate K21": "PlateK21rep1_20200506_132517_049",
    "Plate K22": "plateK22rep1_20200509_094301_366",
    "Plate K23": "plateK23rep1_20200512_103139_970",
    "Plate K25": "plateK25rep1_20200512_123527_554",
    "Plate K26": "plateK26rep1_20200515_221809_658",
    # T plates
    "Plate T1": "plateT1rep1_20200509_114423_754",
    "Plate T2": "plateT2rep1_20200509_190719_179",
    "Plate T3": "plateT3rep1_20200509_152617_891",
    "Plate T4": "plateT4rep1_20200509_171215_610",
    "Plate T5": "plateT5rep1_20200512_143609_835",
    "Plate T6": "plateT6_20200513_105342_945",
    "Plate T7": "plateT7_20200513_131739_093",
    "Plate T8": "plateT8rep1_20200516_091304_432",
    "Plate U13_T9": "plateU13_T9rep1_20200516_105403_122"
}

# cohort_id pattern for standard and Tuebingen cohorts together with the cohort_type extractor (e.g. `Cf4` has a cohort_type of `C`, `3-0320 K` has a cohort_type of `K`)
COHORT_PATTERNS = {
    re.compile('CMV.+'): lambda x: 'E',
    re.compile('EBV.+'): lambda x: 'E',
    re.compile('3-.+'): lambda x: x[-1],
    re.compile('2-.+'): lambda x: x[-1],
    # TODO: what are those cohorts?
    re.compile('02-.+'): lambda x: x[-1] + '?',
    re.compile('[A-Z]\\d+'): lambda x: x[0]
}


def _contains_well_name(row):
    for cell in row:
        if cell in SUPPORTED_WELL_ROWS:
            return True
    return False


def _parse_well_name(row):
    for i, cell in enumerate(row):
        if cell in SUPPORTED_WELL_ROWS:
            return cell, i
    raise RuntimeError("Not a well-row")


def _parse_cohort_ids(row, well_ind):
    result = []
    for i in range(well_ind + 1, len(row)):
        cohort_id = 'unknown'
        cell = row[i]
        if not isinstance(cell, str):
            cell = str(cell)
        if any(p.match(cell) is not None for p in COHORT_PATTERNS):
            cohort_id = cell.strip()
        result.append(cohort_id)
    return result


def parse_row_cohord_ids(results, row):
    if _contains_well_name(row):
        well_row_name, well_ind = _parse_well_name(row)
        cohort_ids = _parse_cohort_ids(row, well_ind)
        well_cohort_ids = []
        for i, cohort_id in enumerate(cohort_ids):
            well_num = i + 1
            well_num = str(well_num)
            if len(well_num) == 1:
                well_num = '0' + well_num
            well_name = well_row_name + well_num
            well_cohort_ids.append((well_name, cohort_id))
            # we expect only 12 columns
            if i == 11:
                break
        results.append(well_cohort_ids)


def _load_cohort_ids_single_plate(excel_file):
    df = pd.read_excel(excel_file)
    results = []
    for row in df.values:
        parse_row_cohord_ids(results, row)
    return results


def _contains_plate_name(row):
    for cell in row:
        if isinstance(cell, str) and 'Plate ' in cell:
            return True
    return False


def _parse_plate_name(row):
    for cell in row:
        if isinstance(cell, str) and 'Plate ' in cell:
            cell = cell.strip()
            return PLATE_NAME_MAP.get(cell, cell)
    raise RuntimeError("Cannot parse plate name")


def _load_cohort_ids_multiple_plates(excel_file):
    sheets = pd.read_excel(excel_file, sheet_name=None)
    final_results = {}

    # iterate over sheets
    for df in sheets.values():
        results = []
        plate_name = None
        for row in df.values:
            if _contains_plate_name(row):
                # save current plate
                if plate_name is not None:
                    if isinstance(plate_name, list):
                        for pn in plate_name:
                            final_results[pn] = results
                    else:
                        final_results[plate_name] = results
                # reset plate name
                plate_name = _parse_plate_name(row)
                # reset results
                results = []
                continue

            parse_row_cohord_ids(results, row)

        # add final plate
        if isinstance(plate_name, list):
            for pn in plate_name:
                final_results[pn] = results
        else:
            final_results[plate_name] = results

    return final_results


class CohortIdParser:
    def __init__(self, excel_dir=DEFAULT_EXCEL_DIR):
        self.well_cohort_ids = {}
        # parse outliers
        for excel_file in glob.glob(os.path.join(excel_dir, '*.xlsx')):
            if excel_file.endswith('_final.xlsx'):
                # parse single plate
                plate_name = os.path.split(excel_file)[1]
                plate_name = plate_name[:plate_name.find('_final')]
                self.well_cohort_ids[plate_name] = _load_cohort_ids_single_plate(excel_file)
            else:
                # parse multiple plates
                self.well_cohort_ids.update(_load_cohort_ids_multiple_plates(excel_file))

    def get_cohorts_for_plate(self, plate_name):
        plate_cohorts = self.well_cohort_ids.get(plate_name)
        if plate_cohorts is None:
            return {}
        result = {}
        for row in plate_cohorts:
            result.update(dict(row))
        return result


def get_cohort_class(cohort_letter):
    if cohort_letter is None:
        return None
    assert isinstance(cohort_letter, str)
    # make sure that the comparison is not case sensitive
    cohort_letter = cohort_letter.lower()

    if cohort_letter == 'c':
        return 'positive'
    elif cohort_letter in ['b', 'a', 'x', 'z', 'e', 'cmv', 'ebv']:
        return 'control'
    else:
        return 'unknown'


def get_cohort(cohort_id):
    if cohort_id is None:
        return None

    for p, cohort_extractor in COHORT_PATTERNS.items():
        if p.match(cohort_id):
            return cohort_extractor(cohort_id)