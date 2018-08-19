# -*- coding: utf-8 -*-
"""
Created on Fri Aug 17 20:19:23 2018

@author: Allen
"""

import zipfile
import torch
import torchvision
import torch.nn as nn
import torch.nn.functional as F
from torch.utils import data
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils
from skimage import io, transform
from sklearn.model_selection import train_test_split
import numpy as np
import pandas as pd
import matplotlib.pyplot as ply
import os
import imageio
from PIL import Image
import glob
import matplotlib.pyplot as plt
import time
import math
import datetime as dt
import pytz
import pickle


if torch.cuda.is_available():
    dtype = torch.cuda.FloatTensor ## UNCOMMENT THIS LINE IF YOU'RE ON A GPU!
else:    
    dtype = torch.FloatTensor
    
    
class IOU_Loss(nn.Module):
    def __init__(self):
        super().__init__()
        
    def forward(self, y_pred, y):
        #print(y_pred.requires_grad)
        #y_pred = torch.where(y_pred.ge(0.5), torch.tensor(1.0), torch.tensor(0.0))
        i = y_pred.mul(y)
        u = (y_pred + y) - i
        mean_iou = torch.mean(i.view(i.shape[0],-1).sum(1) / u.view(i.shape[0],-1).sum(1))
        iou_loss = 1 - mean_iou
        #from boxx import g
        #g()
        
        return iou_loss
      

        
class Rescale(object):
    """Rescale the image in a sample to a given size.

    Args:
        output_size (int): Desired output size. 
    """

    def __init__(self, scale='random', min_scale=1, max_scale=3):
        self.scale = scale 
        self.min_scale = min_scale   
        self.max_scale = max_scale   

    def __call__(self, sample):
        image, mask = sample['image'], sample['mask']
        
        if self.scale == 'random':
            current_scale = np.clip((np.random.rand() * self.max_scale), self.min_scale, self.max_scale)
        else:
            current_scale = self.scale
      
        output_size = round(np.max(image.shape) * current_scale)        
        
        if mask is not None:
            image = np.concatenate([image,mask],2)
        resized_img = transform.resize(image, (output_size, output_size), mode='constant', preserve_range=True)
        #print(resized_img.shape)
        img_final = resized_img[:,:,0:1]
        if mask is not None:
            mask_final = resized_img[:,:,1:]

        return {'image':img_final, 'mask':mask_final}

class RandomCrop(object):
    """Crop randomly the image in a sample.

    Args:
        output_size (int): Desired output size. 
    """

    def __init__(self, output_size):
        assert isinstance(output_size, int)
        self.output_size = output_size

    def __call__(self, sample):
        image, mask = sample['image'], sample['mask']
        if mask is not None:
            image = np.concatenate([image,mask],2)

        h, w = image.shape[:2]

        new_h = new_w = self.output_size
        top = 0 if h == new_h else np.random.randint(0, h - new_h)
        left = 0 if w == new_w else np.random.randint(0, w - new_w)


        cropped_image = image[top: top + new_h,
                      left: left + new_w]
        
        img_final = cropped_image[:,:,0:1]
        if mask is not None:
            mask_final = cropped_image[:,:,1:]

        return {'image':img_final, 'mask':mask_final}

class Flip(object):
    """Crop randomly the image in a sample.

    Args:
        output_size (int): Desired output size. 
    """

    def __init__(self, orient='random'):
        assert orient in ['H', 'V', 'NA', 'random']
        self.orient = orient

    def __call__(self, sample):
        image, mask = sample['image'], sample['mask']
        if self.orient=='random':
            current_orient = np.random.choice(['H', 'W', 'NA', 'NA'])     
        else:
            current_orient = self.orient
        
        if mask is not None:
            image = np.concatenate([image,mask],2)

        if current_orient == 'H':
            flipped_image = image[:,::-1,:] - np.zeros_like(image)
        elif current_orient == 'W':
            flipped_image = image[::-1,:,:] - np.zeros_like(image)
        else:
            # do not flip if orient is NA
            flipped_image = image
        img_final = flipped_image[:,:,0:1]
        if mask is not None:
            mask_final = flipped_image[:,:,1:]

        return {'image':img_final, 'mask':mask_final}

