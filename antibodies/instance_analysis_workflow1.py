#! /home/covid19/software/miniconda3/envs/antibodies/bin/python

import argparse
import os
from batchlib import run_workflow
from batchlib.preprocessing import Preprocess
from batchlib.segmentation import BoundaryAndMaskPrediction, SeededWatershed
from batchlib.segmentation.stardist import StardistPrediction


# TODO enable gpu
def run_instance_analysis(input_folder, folder, n_jobs, reorder):

    input_folder = os.path.abspath(input_folder)
    folder = input_folder.replace('covid-data-vibor', 'data-processed')

    ilastik_bin = '/home/covid19/software/ilastik-1.4.0b1-Linux/run_ilastik.sh'
    ilastik_project = '/home/covid19/antibodies-nuclei/ilastik/boundaries_and_foreground.ilp'

    model_root = '/home/covid19/antibodies-nuclei/stardist/models/pretrained'
    model_name = '2D_dsb2018'

    in_key = 'raw'
    bd_key = 'pmap'
    mask_key = 'mask'
    nuc_key = 'nuclei'
    seg_key = 'cells'

    n_threads_il = 8 if n_jobs == 1 else 4

    # TODO add analysis job
    job_dict = {
        Preprocess: {'run': {'reorder': reorder, 'n_jobs': n_jobs}},
        BoundaryAndMaskPrediction: {'build': {'ilastik_bin': ilastik_bin,
                                              'ilastik_project': ilastik_project,
                                              'input_key': in_key,
                                              'boundary_key': bd_key,
                                              'mask_key': mask_key},
                                    'run': {'n_jobs': n_jobs, 'n_threads': n_threads_il}},
        StardistPrediction: {'build': {'model_root': model_root,
                                       'model_name': model_name,
                                       'input_key': in_key,
                                       'output_key': nuc_key,
                                       'input_channel': 0}},
        SeededWatershed: {'build': {'pmap_key': bd_key,
                                    'seed_key': nuc_key,
                                    'output_key': seg_key,
                                    'mask_key': mask_key},
                          'run': {'erode_mask': 3,
                                  'dilate_seeds': 3,
                                  'n_jobs': n_jobs}}
    }

    name = 'InstanceAnalysisWorkflow'
    run_workflow(name, folder, job_dict, input_folder=input_folder)


if __name__ == '__name__':
    parser = argparse.ArgumentParser(description='Run instance analysis workflow')
    parser.add_argument('input_folder', type=str, help='')
    parser.add_argument('--folder', type=str, default=None)
    parser.add_argument('--n_jobs', type=int, help='', default=1)
    parser.add_argument('--reorder', type=int, default=0, help='')

    args = parser.parse_args()

    run_instance_analysis(args.input_folder, args.n_jobs, bool(args.reorder))
