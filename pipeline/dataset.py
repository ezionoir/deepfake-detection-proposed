from torch.utils.data import Dataset
import os
import json
import cv2
import numpy as np
import torch
import albumentations as albu
from torchvision.transforms import ToTensor

class CustomDataset(Dataset):
    def __init__(self, ids: list, frames_path, labels_path, augmentation=False, sampling=None, img_size=224):
        self.ids = ids  # expected id = name_faceid
        self.frames_path = frames_path
        self.labels_path = labels_path
        self.sampling = sampling
        self.img_size = img_size

        self.labels = self.get_labels(labels_path=self.labels_path)

        if augmentation:
            self.aug = albu.Compose([
                # Resolution
                albu.ImageCompression(quality_lower=60, quality_upper=100, p=0.5),

                # (MUST) Shape
                albu.LongestMaxSize (max_size=self.img_size, interpolation=1, always_apply=True),
                albu.PadIfNeeded(min_height=self.img_size, min_width=self.img_size, border_mode=cv2.BORDER_CONSTANT, value=(0, 0, 0), always_apply=True),
                albu.Resize(height=self.img_size, width=self.img_size, always_apply=True),

                # RGB and blur
                albu.GaussNoise(p=0.1),
                albu.GaussianBlur(blur_limit=3, p=0.05),
                albu.RandomBrightnessContrast(p=0.7),
                albu.ToGray(p=0.2),

                # Geometry
                albu.HorizontalFlip(),
                albu.ShiftScaleRotate(shift_limit=(0.05, 0.05), scale_limit=(0.1, 0.1), rotate_limit=(5, 5), border_mode=cv2.BORDER_CONSTANT, p=0.5),
            ], additional_targets={'image0': 'image'}, is_check_shapes=False
            )
        else:
            self.aug = albu.Compose([
                albu.LongestMaxSize(max_size=self.img_size, interpolation=1, always_apply=True),
                albu.PadIfNeeded(min_height=self.img_size, min_width=self.img_size, border_mode=cv2.BORDER_CONSTANT, value=(0, 0, 0), always_apply=True),
                albu.Resize(height=self.img_size, width=self.img_size, always_apply=True),
            ], additional_targets={'image0': 'image'}, is_check_shapes=False
            )

    def __len__(self):
        return len(self.ids)
    
    def __getitem__(self, index):
        id = self.ids[index]
        video, face = id.split('_')
        folder_path = os.path.join(self.frames_path, video, face)

        frame_names = self.get_frame_names(folder_path=folder_path)

        item = []
        for group in frame_names:
            volume = []
            for frame_name in group:
                image = cv2.imread(os.path.join(folder_path, frame_name))
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                volume.append(image)

            transformed = self.aug(image=volume[0], image0=volume[1])
            volume = [transformed['image'], transformed['image0']]
            
            item.append(np.stack([transformed['image'], transformed['image0']]))

        sample = np.stack(item)

        return self.to_tensor(sample), self.labels[video], id

    def get_labels(self, labels_path):
        labels = {}
    
        for json_file in os.listdir(labels_path):
            with open(os.path.join(labels_path, json_file), 'r') as f:
                file_data = json.load(f)
                for name, details in file_data.items():
                    id = name.split('.')[0]
                    labels[id] = float(details["is_fake"])

        return labels
    
    def get_frame_names(self, folder_path):
        num_groups = self.sampling['num_groups']
        num_frames_per_group = self.sampling['group_size']
        file_names = os.listdir(folder_path)
        file_names = self.sort_files(file_names)
        total_frames = len(file_names)
        interval = (total_frames - num_frames_per_group) // num_groups
        frame_names = []

        for i in range(num_groups):
            group = []
            for j in range(num_frames_per_group):
                idx = i * interval + j
                # group.append(str(str(idx) + '.png'))
                group.append(file_names[idx])
            frame_names.append(group)

        return frame_names
    
    def sort_files(self, file_names):
        to_int = [int(x.split('.')[0]) for x in file_names]
        to_int.sort()
        return [str(x) + '.png' for x in to_int]
    
    def to_tensor(self, sample):
        transform = ToTensor()

        video_tensor = []
        for group in sample:
            group_tensor = []
            for frame in group:
                frame = transform(frame)
                group_tensor.append(frame)
            video_tensor.append(torch.stack(group_tensor, dim=0))

        return torch.stack(video_tensor, dim=0)
    