'''composed = transforms.Compose([Rescale(scale='random', max_scale=5),
                               RandomCrop(101),
                               Flip(orient='random')])


transformed = composed({'image':image, 'mask':mask})
x_final, m_final = transformed['image'], transformed['mask']'''

class SaltDataset(Dataset):
    """Face Landmarks dataset."""

    def __init__(self, np_img, np_mask, df_depth, mean_img, img_out_size=101, transform=None):
        """
        Args:
            data_dir (string): Path to the image files.
            train (bool): Load train or test data
            transform (callable, optional): Optional transform to be applied
                on a sample.
        """
        self.np_img = np_img
        self.np_mask = np_mask.clip(0,1)
        self.df_depth = df_depth
        self.mean_img = mean_img
        self.img_out_size = img_out_size
        self.transform = transform

    def __len__(self):
        return len(self.np_img)

    def __getitem__(self, idx):

        X_orig = self.np_img[idx]
        X = X_orig - self.mean_img
        
        if self.np_mask is None:
            y = np.zeros((101,101,1))
        else:
            y = self.np_mask[idx]
            
        if self.transform:
            transformed = self.transform({'image':X, 'mask': y})
            X = transformed['image']
            y = transformed['mask']
            
        #print(X.dtype)
        X = np.moveaxis(X, -1,0)
        
        pad_size = self.img_out_size - self.np_img.shape[2]
        X = np.pad(X, [(0, 0),(0, pad_size), (0, pad_size)], mode='constant')
        #print(X.dtype)

        d = self.df_depth.iloc[idx,0]
        #id = self.df_depth.index[idx]
        from boxx import g
        g()
        X = torch.from_numpy(X).float().type(dtype)
        y = torch.from_numpy(y).float().squeeze().type(dtype)

        return (X,y,d,idx)
      


