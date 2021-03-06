# Author: Adrien and Zhengying
# Date: 12 Dec 2018

import tensorflow as tf
import pandas as pd
import numpy as np
import glob
import os
import sys
sys.path.append('../')
from shutil import copyfile
from dataset_formatter import UniMediaDatasetFormatter
from PIL import Image
from sklearn.utils import shuffle
import cv2

def get_labels_df(dataset_dir, shuffling=True):
  """ Read labels.csv and return DataFrame
  """
  if not os.path.isdir(dataset_dir):
    raise IOError("{} is not a directory!".format(dataset_dir))
  labels_csv_files = [file for file in glob.glob(os.path.join(dataset_dir, '*labels*.csv'))]
  if len(labels_csv_files) > 1:
    raise ValueError("Ambiguous label file! Several of them found: {}".format(labels_csv_files))
  elif len(labels_csv_files) < 1:
    raise ValueError("No label file found! The name of this file should follow the glob pattern `*labels*.csv` (e.g. monkeys_labels_file_format.csv).")
  else:
    labels_csv_file = labels_csv_files[0]
  labels_df = pd.read_csv(labels_csv_file)
  if shuffling:
    labels_df = shuffle(labels_df, random_state=42)
  return labels_df

def get_merged_df(labels_df, train_size=0.8):
  """Do train/test split by generating random number in [0,1]."""
  np.random.seed(42)
  merged_df = labels_df.copy()
  def get_subset(u):
    if u < train_size:
      return 'train'
    else:
      return 'test'
  merged_df['subset'] = merged_df.apply(lambda x: get_subset(np.random.rand()), axis=1)
  return merged_df

def image_to_bytes(image, num_channels=3, tmp_filename='TMP-a78h2.jpg'):
    image = image[:, :, :num_channels] # delete useless channels
    # we have to do this because VideoCapture read frames as 3 channels images
    cv2.imwrite(tmp_filename, image)
    with open(tmp_filename, 'rb') as f:
      frame_bytes = f.read()
    return frame_bytes

def get_features(dataset_dir, filename, num_channels=3):
    """ Read a file
    """
    features = []
    filepath = os.path.join(dataset_dir, filename)
    vid = cv2.VideoCapture(filepath)
    success, image = vid.read()
    while success:
        features.append([image_to_bytes(image, num_channels=num_channels)])
        success, image = vid.read()

    os.remove('TMP-a78h2.jpg') # to clean
    return features


def get_labels(labels, confidence_pairs=False):
  """Parse label confidence pairs into two lists of labels and confidence.

  Args:
    labels: string, of form `2 0.0001 9 0.48776 0 1.0`." or "2 9 0"
    confidence_pairs: True if labels are confidence pairs.
  """
  if isinstance(labels, str):
      l_split = labels.split(' ')
  else:
      l_split = [labels]

  if confidence_pairs:
      labels = [int(x) for i, x in enumerate(l_split) if i%2 == 0]
      confidences = [float(x) for i, x in enumerate(l_split) if i%2 == 1]
  else:
      labels = [int(x) for x in l_split if x==x] # x==x to remove NaN values
      confidences = [1 for _ in l_split]

  return labels, confidences

def get_features_labels_pairs(merged_df, dataset_dir, subset='train', num_channels=3):
  def func(x):
    index, row = x
    filename = row['FileName']
    if 'LabelConfidencePairs' in row:
        labels = row['LabelConfidencePairs']
        confidence_pairs = True
    elif 'Labels' in row:
        labels = row['Labels']
        confidence_pairs = False
    else:
        raise Exception('No labels found, please check labels.csv file.')
    features = get_features(dataset_dir, filename, num_channels=num_channels) # read file
    labels = get_labels(labels, confidence_pairs=confidence_pairs) # read labels
    return features, labels

  g = merged_df[merged_df['subset'] == subset].iterrows
  features_labels_pairs = lambda:map(func, g())
  return features_labels_pairs

def show_video_from_bytes(video_bytes):
  #video_tensor = tf.image.decode_image(video_bytes)
  #with tf.Session() as sess:
  #  x = sess.run(video_tensor)
  #plt.imshow(x)
  pass

def get_all_classes(merged_df):
  if 'LabelConfidencePairs' in list(merged_df):
      label_confidence_pairs = merged_df['LabelConfidencePairs']
      confidence_pairs = True
  elif 'Labels' in list(merged_df):
      label_confidence_pairs = merged_df['Labels']
      confidence_pairs = False
  else:
      raise Exception('No labels found, please check labels.csv file.')

  labels_sets = label_confidence_pairs.apply(lambda x: set(get_labels(x, confidence_pairs=confidence_pairs)[0]))
  all_classes = set()
  for labels_set in labels_sets:
    all_classes = all_classes.union(labels_set)
  return all_classes

