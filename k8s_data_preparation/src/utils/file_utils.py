import json
import os
import random
import shutil
from typing import Dict, Tuple, List

import SimpleITK as sitk
import numpy as np

from .log_utils import get_logger

logger = get_logger(__name__)


def subfiles(folder, join=True, prefix=None, suffix=None, sort=True):
    if join:
        l = os.path.join  # noqa: E741
    else:
        l = lambda x, y: y  # noqa: E741, E731
    res = [
        l(folder, i)
        for i in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, i))
           and (prefix is None or i.startswith(prefix))
           and (suffix is None or i.endswith(suffix))
    ]
    if sort:
        res.sort()
    return res


def get_identifiers_from_splitted_files(folder: str):
    uniques = np.unique(
        [i[:-12] for i in subfiles(folder, suffix=".nii.gz", join=False)]
    )
    return uniques


def generate_dataset_json(
        output_file: str,
        imagesTr_dir: str,
        imagesTs_dir: str,
        modalities: Tuple,
        labels: dict,
        dataset_name: str,
        license: str = "hands off!",
        dataset_description: str = "",
        dataset_reference="",
        dataset_release="0.0",
):
    """
    :param output_file: This needs to be the full path to the dataset.json you intend to write, so
    output_file='DATASET_PATH/dataset.json' where the folder DATASET_PATH points to is the one with the
    imagesTr and labelsTr subfolders
    :param imagesTr_dir: path to the imagesTr folder of that dataset
    :param imagesTs_dir: path to the imagesTs folder of that dataset. Can be None
    :param modalities: tuple of strings with modality names. must be in the same order as the images (first entry
    corresponds to _0000.nii.gz, etc). Example: ('T1', 'T2', 'FLAIR').
    :param labels: dict with int->str (key->value) mapping the label IDs to label names. Note that 0 is always
    supposed to be background! Example: {0: 'background', 1: 'edema', 2: 'enhancing tumor'}  # noqa: E501
    :param dataset_name: The name of the dataset. Can be anything you want
    :param license:
    :param dataset_description:
    :param dataset_reference: website of the dataset, if available
    :param dataset_release:
    :return:
    """  # noqa: E501
    train_identifiers = get_identifiers_from_splitted_files(imagesTr_dir)

    if imagesTs_dir is not None:
        test_identifiers = get_identifiers_from_splitted_files(imagesTs_dir)
    else:
        test_identifiers = []

    json_dict = {}
    json_dict["name"] = dataset_name
    json_dict["description"] = dataset_description
    json_dict["tensorImageSize"] = "4D"
    json_dict["reference"] = dataset_reference
    json_dict["licence"] = license
    json_dict["release"] = dataset_release
    json_dict["modality"] = {str(i): modalities[i] for i in range(len(modalities))}
    json_dict["labels"] = {str(i): labels[i] for i in labels.keys()}

    json_dict["numTraining"] = len(train_identifiers)
    json_dict["numTest"] = len(test_identifiers)
    json_dict["training"] = [
        {"image": "./imagesTr/%s.nii.gz" % i, "label": "./labelsTr/%s.nii.gz" % i}
        for i in train_identifiers
    ]
    json_dict["test"] = ["./imagesTs/%s.nii.gz" % i for i in test_identifiers]

    if not output_file.endswith("dataset.json"):
        print(
            "WARNING: output file name is not dataset.json! This may be intentional or not. You decide. "  # noqa: E501
            "Proceeding anyways..."
        )
    save_config_json(json_dict, os.path.join(output_file))


def save_config_json(config_dict: Dict[str, str], output_json: str) -> int:
    """

    Parameters
    ----------
    output_json: JSON file path to be saved
    config_dict: dictionary to be saved in JSON format in the RESULTS_FOLDER

    """

    with open(output_json, "w") as fp:
        json.dump(config_dict, fp)
        return 0


