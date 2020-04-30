import os
import time

import configargparse

from batchlib import run_workflow
from batchlib.analysis.cell_level_analysis import (CellLevelAnalysis,
                                                   DenoiseByGrayscaleOpening,
                                                   InstanceFeatureExtraction,
                                                   FindInfectedCells)
from batchlib.outliers.outlier import get_outlier_predicate
from batchlib.preprocessing import Preprocess, get_serum_keys
from batchlib.segmentation import SeededWatershed
from batchlib.segmentation.stardist_prediction import StardistPrediction
from batchlib.segmentation.torch_prediction import TorchPrediction
from batchlib.segmentation.unet import UNet2D
from batchlib.util import get_logger
from batchlib.util.plate_visualizations import all_plots

logger = get_logger('Workflow.CellAnalysis')


def get_input_keys(config, serum_in_keys):

    nuc_in_key = 'nuclei'
    marker_in_key = 'marker'

    if config.segmentation_on_corrected:
        nuc_seg_in_key = nuc_in_key + '_corrected'
        serum_seg_in_keys = [serum_in_key + '_corrected' for serum_in_key in serum_in_keys]
    else:
        nuc_seg_in_key = nuc_in_key
        serum_seg_in_keys = serum_in_keys

    if config.analysis_on_corrected:
        serum_ana_in_keys = [serum_in_key + '_corrected' for serum_in_key in serum_in_keys]
        marker_ana_in_key = marker_in_key + '_corrected'
    else:
        serum_ana_in_keys = serum_in_keys
        marker_ana_in_key = marker_in_key

    return nuc_seg_in_key, serum_seg_in_keys, marker_ana_in_key, serum_ana_in_keys


def run_cell_analysis(config):
    """
    """

    name = 'CellAnalysisWorkflow'

    # to allow running on the cpu
    if config.gpu < 0:
        config.gpu = None

    config.input_folder = os.path.abspath(config.input_folder)
    if config.folder == "":
        config.folder = config.input_folder.replace('covid-data-vibor', config.output_root_name)
        if config.use_unique_output_folder:
            config.folder += '_' + name

    misc_folder = config.misc_folder

    model_root = os.path.join(misc_folder, 'models/stardist')
    model_name = '2D_dsb2018'

    # TODO load the correct barrel corrector based on the image size
    barrel_corrector_path = os.path.join(misc_folder, config.barrel_corrector)
    if not os.path.exists(barrel_corrector_path):
        raise ValueError("Invalid barrel corrector path:", barrel_corrector_path)

    torch_model_path = os.path.join(misc_folder, 'models/torch/fg_and_boundaries_V1.torch')
    torch_model_class = UNet2D
    torch_model_kwargs = {
        'in_channels': 1,
        'out_channels': 2,
        'f_maps': [32, 64, 128, 256, 512],
        'testing': True
    }

    # get keys and identifier
    serum_in_keys = get_serum_keys(config.input_folder)
    (nuc_seg_in_key, serum_seg_in_keys,
     marker_ana_in_key, serum_ana_in_keys) = get_input_keys(config, serum_in_keys)

    outlier_predicate = get_outlier_predicate(config)

    job_list = [
        (Preprocess.from_folder, {
            'build': {
                'input_folder': config.input_folder,
                'barrel_corrector_path': barrel_corrector_path,
                'scale_factors': config.scale_factors},
            'run': {
                'n_jobs': config.n_cpus,
                'ignore_failed_outputs': True}}),  # FIXME something goes wring in the output validation..
        (TorchPrediction, {
            'build': {
                'input_key': serum_seg_in_keys[0],
                'output_key': [config.mask_key, config.bd_key],
                'model_path': torch_model_path,
                'model_class': torch_model_class,
                'model_kwargs': torch_model_kwargs,
                'scale_factors': config.scale_factors},
            'run': {
                'gpu_id': config.gpu,
                'batch_size': config.batch_size,
                'threshold_channels': {0: 0.5}}}),
        (StardistPrediction, {
            'build': {
                'model_root': model_root,
                'model_name': model_name,
                'input_key': nuc_seg_in_key,
                'output_key': config.nuc_key,
                'scale_factors': config.scale_factors},
            'run': {
                'gpu_id': config.gpu,
                'n_jobs': config.n_cpus}}),
        (SeededWatershed, {
            'build': {
                'pmap_key': config.bd_key,
                'seed_key': config.nuc_key,
                'output_key': config.seg_key,
                'mask_key': config.mask_key,
                'scale_factors': config.scale_factors},
            'run': {
                'erode_mask': 20,
                'dilate_seeds': 3,
                'n_jobs': config.n_cpus}})
    ]
    if config.marker_denoise_radius > 0:
        job_list.append((DenoiseByGrayscaleOpening, {
            'build': {
                'key_to_denoise': marker_ana_in_key,
                'radius': config.marker_denoise_radius},
            'run': {}}))
        marker_ana_in_key = marker_ana_in_key + '_denoised'

    job_list.append((InstanceFeatureExtraction, {
        'build': {
            'channel_keys': (*serum_ana_in_keys, marker_ana_in_key),
            'nuc_seg_key': config.nuc_key,
            'cell_seg_key': config.seg_key},
        'run': {'gpu_id': config.gpu}}))

    job_list.append((FindInfectedCells, {
        'build': {
            'marker_key': marker_ana_in_key,
            'cell_seg_key': config.seg_key,
            'bg_correction_key': 'means'},
        'run': {}}))

    table_identifiers = serum_ana_in_keys
    for serum_key, identifier in zip(serum_ana_in_keys, table_identifiers):
        job_list.append((CellLevelAnalysis, {
            'build': {
                'serum_key': serum_key,
                'marker_key': marker_ana_in_key,
                'cell_seg_key': config.seg_key,
                'outlier_predicate': outlier_predicate,
                'write_summary_images': True,
                'scale_factors': config.scale_factors,
                'identifier': identifier}}))

    t0 = time.time()

    run_workflow(name,
                 config.folder,
                 job_list,
                 input_folder=config.input_folder,
                 force_recompute=config.force_recompute,
                 ignore_invalid_inputs=config.ignore_invalid_inputs,
                 ignore_failed_outputs=config.ignore_failed_outputs)

    # run all plots on the output files
    plot_folder = os.path.join(config.folder, 'plots')
    for identifier in table_identifiers:
        table_path = CellLevelAnalysis.folder_to_table_path(config.folder, identifier)
        all_plots(table_path, plot_folder,
                  table_key='tables/images/default',
                  identifier=identifier,
                  stat_names=['ratio_of_median_of_means'])

    t0 = time.time() - t0
    logger.info(f"Run {name} in {t0}s")
    return name, t0