def im_size(input_dir, filenames):
    """ Find videos width and length
        -1 means not fixed size
    """
    s = set()
    for filename in filenames:
        vid = cv2.VideoCapture(os.path.join(input_dir, filename))
        _, image = vid.read()
        s.add((image.shape[0], image.shape[1]))

    if len(s) == 1:
        row_count, col_count = next(iter(s))
    else:
        row_count, col_count = -1, -1
    print('Videos frame size: {} x {}\n'.format(row_count, col_count))
    return row_count, col_count

def seq_size(input_dir, filenames):
    """ Find videos width and length
        -1 means not fixed size
    """
    s = set()
    for filename in filenames:
        n_frames = 0
        vid = cv2.VideoCapture(os.path.join(input_dir, filename))
        success, _ = vid.read()
        while(success):
            n_frames += 1
            success, _ = vid.read()
        s.add(n_frames)

    if len(s) == 1:
        sequence_size = next(iter(s))
    else:
        sequence_size = -1
    print('Videos sequence size: {}\n'.format(sequence_size))
    return sequence_size

def format_data(input_dir, output_dir, new_dataset_name, train_size=0.8,
                max_num_examples=None,
                num_channels=3,
                classes_list=None):
  print(input_dir)
  input_dir = os.path.normpath(input_dir)
  dataset_name = os.path.basename(input_dir)
  print('Some files in input directory:')
  print(os.listdir(input_dir)[:10])
  print()
  labels_df = get_labels_df(input_dir)
  merged_df = get_merged_df(labels_df, train_size=train_size)

  if max_num_examples and max_num_examples<=4: # if quick check, it'll be the number of examples to format for each class
    # Need at least one example of each class (tensorflow)
    #merged_df = merged_df.sample(n=max_num_examples)
    if 'LabelConfidencePairs' in list(merged_df):
        merged_df = merged_df.groupby('LabelConfidencePairs').apply(lambda x: x.sample(n=1))
    elif 'Labels' in list(merged_df):
        merged_df = merged_df.groupby('Labels').apply(lambda x: x.sample(n=1))
    else:
        raise Exception('No labels found, please check labels.csv file.')


  all_classes = get_all_classes(merged_df)

  features_labels_pairs_train =\
    get_features_labels_pairs(merged_df, input_dir, subset='train', num_channels=num_channels)
  features_labels_pairs_test =\
    get_features_labels_pairs(merged_df, input_dir, subset='test', num_channels=num_channels)

  output_dim = len(all_classes)
  num_examples_train = merged_df[merged_df['subset'] == 'train'].shape[0]
  num_examples_test = merged_df[merged_df['subset'] == 'test'].shape[0]

  filenames = labels_df['FileName']
  row_count, col_count = im_size(input_dir, filenames)
  sequence_size = seq_size(input_dir, filenames)

  dataset_formatter =  UniMediaDatasetFormatter(dataset_name,
                                                output_dir,
                                                features_labels_pairs_train,
                                                features_labels_pairs_test,
                                                output_dim,
                                                col_count,
                                                row_count,
                                                sequence_size=sequence_size, # for strides=2
                                                num_channels=num_channels,
                                                num_examples_train=num_examples_train,
                                                num_examples_test=num_examples_test,
                                                is_sequence_col='false',
                                                is_sequence_row='false',
                                                has_locality_col='true',
                                                has_locality_row='true',
                                                format='COMPRESSED',
                                                is_sequence='false',
                                                sequence_size_func=None,
                                                new_dataset_name=new_dataset_name,
                                                classes_list=classes_list)

  dataset_formatter.press_a_button_and_give_me_an_AutoDL_dataset()

  # Copy original info file to formatted dataset
  #try:
  #    for info_file_type in ['_public', '_private']:
  #        info_filepath = os.path.join(input_dir, dataset_name, dataset_name + info_file_type + '.info')
  #        new_info_filepath = os.path.join(output_dir, new_dataset_name, new_dataset_name + info_file_type + '.info')
  #        copyfile(info_filepath, new_info_filepath)
  #except Exception as e:
  #    print('Unable to copy info files')


if __name__ == '__main__':
  tf.flags.DEFINE_string('input_dir', '../../file_format/monkeys',
                         "Directory containing video datasets.")
  tf.flags.DEFINE_string('output_dir', '../../formatted_datasets/',
                         "Output data directory.")
  tf.flags.DEFINE_string('new_dataset_name', 'new_dataset',
                         "Basename of formatted dataset.")

  FLAGS = tf.flags.FLAGS
  input_dir = FLAGS.input_dir
  output_dir = FLAGS.output_dir
  new_dataset_name = FLAGS.new_dataset_name

  format_data(input_dir, output_dir, new_dataset_name)