def load_all_data():
    try:
        print('Try loading data from npy and pickle files...')
        np_train_all = np.load('./data/np_train_all.npy')
        np_train_all_mask = np.load('./data/np_train_all_mask.npy')
        np_test = np.concatenate([np.load('./data/np_test_0.npy'), np.load('./data/np_test_1.npy')])
        with open('./data/misc_data.pickle', 'rb') as f:
            misc_data = pickle.load(f)
        print('Data loaded.')
        return (np_train_all, np_train_all_mask, np_test, misc_data)
    
    except:
        print('npy files not found. Reload data from raw images...')
        np_train_all, np_train_all_ids = load_img_to_np('./data/train/images')
        np_train_all_mask, np_train_all_mask_ids = load_img_to_np('./data/train/masks')
        df_train_all_depth = pd.read_csv('./data/depths.csv').set_index('id')
        np_test, np_test_ids = load_img_to_np('./data/test/images')
        np.save('./data/np_train_all.npy', np_train_all)
        np.save('./data/np_train_all_mask.npy', np_train_all_mask)
        for k, v in enumerate(np.split(np_test,2)):
            np.save(f'./data/np_test_{k}.npy', v)
        misc_data = {'df_train_all_depth': df_train_all_depth,
                     'np_train_all_ids': np_train_all_ids,
                     'np_train_all_mask_ids': np_train_all_mask_ids,
                     'np_test_ids': np_test_ids}
        with open('./data/misc_data.pickle', 'wb') as f:
            pickle.dump(misc_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        print('Data loaded.')
        return (np_train_all, np_train_all_mask, np_test, misc_data)
          
  
def rle_encoder2d(x):
    if isinstance(x, torch.Tensor):
        x = x.detach().numpy()
    s = pd.Series(x.clip(0,1).flatten('F'))
    s.index = s.index+1
    df = s.to_frame('pred').assign(zero_cumcnt=s.eq(0).cumsum())
    df = df.loc[df.pred.gt(0)]
    df_rle = df.reset_index().groupby('zero_cumcnt').agg({'index': min, 'pred': sum}).astype(int).astype(str)
    rle = ' '.join((df_rle['index'] + ' '+df_rle['pred']).tolist())
    
    return rle
  
  
def rle_encoder3d(x):   
    return np.r_[[rle_encoder2d(e) for e in x]]
  
  
def load_img_to_np(img_path, num_channel=1):
    images = []
    img_ids = []
    for filename in sorted(glob.glob(f'{img_path}/*.png')): #assuming png
        img_id = filename.split('\\')[-1].split('.')[0]
        img_ids.append(img_id)
        images.append(np.array(imageio.imread(filename), dtype=np.uint8).reshape(101,101,-1)[:,:,0:num_channel])
    return (np.r_[images], img_ids)
  
  
def load_single_img(path, show=False):
    img = np.array(imageio.imread(path), dtype=np.uint8)
    if show:
        plt.imshow(img, cmap='gray')
    return img
  
  
def calc_raw_iou(a, b):
    if isinstance(a, torch.Tensor):
        a = a.cpu().detach().numpy()
    if isinstance(b, torch.Tensor):
        b = b.cpu().detach().numpy()
    a = np.clip(a, 0, 1)
    b = np.clip(b, 0, 1)
    u = np.sum(np.clip(a+b, 0, 1), (1,2)).astype(np.float)
    i = np.sum(np.where((a+b)==2, 1, 0), (1,2)).astype(np.float)
    with np.errstate(divide='ignore',invalid='ignore'):
        iou = np.where(i==u, 1, np.where(u==0, 0, i/u))
        
    return iou
  
  
def calc_mean_iou(a, b):
    thresholds = np.array([0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95])
    iou = calc_raw_iou(a, b)
    iou_mean = (iou[:,None]>thresholds).mean(1).mean()

    return iou_mean
  
  
def timeSince(since):
    now = time.time()
    s = now - since
    m = math.floor(s / 60)
    s -= m * 60
    return '%dm %ds' % (m, s)
  
  
def get_current_time_as_fname():
        timestamp = (
                dt.datetime.now(pytz.timezone('Australia/Melbourne'))
                .strftime('%Y_%m_%d_%H_%M_%S')
                )
                
        return timestamp
      
      
def plot_img_mask_pred(image, mask, pred=None):
    if isinstance(image, torch.Tensor):
        image = image.detach().numpy()
    if isinstance(mask, torch.Tensor):
        mask = mask.detach().numpy()
    image = image.squeeze()
    mask = mask.squeeze()
    if pred is None:
        f, axarr = plt.subplots(1,2)
    else:
        f, axarr = plt.subplots(1,3)        
    axarr[0].imshow(image, cmap='gray')
    axarr[1].imshow(mask, cmap='gray')    
    axarr[0].grid()
    axarr[1].grid()    
    axarr[0].set_title('Image')
    axarr[1].set_title('Mask')
    if pred is not None:
        axarr[2].imshow(pred, cmap='gray')
        axarr[2].grid()
        axarr[2].set_title('Predicted Mask')
    plt.show()
    
    
def adjust_predictions(zero_mask_cut_off, X, y_pred, y=None):
    if isinstance(X, torch.Tensor):
        X = X.cpu().detach().numpy()
    if isinstance(y_pred, torch.Tensor):
        y_pred = y_pred.cpu().detach().numpy()
    if isinstance(y, torch.Tensor):
        y = y.cpu().detach().numpy()
    y_pred_adj = y_pred.clip(0,1)

    # Set predictions to all 0 for black images
    black_img_mask = (X.mean((1,2,3)) == 0)
    y_pred_adj[black_img_mask]=0

    # set all predictions to 0 if the number of positive predictions is less than ZERO_MASK_CUTOFF
    y_pred_adj = np.r_[[e if e.sum()>zero_mask_cut_off else np.zeros_like(e) for e in y_pred_adj]]
    
    if y is not None:
        print(f'IOU score before: {calc_mean_iou(y_pred, y)}, IOU Score after:{calc_mean_iou(y_pred_adj, y)}')
        
    return y_pred_adj
  
def show_img_grid():
    pass
    #plt.imshow(torchvision.utils.make_grid(torch.from_numpy(y_train_black).unsqueeze(1)).permute(1, 2, 0))