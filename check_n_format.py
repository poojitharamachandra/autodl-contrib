# Authors: Isabelle Guyon, Adrien Pavao and Zhengying Liu
# Date: Feb 6 2019

from sys import argv, path
import glob
import os
import yaml
import tensorflow as tf
path.append('utils')
path.append('utils/image')
path.append('autodl_starting_kit_stable')
path.append('autodl_starting_kit_stable/AutoDL_ingestion_program')
import dataset_manager
import pandas as pd
import format_image
import run_local_test

# Delete flags to avoid conflicts between scripts
FLAGS = tf.flags.FLAGS
flags_dict = FLAGS._flags()
keys_list = [keys for keys in flags_dict]
for keys in keys_list:
    FLAGS.__delattr__(keys)

import data_browser


def read_metadata(input_dir):
    #filename = os.path.join(input_dir, 'private.info')
    filename = find_file(input_dir, 'private.info')
    return yaml.load(open(filename, 'r'))


def compute_stats(labels_df, label_name=None):
    res = {}
    res['sample_num'] = labels_df.shape[0]
    if 'Labels' in list(labels_df):
        res['label_num'] = len(labels_df['Labels'].unique())
    elif 'LabelConfidencePairs' in list(labels_df):
        res['label_num'] = len(labels_df['LabelConfidencePairs'].unique())
    else:
        raise Exception('No labels found, please check labels.csv file.')
    if label_name is not None:
        assert(label_name.shape[0] == res['label_num'])
    res['domain'] = 'image'
    return res


def write_info(info_file, res):
    """ Write info file from dictionary res
    """
    file = open(info_file, 'w')
    for e in res:
        file.write('{} : {}\n'.format(e, res[e]))
    file.close()


def find_file(input_dir, name):
    """ Find filename containing 'name'
    """
    filename = [file for file in glob.glob(os.path.join(input_dir, '*{}*'.format(name)))]
    return filename[0]


def format_data(input_dir, output_dir, fake_name, effective_sample_num):
    print('Formatting... {} samples'.format(effective_sample_num))
    # TODO: use effective_sample_num
    format_image.format_data(input_dir, output_dir, fake_name)


def run_baseline(data_dir, code_dir):
    print('Running baseline...')
    run_local_test.run_baseline(data_dir, code_dir)


def manual_check(data_dir):
    print('Checking manually...')
    data_browser.show_examples(data_dir)


def is_formatted(output_dir):
    """ Check if data are already formatted """
    return os.path.exists(output_dir)

if __name__=="__main__":

    if len(argv)==2:
        input_dir = argv[1]
        input_dir = os.path.normpath(input_dir)
        output_dir = os.path.join(input_dir + '_formatted')
    else:
        print('Please enter a dataset directory')
        exit()

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # Read the meta-data in private.info.
    metadata = read_metadata(input_dir)
    fake_name = metadata['name']
    print(metadata['name'])
    labels_df = format_image.get_labels_df(input_dir)
    print(labels_df.head())

    label_name = None
    label_file = os.path.join(input_dir, 'label.name')
    if os.path.exists(label_file):
        label_name = pd.read_csv(label_file, header=None)
        print(label_name.head())

    # Compute simple statistics about the data (file number, etc.) and check consistency with the CSV file containing the labels.
    res = compute_stats(labels_df, label_name=label_name)
    print(res)

    public_info_file = os.path.join(output_dir, 'public.info')
    write_info(public_info_file, res)


    # Ask user

    effective_sample_num = res['sample_num']

    if is_formatted(output_dir):
        # already exists
        if not input('Overwrite existing formatted data? [Y/n] ') in ['n', 'N']:
            # Overwrite
            if not input('Quick check? [Y/n] ') in ['n', 'N']:
                # quick check
                print('Quick check enabled: running script on a small subset of data to check if everything works as it should.')
                effective_sample_num = min(effective_sample_num, 10)

            elif input('Re-format all {} files? [Y/n] '.format(effective_sample_num)) in ['n', 'N']:
                # quick check
                effective_sample_num = min(effective_sample_num, 10)

        else:
            effective_sample_num = 0

    # booleans
    do_run_baseline = not input('Run baseline on formatted data? [Y/n] ') in ['n', 'N']
    do_manual_check = not input('Do manual check? [Y/n] ') in ['n', 'N']

    # format data in TFRecords
    format_data(input_dir, output_dir, fake_name, effective_sample_num)
    formatted_dataset_path = os.path.join(output_dir, fake_name)

    # run baseline
    if do_run_baseline:
        code_dir = './autodl_starting_kit_stable/AutoDL_sample_code_submission'
        run_baseline(formatted_dataset_path, code_dir)
        # TODO: save results in log file

    # manual check
    if do_manual_check:
        manual_check(formatted_dataset_path)
