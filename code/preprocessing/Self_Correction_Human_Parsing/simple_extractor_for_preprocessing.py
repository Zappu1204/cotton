#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
@Author  :   Peike Li
@Contact :   peike.li@yahoo.com
@File    :   simple_extractor.py
@Time    :   8/30/19 8:59 PM
@Desc    :   Simple Extractor
@License :   This source code is licensed under the license found in the
             LICENSE file in the root directory of this source tree.
"""

import os
import torch
import argparse
import numpy as np
from PIL import Image
from tqdm import tqdm

from torch.utils.data import DataLoader
import torchvision.transforms as transforms

# import networks
# from utils.transforms import transform_logits
# from datasets.simple_extractor_dataset import SimpleFolderDataset
from preprocessing.Self_Correction_Human_Parsing import networks
from preprocessing.Self_Correction_Human_Parsing.utils.transforms import transform_logits
from preprocessing.Self_Correction_Human_Parsing.datasets.simple_extractor_dataset import SimpleFolderDataset
import glob

dataset_settings = {
    'lip': {
        'input_size': [473, 473],
        'num_classes': 20,
        'label': ['Background', 'Hat', 'Hair', 'Glove', 'Sunglasses', 'Upper-clothes', 'Dress', 'Coat',
                  'Socks', 'Pants', 'Jumpsuits', 'Scarf', 'Skirt', 'Face', 'Left-arm', 'Right-arm',
                  'Left-leg', 'Right-leg', 'Left-shoe', 'Right-shoe']
    },
    'atr': {
        'input_size': [512, 512],
        'num_classes': 18,
        'label': ['Background', 'Hat', 'Hair', 'Sunglasses', 'Upper-clothes', 'Skirt', 'Pants', 'Dress', 'Belt',
                  'Left-shoe', 'Right-shoe', 'Face', 'Left-leg', 'Right-leg', 'Left-arm', 'Right-arm', 'Bag', 'Scarf']
    },
    'pascal': {
        'input_size': [512, 512],
        'num_classes': 7,
        'label': ['Background', 'Head', 'Torso', 'Upper Arms', 'Lower Arms', 'Upper Legs', 'Lower Legs'],
    }
}


def get_arguments():
    """Parse all the arguments provided from the CLI.
    Returns:
      A list of parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Self Correction for Human Parsing")

    parser.add_argument("--dataset", type=str, default='lip', choices=['lip', 'atr', 'pascal'])
    parser.add_argument("--model-restore", type=str, default='', help="restore pretrained model parameters.")
    parser.add_argument("--gpu", type=str, default='0', help="choose gpu device.")
    parser.add_argument("--input-dir", type=str, default='', help="path of input image folder.")
    parser.add_argument("--output-dir", type=str, default='', help="path of output image folder.")
    parser.add_argument("--logits", action='store_true', default=False, help="whether to save the logits.")
    parser.add_argument("--brand",
                        type=str,
                        default='Example_top')
    parser.add_argument("--cat",
                        type=str,
                        default=None)
    parser.add_argument("--root",
                        type=str,
                        default='parse_filtered_Data')    
    return parser.parse_args()


def get_palette(num_cls):
    """ Returns the color map for visualizing the segmentation mask.
    Args:
        num_cls: Number of classes
    Returns:
        The color map
    """
    n = num_cls
    palette = [0] * (n * 3)
    for j in range(0, n):
        lab = j
        palette[j * 3 + 0] = 0
        palette[j * 3 + 1] = 0
        palette[j * 3 + 2] = 0
        i = 0
        while lab:
            palette[j * 3 + 0] |= (((lab >> 0) & 1) << (7 - i))
            palette[j * 3 + 1] |= (((lab >> 1) & 1) << (7 - i))
            palette[j * 3 + 2] |= (((lab >> 2) & 1) << (7 - i))
            i += 1
            lab >>= 3
    return palette