class CrossValidationDataset(Dataset):
    def __init__(self, frames_path, labels_path, augmentation=False, sampling=None, img_size=224):
        super().__init__()

        self.root_path = frames_path
        self.labels_path = labels_path
        self.ids = self.get_full_paths()
        self.labels = self.get_labels()

        self.img_size = img_size
        self.sampling = sampling

        if augmentation:
            self.aug = albu.Compose([
                # Resolution
                albu.ImageCompression(quality_lower=60, quality_upper=100, p=0.5),

                # (MUST) Shape
                albu.LongestMaxSize (max_size=self.img_size, interpolation=1, always_apply=True),
                albu.PadIfNeeded(min_height=self.img_size, min_width=self.img_size, border_mode=cv2.BORDER_CONSTANT, value=(0, 0, 0), always_apply=True),
                albu.Resize(height=self.img_size, width=self.img_size, always_apply=True),

                # RGB and blur
                albu.GaussNoise(p=0.1),
                albu.GaussianBlur(blur_limit=3, p=0.05),
                albu.RandomBrightnessContrast(p=0.7),
                albu.ToGray(p=0.2),

                # Geometry
                albu.HorizontalFlip(),
                albu.ShiftScaleRotate(shift_limit=(0.05, 0.05), scale_limit=(0.1, 0.1), rotate_limit=(5, 5), border_mode=cv2.BORDER_CONSTANT, p=0.5),
            ], additional_targets={'image0': 'image'}, is_check_shapes=False
            )
        else:
            self.aug = albu.Compose([
                albu.LongestMaxSize(max_size=self.img_size, interpolation=1, always_apply=True),
                albu.PadIfNeeded(min_height=self.img_size, min_width=self.img_size, border_mode=cv2.BORDER_CONSTANT, value=(0, 0, 0), always_apply=True),
                albu.Resize(height=self.img_size, width=self.img_size, always_apply=True),
            ], additional_targets={'image0': 'image'}, is_check_shapes=False
            )

    def get_full_paths(self):
        ids = []
        dirs = [os.path.join(self.root_path, 'training'), os.path.join(self.root_path, 'validation')]

        for dir in dirs:
            for video in os.listdir(dir):
                for face in os.listdir(os.path.join(dir, video)):
                    if face == '0' and len(os.listdir(os.path.join(dir, video, face))) >= 24:
                        ids.append(os.path.join(dir, video, face))

        return ids

    def get_labels(self):
        labels = {}

        dirs = [
            os.path.join(self.labels_path, 'training'),
            os.path.join(self.labels_path, 'validation')
        ]

        for dir in dirs:
            for json_file in os.listdir(dir):
                with open(os.path.join(dir, json_file), 'r') as f:
                    file_data = json.load(f)
                    for name, details in file_data.items():
                        id = name.split('.')[0]
                        labels[id] = float(details['is_fake'])

        return labels
    
        # for json_file in os.listdir(labels_path):
        #     with open(os.path.join(labels_path, json_file), 'r') as f:
        #         file_data = json.load(f)
        #         for name, details in file_data.items():
        #             id = name.split('.')[0]
        #             labels[id] = float(details["is_fake"])

        # return labels

    def __len__(self):
        return len(self.ids)
    
    
    def get_ids (self):
        return self.ids
    
    def __getitem__(self, idx):
        id = self.ids[idx]

        frame_names = self.get_frame_names(folder_path=id)

        item = []
        for group in frame_names:
            volume = []
            for frame_name in group:
                image = cv2.imread(os.path.join(id, frame_name))
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                volume.append(image)

            transformed = self.aug(image=volume[0], image0=volume[1])
            volume = [transformed['image'], transformed['image0']]
            
            item.append(np.stack([transformed['image'], transformed['image0']]))

        sample = np.stack(item)

        return self.to_tensor(sample), self.labels[os.path.basename(id)], id
    
    def get_frame_names(self, folder_path):
        num_groups = self.sampling['num_groups']
        num_frames_per_group = self.sampling['group_size']
        file_names = os.listdir(folder_path)
        file_names = self.sort_files(file_names)
        total_frames = len(file_names)
        interval = (total_frames - num_frames_per_group) // num_groups
        frame_names = []

        for i in range(num_groups):
            group = []
            for j in range(num_frames_per_group):
                idx = i * interval + j
                group.append(file_names[idx])
            frame_names.append(group)

        return frame_names

    def sort_files(self, file_names):
        to_int = [int(x.split('.')[0]) for x in file_names]
        to_int.sort()
        return [str(x) + '.png' for x in to_int]
    
    def to_tensor(self, sample):
        transform = ToTensor()

        video_tensor = []
        for group in sample:
            group_tensor = []
            for frame in group:
                frame = transform(frame)
                group_tensor.append(frame)
            video_tensor.append(torch.stack(group_tensor, dim=0))

        return torch.stack(video_tensor, dim=0)