def create_nnunet_data_folder_tree(data_folder: str, task_name: str, task_id: str):
    """
    Create nnUNet_raw_data_base folder tree, ready to be populated with the dataset

    :param data_folder: folder path corresponding to the nnUNet_raw_data_base ENV variable
    :param task_id: string used as task_id when creating task folder
    :param task_name: string used as task_name when creating task folder
    """  # noqa E501
    os.makedirs(
        os.path.join(
            data_folder,
            "nnUNet_raw_data",
            "Task" + task_id + "_" + task_name,
            "imagesTr",
        ),
        exist_ok=True,
    )
    os.makedirs(
        os.path.join(
            data_folder,
            "nnUNet_raw_data",
            "Task" + task_id + "_" + task_name,
            "labelsTr",
        ),
        exist_ok=True,
    )
    os.makedirs(
        os.path.join(
            data_folder,
            "nnUNet_raw_data",
            "Task" + task_id + "_" + task_name,
            "imagesTs",
        ),
        exist_ok=True,
    )


def split_dataset(
        input_data_folder: str, test_split_ratio: int
) -> Tuple[List[str], List[str]]:
    """

    Parameters
    ----------
    input_data_folder: folder path of the input dataset
    test_split_ratio:  integer value in the range 0-100, specifying the split ratio to be used for the test set

    Returns
    -------
    train_subjects and test_subjects: lists of strings containing subject IDs for train set and test set respectively

    """  # noqa E501
    subject = [dirs for _, dirs, _ in os.walk(input_data_folder)]
    subjects = subject[0]  # TODO: Refactor subdirectory listing

    random.seed(6)
    random.shuffle(subjects)

    split_index = len(subjects) - int(len(subjects) * test_split_ratio / 100)

    train_subjects = subjects[0:split_index]
    test_subjects = subjects[split_index:]

    return train_subjects, test_subjects


def copy_data_to_dataset_folder(
        input_data_folder: str,
        train_subjects: List[str],
        output_data_folder: str,
        image_suffix: str,
        image_subpath: str,
        config_dict: Dict[str, str],
        label_suffix: str = "None",
        labels_subpath: str = "labelsTr",
        modality: int = 0,
):
    """

    Parameters
    ----------
    input_data_folder: folder path of the input dataset
    train_subjects: string list containing subject IDs for train set
    output_data_folder: folder path where to store images ( and labels )
    image_suffix: file suffix to be used to correctly detect the file to store in imagesTr/imagesTs
    image_subpath: relative folder name where to store images in nnUNet folder hierarchy: imagesTr/imagesTs
    label_suffix: file suffix to be used to correctly detect the file to store in labelsTr. If None, label images
    are not stored
    labels_subpath: relative folder name where to store labels in nnUNet folder hierarchy ( Default: labelsTr ). If label_suffix is None,
    labels are not stored
    config_dict: dictionary with dataset and nnUNet configuration parameters
    modality: integer value indexing the modality in config_dict['modalities'] to be considered ( Default: 0 in single modality ) # noqa: E501
    """

    modality_code = "{0:04d}".format(modality)
    for directory in train_subjects:
        for _, _, files in os.walk(os.path.join(input_data_folder, directory)):
            for (
                    file
            ) in files:  # TODO : debug log to check if image+label mask are found

                if file == (directory + image_suffix):
                    image_filename = file.replace(
                        image_suffix, "_" + modality_code + config_dict["FileExtension"]
                    )
                    shutil.copy(
                        os.path.join(input_data_folder, directory, file),
                        os.path.join(output_data_folder, image_subpath, image_filename),
                    )
                if label_suffix is not None and file == (directory + label_suffix):
                    label_filename = file.replace(
                        label_suffix, config_dict["FileExtension"]
                    )
                    image_1 = sitk.ReadImage(
                        os.path.join(
                            input_data_folder, directory, directory + label_suffix
                        )
                    )
                    image_2 = sitk.ReadImage(
                        os.path.join(
                            input_data_folder, directory, directory + image_suffix
                        )
                    )
                    image_1.CopyInformation(image_2)
                    sitk.WriteImage(
                        image_1,
                        os.path.join(
                            output_data_folder, labels_subpath, label_filename
                        ),
                    )
