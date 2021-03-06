import os
import json
import h5py
from batchlib.util import read_table


def has_two_bg_wells(name):
    isT = 'plateT' in name

    is_recentK = False
    if 'plateK' in name or 'PlateK' in name:
        prelen = len('plateK')
        kid = int(name[prelen:prelen+2])
        if kid >= 22:
            is_recentK = True

    return isT or is_recentK


def get_expected_bg_well(name, bg_wells_per_plate):
    if name in bg_wells_per_plate:
        return bg_wells_per_plate[name]
    if has_two_bg_wells(name):
        return ['H01', 'G01']
    else:
        return ['H01']


def get_channel_dict(name):
    root_in = '/g/kreshuk/data/covid/covid-data-vibor'
    channel_mapping = os.path.join(root_in, name, 'channel_mapping.json')
    with open(channel_mapping) as f:
        channel_mapping = json.load(f)
    channel_dict = {name: f'{name}_min_well' for name in channel_mapping.values()
                    if name is not None and name.startswith('serum')}
    return channel_dict


def get_actual_bg_well(name, root, channel_dict, bg_table_key='plate/backgrounds_from_min_well'):
    folder = os.path.join(root, name)
    table_path = os.path.join(folder, f'{name}_table.hdf5')
    with h5py.File(table_path, 'r') as f:
        col_names, table = read_table(f, bg_table_key)
    return {chan_name: table[0, col_names.index(well_key)] for chan_name, well_key in channel_dict.items()}


def get_well_bg_fractions(name, root):
    folder = os.path.join(root, name)
    table_path = os.path.join(folder, f'{name}_table.hdf5')
    bg_table_key = 'wells/backgrounds'
    with h5py.File(table_path, 'r') as f:
        col_names, table = read_table(f, bg_table_key)

    wells = table[:, col_names.index('well_name')]
    fractions = table[:, col_names.index('background_fraction')]
    values = table[:, col_names.index('serum_IgG_median')]

    return dict(zip(wells, values)), dict(zip(wells, fractions))


def check_bg_well_for_all_plates(root):
    plate_names = os.listdir(root)
    plate_names.sort()

    bg_wells_per_plate = '../../misc/plates_to_background_well.json'
    with open(bg_wells_per_plate) as f:
        bg_wells_per_plate = json.load(f)

    n_disagree = 0
    n_total = 0
    for name in plate_names:
        expected_bg_well = get_expected_bg_well(name, bg_wells_per_plate)

        if expected_bg_well is None:
            continue

        channel_dict = get_channel_dict(name)
        actual_bg_well = get_actual_bg_well(name, root, channel_dict)
        igg_well = actual_bg_well['serum_IgG']
        bg_vals, bg_fractions = get_well_bg_fractions(name, root)
        if igg_well not in expected_bg_well:
            print("Plate", name, ": expected bg well to be one of", expected_bg_well, "but got", igg_well)
            print("BG-fraction for expected wells:")
            for well in expected_bg_well + [igg_well]:
                print(well, ": bg-val:", bg_vals[well], "fraction:", bg_fractions[well])
            n_disagree += 1
        n_total += 1

    print("Error rate:", float(n_disagree) / float(n_total))


def check_plate():
    from batchlib.analysis.background_extraction import BackgroundFromWells
    folder = '/g/kreshuk/data/covid/data-processed/plateT8rep1_20200516_091304_432'
    chan_names = ['serum_IgG', 'serum_IgA']
    job = BackgroundFromWells(well_list=['H01', 'G01'], output_table='backgrounds/blub',
                              seg_key='segmentation', channel_names=chan_names)
    job(folder, force_recompute=True)


if __name__ == '__main__':
    root = '/g/kreshuk/data/covid/data-processed'
    # check_bg_well_for_all_plates(root)
    check_plate()
