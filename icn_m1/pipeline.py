import filter
import IO
import projection
import online_analysis
import offline_analysis
import numpy as np
import json
import os
import pickle 
import rereference
import sys

if __name__ == "__main__":


    vhdr_file = '/Users/hi/Documents/lab_work/BIDS_iEEG/sub-016/ses-left/ieeg/sub-016_ses-left_task-force_run-0_ieeg.vhdr'  # specify the file indirectly


    #vhdr_files = IO.get_all_vhdr_files(settings['BIDS_path'])  # read all files
    #vhdr_file = vhdr_files[3]

    #vhdr_file = sys.argv[1]  # read from command line the given vhdr file 

    WRITE_M1_FILES = False
    settings = IO.read_settings()  # reads settings from settings/settings.json file in a dict 

    if WRITE_M1_FILES is True:
        IO.write_all_M1_channel_files()
    
    # read grid from session
    cortex_left, cortex_right, subcortex_left, subcortex_right = IO.read_grid()
    grid_ = [cortex_left, subcortex_left, cortex_right, subcortex_right]

    bv_raw, ch_names = IO.read_BIDS_file(vhdr_file)

    subject, run, sess = IO.get_sess_run_subject(vhdr_file)

    sess_right = IO.sess_right(sess)

    # read M1 channel file
    used_channels = IO.read_M1_channel_specs(vhdr_file[:-10])

    # rereferencing
    # bv_raw = rereference.rereference(bv_raw, vhdr_file[:-10])

    # extract used channels/labels from brainvision file, split up in cortex/subcortex/labels
    data_ = IO.get_dat_cortex_subcortex(bv_raw, ch_names, used_channels)

    #dat_cortex, dat_subcortex, dat_label, ind_cortex, ind_subcortex, ind_label, ind_dat = IO.get_dat_cortex_subcortex(bv_raw, ch_names, used_channels)

    # read all used coordinates from session coordinates.tsv BIDS file
    coord_patient = IO.get_patient_coordinates(ch_names, data_["ind_cortex"], data_["ind_subcortex"], vhdr_file, settings['BIDS_path'])

    # given those coordinates and the provided grid, estimate the projection matrix
    proj_matrix_run = projection.calc_projection_matrix(coord_patient, grid_, sess_right, settings['max_dist_cortex'], settings['max_dist_subcortex'])

    # from the BIDS run channels.tsv read the sampling frequency 
    # here: the sampling frequency can be different for all channels
    # therefore read the frequency for all channels, which makes stuff complicated...
    fs_array = IO.read_run_sampling_frequency(vhdr_file).astype(int)

    # read line noise from participants.tsv
    line_noise = IO.read_line_noise(settings['BIDS_path'],subject)

    seglengths = np.array(settings['seglengths'])

    recording_time = bv_raw.shape[1] 

    normalization_samples = settings['normalization_time']*settings['resamplingrate']
    new_num_data_points = int((bv_raw.shape[1]/fs_array[0])*settings['resamplingrate'])

    # downsample_idx states the original brainvision sample indexes are used
    downsample_idx = (np.arange(0,new_num_data_points,1)*fs_array[0]/settings['resamplingrate']).astype(int)

    filter_fun = filter.calc_band_filters(settings['frequencyranges'], sample_rate=fs_array[0])

    offset_start = int(seglengths[0] / (fs_array[0]/settings['resamplingrate'])) # resampling is done wrt a common sampling frequency of 1kHz

    arr_act_grid_points = IO.get_active_grid_points(sess_right, data_["ind_label"], ch_names, proj_matrix_run, grid_)


    label_baseline_corrected = np.zeros(data_["dat_label"].shape)
    label_baseline_corrected_onoff = np.zeros(data_["dat_label"].shape)
    for label_idx in range(data_["dat_label"].shape[0]):
        label_baseline_corrected[label_idx,:], label_baseline_corrected_onoff[label_idx,:], _ =  offline_analysis.baseline_correction(data_["dat_label"][label_idx, :])

    rf_data_median, pf_data_median = offline_analysis.run(fs_array[0], settings['resamplingrate'], seglengths, settings['frequencyranges'], grid_, downsample_idx, bv_raw, line_noise, \
                      sess_right, data_, filter_fun, proj_matrix_run, arr_act_grid_points, new_num_data_points, ch_names, normalization_samples)


    run_ = {
        "vhdr_file" : vhdr_file,
        "resamplingrate" : settings['resamplingrate'],
        "BIDS_path" : settings['BIDS_path'], 
        "projection_grid" : grid_, 
        "bv_raw" : bv_raw, 
        "ch_names" : ch_names, 
        "subject" : subject, 
        "run" : run, 
        "sess" : sess, 
        "sess_right" :  sess_right, 
        "used_channels" : used_channels, 
        "data_" : data_,
        "coord_patient" : coord_patient, 
        "proj_matrix_run" : proj_matrix_run, 
        "fs" : fs_array[0], 
        "line_noise" : line_noise, 
        "seglengths" : seglengths, 
        "normalization_samples" : normalization_samples, 
        "new_num_data_points" : new_num_data_points, 
        "downsample_idx" : downsample_idx, 
        "filter_fun" : filter_fun, 
        "offset_start" : offset_start, 
        "arr_act_grid_points" : arr_act_grid_points, 
        "rf_data_median" : rf_data_median, 
        "pf_data_median" : pf_data_median, 
        "label_baseline_corrected" : label_baseline_corrected, 
        "label_baseline_corrected_onoff" : label_baseline_corrected_onoff,
        "label_names" : np.array(ch_names)[data_["ind_label"]]
    }

    out_path = os.path.join(settings['output_path'],'sub_' + subject + '_sess_' + sess + '_run_' + run + '.p')
    
    with open(out_path, 'wb') as handle:
        pickle.dump(run_, handle, protocol=pickle.HIGHEST_PROTOCOL)

