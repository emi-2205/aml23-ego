import glob
from abc import ABC
import pandas as pd
from .epic_record import EpicVideoRecord
from .action_record import ActionEMGRecord
import torch.utils.data as data
from PIL import Image
import os
import os.path
from utils.logger import logger
import numpy as np

class EpicKitchensDataset(data.Dataset, ABC):
    def __init__(self, split, modalities, mode, dataset_conf, num_frames_per_clip, num_clips, dense_sampling,
                 transform=None, load_feat=False, additional_info=False, **kwargs):
        """
        split: str (D1, D2 or D3)
        modalities: list(str, str, ...)
        mode: str (train, test/val)
        dataset_conf must contain the following:
            - annotations_path: str
            - stride: int
        dataset_conf[modality] for the modalities used must contain:
            - data_path: str
            - tmpl: str
            - features_name: str (in case you are loading features for a predefined modality)
            - (Event only) rgb4e: int
        num_frames_per_clip: dict(modality: int)
        num_clips: int
        dense_sampling: dict(modality: bool)
        additional_info: bool, set to True if you want to receive also the uid and the video name from the get function
            notice, this may be useful to do some proper visualizations!
        """
        self.modalities = modalities  # considered modalities (ex. [RGB, Flow, Spec, Event])
        self.mode = mode  # 'train', 'val' or 'test'
        self.dataset_conf = dataset_conf
        self.num_frames_per_clip = num_frames_per_clip
        self.dense_sampling = dense_sampling
        self.num_clips = num_clips
        self.stride = self.dataset_conf.stride
        self.additional_info = additional_info

        if self.mode == "train":
            pickle_name = split + "_train.pkl"
        elif kwargs.get('save', None) is not None:
            pickle_name = split + "_" + kwargs["save"] + ".pkl"
        else:
            pickle_name = split + "_test.pkl"

        self.list_file = pd.read_pickle(os.path.join(self.dataset_conf.annotations_path, pickle_name))
        logger.info(self.list_file)
        logger.info(f"Dataloader for {split}-{self.mode} with {len(self.list_file)} samples generated")
        self.video_list = [EpicVideoRecord(tup, self.dataset_conf) for tup in self.list_file.iterrows()]
        self.transform = transform  # pipeline of transforms
        self.load_feat = load_feat

        if self.load_feat:
            self.model_features = None
            for m in self.modalities:
                # load features for each modality
                model_features = pd.DataFrame(pd.read_pickle(os.path.join("saved_features",
                                                                          self.dataset_conf[m].features_name + "_" +
                                                                          pickle_name))['features'])[["uid", "features_" + m]]
                if self.model_features is None:
                    self.model_features = model_features
                else:
                    self.model_features = pd.merge(self.model_features, model_features, how="inner", on="uid")

            self.model_features = pd.merge(self.model_features, self.list_file, how="inner", on="uid")

    def _get_train_indices(self, record, modality='RGB'):
        record_num_frames = record.num_frames[modality]
        num_frames_per_clip = self.num_frames_per_clip[modality]
        desired_num_frames = num_frames_per_clip * self.num_clips
        sampled_frames_inidices_list = []
    
        if self.dense_sampling[modality]:
            ##* DENSE Sampling
            clip_radius = (num_frames_per_clip // 2)
            for clip_number in range(self.num_clips):
                    clip_central_point = np.random.randint(clip_radius, record_num_frames-clip_radius+2) # se record_num_frames=80 e cp=64 => sampled_frames_inidices_list=[48,..,64,..78], per questo il +2
                    clip_frames_inidices_list = list(range(clip_central_point-clip_radius, clip_central_point+clip_radius+1))
                    #*Se volessimo una lista di array numpy dove ogni array ha i frame di una clip
                    #clip_frames_indices_list = np.arange(clip_central_point-clip_radius, clip_central_point+clip_radius, frames_interval)
                    #sampled_frames_inidices_list.append(clip_frames_indices_list)
                    #*Caso di una lista piatta con solo indici
                    sampled_frames_inidices_list.extend(clip_frames_inidices_list[:num_frames_per_clip])
        else:
            ##* UNIFORM Sampling
            def uniform_sampling(clip_window):
                clip_radius = (clip_window // 2)
                frames_interval = clip_window//num_frames_per_clip

                for clip_number in range(self.num_clips):
                        clip_central_point = np.random.randint(clip_radius, record_num_frames-clip_radius+2)
                        clip_frames_inidices_list = list(range(clip_central_point-clip_radius, clip_central_point+clip_radius+1, frames_interval))
                        sampled_frames_inidices_list.extend(clip_frames_inidices_list[:num_frames_per_clip])
        
            if record_num_frames >= 75:
                uniform_sampling(75)    
            elif record_num_frames>=50:
                uniform_sampling(50)
            elif record_num_frames>=25:
                uniform_sampling(25)
            else:
                raise SystemError(f"The record {record.untrimmed_video_name} {record.uid}, has less than 25 frames!")

        if(len(sampled_frames_inidices_list) < desired_num_frames):
            #DEBUG  
            # logger.info(f"{record.untrimmed_video_name} {record.uid}- record_num_frames: {record_num_frames}, clips_interval: {clips_interval}, frames_interval: {frames_interval}, frames: {sampled_frames_inidices_list}")
            raise SystemError(f"For the record {record.untrimmed_video_name} {record.uid}, the number of extracted frames is {len(sampled_frames_inidices_list)}, that is less than the desired {desired_num_frames} frames!")
        elif(len(sampled_frames_inidices_list) > desired_num_frames):
            #DEBUG  
            # logger.info(f"{record.untrimmed_video_name} {record.uid}- record_num_frames: {record_num_frames}, clips_interval: {clips_interval}, frames_interval: {frames_interval}, frames: {sampled_frames_inidices_list}")
            raise SystemError(f"For the record {record.untrimmed_video_name} {record.uid}, the number of extracted frames is {len(sampled_frames_inidices_list)}, that is more than the desired {desired_num_frames} frames!")
        else:
            #DEBUG
            #logger.info(f"{record.untrimmed_video_name} {record.uid} - record_num_frames: {record_num_frames}, sampled_frames_inidices_list: {sampled_frames_inidices_list}")
            return sampled_frames_inidices_list
  
    def _get_val_indices(self, record, modality):        
        record_num_frames = record.num_frames[modality]
        num_frames_per_clip = self.num_frames_per_clip[modality]
        desired_num_frames = num_frames_per_clip * self.num_clips
        sampled_frames_inidices_list = []

        if self.dense_sampling[modality]:
            ##* DENSE Sampling
            clip_radius = (num_frames_per_clip // 2)
            for clip_number in range(self.num_clips):
                    clip_central_point = np.random.randint(clip_radius, record_num_frames-clip_radius+2) # se record_num_frames=80 e cp=64 => sampled_frames_inidices_list=[48,..,64,..78], per questo il +2
                    clip_frames_inidices_list = list(range(clip_central_point-clip_radius, clip_central_point+clip_radius+1))
                    #*Se volessimo una lista di array numpy dove ogni array ha i frame di una clip
                    #clip_frames_indices_list = np.arange(clip_central_point-clip_radius, clip_central_point+clip_radius, frames_interval)
                    #sampled_frames_inidices_list.append(clip_frames_indices_list)
                    #*Caso di una lista piatta con solo indici
                    sampled_frames_inidices_list.extend(clip_frames_inidices_list[:num_frames_per_clip])
        else:
            ##* UNIFORM Sampling
            def uniform_sampling(clip_window):
                clip_radius = (clip_window // 2)
                frames_interval = clip_window//num_frames_per_clip

                for clip_number in range(self.num_clips):
                        clip_central_point = np.random.randint(clip_radius, record_num_frames-clip_radius+2)
                        clip_frames_inidices_list = list(range(clip_central_point-clip_radius, clip_central_point+clip_radius+1, frames_interval))
                        sampled_frames_inidices_list.extend(clip_frames_inidices_list[:num_frames_per_clip])
        
            if record_num_frames >= 75:
                uniform_sampling(75)    
            elif record_num_frames>=50:
                uniform_sampling(50)
            elif record_num_frames>=25:
                uniform_sampling(25)
            else:
                raise SystemError(f"The record {record.untrimmed_video_name} {record.uid}, has less than 25 frames!")

        if(len(sampled_frames_inidices_list) < desired_num_frames):
            #DEBUG  
            # logger.info(f"{record.untrimmed_video_name} {record.uid}- record_num_frames: {record_num_frames}, clips_interval: {clips_interval}, frames_interval: {frames_interval}, frames: {sampled_frames_inidices_list}")
            raise SystemError(f"For the record {record.untrimmed_video_name} {record.uid}, the number of extracted frames is {len(sampled_frames_inidices_list)}, that is less than the desired {desired_num_frames} frames!")
        elif(len(sampled_frames_inidices_list) > desired_num_frames):
            #DEBUG  
            # logger.info(f"{record.untrimmed_video_name} {record.uid}- record_num_frames: {record_num_frames}, clips_interval: {clips_interval}, frames_interval: {frames_interval}, frames: {sampled_frames_inidices_list}")
            raise SystemError(f"For the record {record.untrimmed_video_name} {record.uid}, the number of extracted frames is {len(sampled_frames_inidices_list)}, that is more than the desired {desired_num_frames} frames!")
        else:
            #DEBUG
            #logger.info(f"{record.untrimmed_video_name} {record.uid} - record_num_frames: {record_num_frames}, sampled_frames_inidices_list: {sampled_frames_inidices_list}")
            return sampled_frames_inidices_list

    def __getitem__(self, index):

        frames = {}
        label = None
        # record is a row of the pkl file containing one sample/action
        # notice that it is already converted into a EpicVideoRecord object so that here you can access
        # all the properties of the sample easily
        record = self.video_list[index]

        if self.load_feat:
            sample = {}
            sample_row = self.model_features[self.model_features["uid"] == int(record.uid)]
            assert len(sample_row) == 1
            for m in self.modalities:
                sample[m] = sample_row["features_" + m].values[0]
            if self.additional_info:
                return sample, record.label, record.untrimmed_video_name, record.uid
            else:
                return sample, record.label

        segment_indices = {}
        # notice that all indexes are sampled in the[0, sample_{num_frames}] range, then the start_index of the sample
        # is added as an offset
        for modality in self.modalities:
            if self.mode == "train":
                # here the training indexes are obtained with some randomization
                segment_indices[modality] = self._get_train_indices(record, modality)
            else:
                # here the testing indexes are obtained with no randomization, i.e., centered
                segment_indices[modality] = self._get_val_indices(record, modality)

        for m in self.modalities:
            img, label = self.get(m, record, segment_indices[m])
            frames[m] = img

        if self.additional_info:
            return frames, label, record.untrimmed_video_name, record.uid
        else:
            return frames, label

    def get(self, modality, record, indices):
        images = list()
        for frame_index in indices:
            p = int(frame_index)
            # here the frame is loaded in memory
            frame = self._load_data(modality, record, p)
            images.extend(frame)
        # finally, all the transformations are applied
        process_data = self.transform[modality](images)
        return process_data, record.label

    def _load_data(self, modality, record, idx):
        data_path = self.dataset_conf[modality].data_path
        tmpl = self.dataset_conf[modality].tmpl

        if modality == 'RGB' or modality == 'RGBDiff':
            # here the offset for the starting index of the sample is added

            idx_untrimmed = record.start_frame + idx    #start_frame decrementa di 1
            #logger.info(str(record.start_frame) + " - " + str(idx) + " - " + str(idx_untrimmed))
            try:
                img = Image.open(os.path.join(data_path, record.untrimmed_video_name, tmpl.format(idx_untrimmed))) \
                    .convert('RGB')
            except FileNotFoundError:
                print("Img not found")
                max_idx_video = int(sorted(glob.glob(os.path.join(data_path,
                                                                  record.untrimmed_video_name,
                                                                  "img_*")))[-1].split("_")[-1].split(".")[0])
                if idx_untrimmed > max_idx_video:
                    img = Image.open(os.path.join(data_path, record.untrimmed_video_name, tmpl.format(max_idx_video))) \
                        .convert('RGB')
                else:
                    raise FileNotFoundError
            return [img]
        
        else:
            raise NotImplementedError("Modality not implemented")

    def __len__(self):
        return len(self.video_list)


class ActionEMGDataset(data.Dataset, ABC):
    def __init__(self, split, mode, dataset_conf, additional_info=False):
        self.mode = mode  # 'train', 'val' or 'test'
        self.dataset_conf = dataset_conf
        self.stride = self.dataset_conf.stride
        self.additional_info = additional_info

        if self.mode == "train":
            pickle_name = "big_file" + "_train.pkl"
        else:
            pickle_name = "big_file" + "_test.pkl"

        self.list_file = pd.read_pickle(os.path.join(self.dataset_conf.annotations_path, pickle_name))
        #print(f"list-file: {self.list_file}")
        self.emg_list = [ActionEMGRecord(tup, self.dataset_conf) for tup in self.list_file["features"]]
        #print(f"mode: {self.mode}, len: {len(self.emg_list)}, [0]: {self.emg_list[0].label}")
        #exit()

    def _preprocess(self, reading):
        #* apply preprocessing to the EMG data
        # abs value
        x = np.abs(reading)
        #! low pass filter here
        # normalize the readings between -1 and 1 on the second axis
        reading = (x - np.min(x, axis=1)[:, None]) / (np.max(x, axis=1) - np.min(x, axis=1))[:, None] * 2 - 1
        # abs value
        reading = np.abs(reading)
        # sum the readings of the 8 channels
        reading = np.sum(reading, axis=1)

        return reading

    def __getitem__(self, index):
        # record is a row of the pkl file containing one sample/action
        # notice that it is already converted into a EpicVideoRecord object so that here you can access
        # all the properties of the sample easily
        record = self.emg_list[index]

        left_reading = self._preprocess(record.myo_left_readings)
        right_reading = self._preprocess(record.myo_right_readings)

        return record.label, left_reading, right_reading, record.id
    
    def __len__(self):
        return len(self.emg_list)
