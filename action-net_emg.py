from datetime import datetime
from statistics import mean
from utils.logger import logger
import torch.nn.parallel
import torch.optim
import torch
from utils.loaders import ActionEMGRecord
from utils.args import args
from utils.utils import pformat_dict
import utils
import numpy as np
import os
import models as model_list
import tasks
import wandb

# global variables among training functions
training_iterations = 0
modalities = None
np.random.seed(13696641)
torch.manual_seed(13696641)


def init_operations():
    """
    parse all the arguments, generate the logger, check gpus to be used and wandb
    """
    logger.info("Running with parameters: " + pformat_dict(args, indent=1))

    # this is needed for multi-GPUs systems where you just want to use a predefined set of GPUs
    if args.gpus is not None:
        logger.debug('Using only these GPUs: {}'.format(args.gpus))
        os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpus)

    # wanbd logging configuration
    if args.wandb_name is not None:
        wandb.init(group=args.wandb_name, dir=args.wandb_dir)
        wandb.run.name = args.name + "_" + args.shift.split("-")[0] + "_" + args.shift.split("-")[-1]


def main():

    train_loader = torch.utils.data.DataLoader(ActionEMGRecord(args.dataset.shift.split("-")[0],
                                                                    'train', args.dataset),
                                                batch_size=args.batch_size, shuffle=True,
                                                num_workers=args.dataset.workers, pin_memory=True, drop_last=True)
    
    for i_val, (label, left, right, id) in enumerate(train_loader):
        print(label, left, right, id)



def train(action_classifier, train_loader, val_loader, device, num_classes):
    return


def validate(model, val_loader, device, it, num_classes):
   return 


if __name__ == '__main__':
    main()