def main():
    import time
    start_time = time.time()
    args = get_arguments()

    gpus = [int(i) for i in args.gpu.split(',')]
    assert len(gpus) == 1
    if not args.gpu == 'None':
        os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

    num_classes = dataset_settings[args.dataset]['num_classes']
    input_size = dataset_settings[args.dataset]['input_size']
    label = dataset_settings[args.dataset]['label']
    print("Evaluating total class number {} with {}".format(num_classes, label))

    model = networks.init_model('resnet101', num_classes=num_classes, pretrained=None)

    state_dict = torch.load(args.model_restore)['state_dict']
    from collections import OrderedDict
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = k[7:]  # remove `module.`
        new_state_dict[name] = v
    model.load_state_dict(new_state_dict)
    model.cuda()
    model.eval()

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.406, 0.456, 0.485], std=[0.225, 0.224, 0.229])
    ])

    file_path = os.path.abspath(__file__)
    code_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(file_path))))
    Data_path = os.path.join(code_path, 'Data')
    data_folder = os.path.join(Data_path, args.root, args.brand)

    # data_folder = os.path.join(args.root, args.brand)
    cats = glob.glob(os.path.join(data_folder, '*'))

    for cat in cats:
        cat = os.path.basename(cat)
        print(cat)
        dataset = SimpleFolderDataset(root=os.path.join(data_folder, cat, 'model'), input_size=input_size, transform=transform)
        dataloader = DataLoader(dataset)
        args.output_dir = os.path.join(data_folder, cat, 'ATR')

        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)
        vis_dir = os.path.join(args.output_dir, 'vis')
        os.makedirs(vis_dir, exist_ok=True)

        palette = get_palette(num_classes)
        with torch.no_grad():
            for idx, batch in enumerate(tqdm(dataloader)):
                image, meta = batch
                img_name = meta['name'][0]
                c = meta['center'].numpy()[0]
                s = meta['scale'].numpy()[0]
                w = meta['width'].numpy()[0]
                h = meta['height'].numpy()[0]

                output = model(image.cuda())
                upsample = torch.nn.Upsample(size=input_size, mode='bilinear', align_corners=True)
                upsample_output = upsample(output[0][-1][0].unsqueeze(0))
                upsample_output = upsample_output.squeeze()
                upsample_output = upsample_output.permute(1, 2, 0)  # CHW -> HWC

                logits_result = transform_logits(upsample_output.data.cpu().numpy(), c, s, w, h, input_size=input_size)
                parsing_result = np.argmax(logits_result, axis=2)
                parsing_result_path = os.path.join(args.output_dir, img_name[:-4] + '.png')
                output_img = Image.fromarray(np.asarray(parsing_result, dtype=np.uint8))
                output_img.save(parsing_result_path)
                vis_result_path = os.path.join(vis_dir, img_name[:-4] + '.png')
                output_img.putpalette(palette)
                output_img.save(vis_result_path)
                if args.logits:
                    logits_result_path = os.path.join(args.output_dir, img_name[:-4] + '.npy')
                    np.save(logits_result_path, logits_result)
    print('Self Correction Human Parsing time: {:.4f}'.format(time.time() - start_time))
    return

def simple_extractor_for_preprocessing_py(argdataset, model_restore, brand):
    import time
    start_time = time.time()
    args = get_arguments()
    args.dataset = argdataset
    args.model_restore = model_restore
    args.brand = brand

    gpus = [int(i) for i in args.gpu.split(',')]
    assert len(gpus) == 1
    if not args.gpu == 'None':
        os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

    num_classes = dataset_settings[args.dataset]['num_classes']
    input_size = dataset_settings[args.dataset]['input_size']
    label = dataset_settings[args.dataset]['label']
    print("Evaluating total class number {} with {}".format(num_classes, label))

    model = networks.init_model('resnet101', num_classes=num_classes, pretrained=None)

    state_dict = torch.load(args.model_restore)['state_dict']
    from collections import OrderedDict
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = k[7:]  # remove `module.`
        new_state_dict[name] = v
    model.load_state_dict(new_state_dict)
    model.cuda()
    model.eval()

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.406, 0.456, 0.485], std=[0.225, 0.224, 0.229])
    ])

    file_path = os.path.abspath(__file__)
    code_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(file_path))))
    Data_path = os.path.join(code_path, 'Data')
    data_folder = os.path.join(Data_path, args.root, args.brand)

    # data_folder = os.path.join(args.root, args.brand)
    cats = glob.glob(os.path.join(data_folder, '*'))

    for cat in cats:
        cat = os.path.basename(cat)
        print(cat)
        dataset = SimpleFolderDataset(root=os.path.join(data_folder, cat, 'model'), input_size=input_size, transform=transform)
        dataloader = DataLoader(dataset)
        args.output_dir = os.path.join(data_folder, cat, 'ATR')

        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)
        vis_dir = os.path.join(args.output_dir, 'vis')
        os.makedirs(vis_dir, exist_ok=True)

        palette = get_palette(num_classes)
        with torch.no_grad():
            for idx, batch in enumerate(tqdm(dataloader)):
                image, meta = batch
                img_name = meta['name'][0]
                c = meta['center'].numpy()[0]
                s = meta['scale'].numpy()[0]
                w = meta['width'].numpy()[0]
                h = meta['height'].numpy()[0]

                output = model(image.cuda())
                upsample = torch.nn.Upsample(size=input_size, mode='bilinear', align_corners=True)
                upsample_output = upsample(output[0][-1][0].unsqueeze(0))
                upsample_output = upsample_output.squeeze()
                upsample_output = upsample_output.permute(1, 2, 0)  # CHW -> HWC

                logits_result = transform_logits(upsample_output.data.cpu().numpy(), c, s, w, h, input_size=input_size)
                parsing_result = np.argmax(logits_result, axis=2)
                parsing_result_path = os.path.join(args.output_dir, img_name[:-4] + '.png')
                output_img = Image.fromarray(np.asarray(parsing_result, dtype=np.uint8))
                output_img.save(parsing_result_path)
                vis_result_path = os.path.join(vis_dir, img_name[:-4] + '.png')
                output_img.putpalette(palette)
                output_img.save(vis_result_path)
                if args.logits:
                    logits_result_path = os.path.join(args.output_dir, img_name[:-4] + '.npy')
                    np.save(logits_result_path, logits_result)
    print('Self Correction Human Parsing time: {:.4f}'.format(time.time() - start_time))
    return

if __name__ == '__main__':
    main()