# TODO rename the default config
def cell_analysis_parser(config_folder, config_name='instance_analysis_2.conf'):
    """
    """

    doc = """Run cell based analysis workflow.
    Based on UNet boundary and foreground predictions,
    stardist nucleus prediction and watershed segmentation.
    """
    fhelp = """Folder to store the results. will default to
    /home/covid19/data/data-processed/<INPUT_FOLDER_NAME>, which will be
    overriden if this parameter is specified
    """
    mischelp = """Path to the folder batchlib/misc,
    that contains all necessary additional data to run the workflow"""

    default_config = os.path.join(config_folder, config_name)
    parser = configargparse.ArgumentParser(description=doc,
                                           default_config_files=[default_config],
                                           config_file_parser_class=configargparse.YAMLConfigFileParser)

    # mandatory
    parser.add('-c', '--config', is_config_file=True, help='config file path')
    parser.add('--input_folder', required=True, type=str, help='folder with input files as tifs')
    parser.add('--gpu', required=True, type=int, help='id of gpu for this job')
    parser.add('--n_cpus', required=True, type=int, help='number of cpus')
    parser.add('--folder', required=True, type=str, default="", help=fhelp)
    parser.add('--misc_folder', required=True, type=str, help=mischelp)

    # TODO infer the appropriate barrel corrector from the file-size instead
    # barrel corrector
    parser.add('--barrel_corrector', type=str, default="barrel_corrector.h5",
               help="name of barrel corrector file in batchlib/misc/")

    # folder options
    # this parameter is not necessary here any more, but for now we need it to be
    # compatible with the pixel-wise workflow
    parser.add("--root", default='/home/covid19/antibodies-nuclei')
    parser.add("--output_root_name", default='data-processed')
    parser.add("--use_unique_output_folder", default=False)

    # keys for intermediate data
    parser.add("--bd_key", default='boundaries', type=str)
    parser.add("--mask_key", default='mask', type=str)
    parser.add("--nuc_key", default='nucleus_segmentation', type=str)
    parser.add("--seg_key", default='cell_segmentation', type=str)

    # TODO I am not sure if changing away from the defaults works for this
    # whether to run the segmentation / analysis on the corrected or on the corrected data
    parser.add("--segmentation_on_corrected", default=True)
    parser.add("--analysis_on_corrected", default=True)

    # marker denoising
    parser.add("--marker_denoise_radius", default=0, type=int)

    # runtime options
    parser.add("--batch_size", default=4)
    parser.add("--force_recompute", default=None)
    parser.add("--ignore_invalid_inputs", default=None)
    parser.add("--ignore_failed_outputs", default=None)

    # default_scale_factors = None
    default_scale_factors = [1, 2, 4, 8, 16]
    parser.add("--scale_factors", default=default_scale_factors)

    # FIXME I don't think this pattern makes much sense ...
    # TODO this should all just be read from the misc folder
    # tagged outliers from a given plate
    # if plate_name is empty we will try to infer it from the 'input_folder' name
    parser.add("--plate_name", default=None, nargs='+', type=str, help="The name of the imaged plate")
    # if outliers_dir is empty, ../misc/tagged_outliers will be used
    parser.add("--outliers_dir", default=None, type=str,
               help="Path to the directory containing CSV files with marked outliers")

    return parser
