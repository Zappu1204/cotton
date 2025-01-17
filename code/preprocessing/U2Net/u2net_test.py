import os
from skimage import io, transform
import torch
import torchvision
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms#, utils
# import torch.optim as optim

import numpy as np
from PIL import Image
import glob

# from data_loader import RescaleT
# from data_loader import ToTensor
# from data_loader import ToTensorLab
# from data_loader import SalObjDataset
from preprocessing.U2Net.data_loader import RescaleT, ToTensor, ToTensorLab, SalObjDataset

# from model import U2NET # full size version 173.6 MB
# from model import U2NETP # small version u2net 4.7 MB
from preprocessing.U2Net.model import U2NET, U2NETP
import argparse
from tqdm import tqdm
import cv2
import time

tensor_transform_woResize = transforms.Compose([  \
                            transforms.ToTensor(),   \
                            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])


# normalize the predicted SOD probability map
def normPRED(d):
    ma = torch.max(d)
    mi = torch.min(d)

    dn = (d-mi)/(ma-mi)

    return dn

def save_output(image_name,pred,d_dir):

    predict = pred
    predict = predict.squeeze()
    predict_np = predict.cpu().data.numpy()

    img_name = image_name.split(os.sep)[-1]
    image = io.imread(image_name)
    
    mask = (predict_np >= 0.5).astype(np.uint8) * 255
    mask = cv2.resize(mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)
    cv2.imwrite(os.path.join(d_dir,img_name.split('.')[0]+'.png'), mask)


def main(opt):
    file_path = os.path.abspath(__file__)
    code_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(file_path))))
    Data_path = os.path.join(code_path, 'Data')
    data_folder = os.path.join(Data_path, opt.root, opt.brand)
    # print("data_folder = ", data_folder)
    # --------- 1. get image path and name ---------
    model_name='u2net'#u2netp

    # cat_list = [opt.cat] if opt.cat is not None else [os.path.basename(cat) for cat in glob.glob(os.path.join(opt.root, opt.brand, '*'))]
    cat_list = [opt.cat] if opt.cat is not None else [os.path.basename(cat) for cat in glob.glob(os.path.join(data_folder, '*'))]
    print(cat_list)
    for cat in cat_list:
        print('='*10 + " {} -- {} ".format(opt.brand, cat) + "="*20)

        input_dir = os.path.join(data_folder, cat, 'product')
        output_dir = os.path.join(data_folder, cat, 'product-mask')
        model_dir = os.path.join('saved_models', model_name, model_name + '.pth')

        img_name_list = glob.glob(input_dir + os.sep + '*')

        # --------- 2. dataloader ---------
        #1. dataloader
        test_salobj_dataset = SalObjDataset(img_name_list = img_name_list,
                                            lbl_name_list = [],
                                            transform=transforms.Compose([RescaleT(320),
                                                                        ToTensorLab(flag=0)])
                                            )
        test_salobj_dataloader = DataLoader(test_salobj_dataset,
                                            batch_size=1,
                                            shuffle=False,
                                            num_workers=1)

        # --------- 3. model define ---------
        if(model_name=='u2net'):
            print("...load U2NET---173.6 MB")
            net = U2NET(3,1)
        elif(model_name=='u2netp'):
            print("...load U2NEP---4.7 MB")
            net = U2NETP(3,1)

        if torch.cuda.is_available():
            print("using GPU")
            net.load_state_dict(torch.load(model_dir))
            net.cuda()
        else:
            net.load_state_dict(torch.load(model_dir, map_location='cpu'))
        net.eval()

        # --------- 4. inference for each image ---------
        for i_test, data_test in tqdm(enumerate(test_salobj_dataloader), total=len(test_salobj_dataloader)):

            # print("\r inferencing:",img_name_list[i_test].split(os.sep)[-1], end=" ")

            inputs_test = data_test['image']
            inputs_test = inputs_test.type(torch.FloatTensor)

            if torch.cuda.is_available():
                inputs_test = Variable(inputs_test.cuda())
            else:
                inputs_test = Variable(inputs_test)

            d1,d2,d3,d4,d5,d6,d7= net(inputs_test)

            # normalization
            pred = d1[:,0,:,:]
            pred = normPRED(pred)

            # save results to test_results folder
            # print("output_dir = ", output_dir)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            save_output(img_name_list[i_test],pred,output_dir)

            del d1,d2,d3,d4,d5,d6,d7

def main():
    start = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand",
                        type=str,
                        default='Example_top')
    parser.add_argument("--cat",
                        type=str,
                        default=None)
    parser.add_argument("--root",
                        type=str,
                        default='parse_filtered_Data')          
    opt = parser.parse_args()
    main(opt)
    print("Product mask generation (U2Net) Time: {:.4f}".format(time.time() - start))

def u2net_test_py(brand):
    start = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand",
                        type=str,
                        default=brand)
    parser.add_argument("--cat",
                        type=str,
                        default=None)
    parser.add_argument("--root",
                        type=str,
                        default='parse_filtered_Data')          
    opt = parser.parse_args()
    main(opt)
    print("Product mask generation (U2Net) Time: {:.4f}".format(time.time() - start))

if __name__ == "__main__":
    main()