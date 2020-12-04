import math
import sys
import time
import torch

from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
import torchvision.models.detection.mask_rcnn

from pytorch_files.coco_utils import get_coco_api_from_dataset
from pytorch_files.coco_eval import CocoEvaluator
import pytorch_files.utils as utils
from math import floor, sqrt
from itertools import chain
import os

import torch
import os
import pickle
import sys

import torchvision
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

# errors are fine, importing local files in ./pytorch_files/
from pytorch_files.engine import train_one_epoch, evaluate
import pytorch_files.utils as utils
import PO3_dataset
import plot_losses


def floor_lists(boxes):
    result = []
    for box in boxes:
        result.append(list(map(lambda x: floor(float(x)), box)))
    return result


def calc_area(box):
    return (box[2]-box[0])*(box[3]-box[1])


def iou(box1, box2):
    iou_b = [max(box1[0], box2[0]),
             max(box1[1], box2[1]),
             min(box1[2], box2[2]),
             min(box1[3], box2[3])]
    if iou_b[2] < iou_b[0] or iou_b[3] < iou_b[1]:
        return 0
    iou_ar = calc_area(iou_b)
    return iou_ar / (calc_area(box1) + calc_area(box1) - iou_ar)


def adjusted_iou(box1, box2):
    iou_b = [max(box1[0], box2[0]),
           max(box1[1], box2[1]),
           min(box1[2], box2[2]),
           min(box1[3], box2[3])]
    if iou_b[2] < iou_b[0] or iou_b[3] < iou_b[1]:
        return 0
    iou_ar = calc_area(iou_b)
    return iou_ar / min(calc_area(box1), calc_area(box2))


def center_of_box(box):
    return (box[0] + box[2]) // 2, (box[1] + box[3]) // 2


def split_arrays(boxes, scores, labels):
    boxes_1, boxes_2, scores_1, scores_2 = [], [], [], []

    for i, label in enumerate(labels):
        if labels == 1:
            boxes_1.append(boxes[i])
            scores_1.append(scores[i])
        else:
            boxes_2.append(boxes[i])
            scores_2.append(scores[i])
    return boxes_1, scores_1, boxes_2, scores_2


def main_filter(boxes, scores):
    # vars
    score_distribution = dict()
    good_boxes, co = [], []
    filtered_score, filtered_iou = 0, 0

    # filter (+- same method as in Detector_new.py)
    for i, box in enumerate(boxes):
        rounded_score = round(scores[i], 3)
        score_distribution[rounded_score] = score_distribution.get(rounded_score, 0) + 1
        if scores[i] > 0.9:
            add_im = True
            j = 0
            run = True
            if len(good_boxes) == 0:
                run = False
            while run:
                if adjusted_iou(box, good_boxes[j]) > 0.8:
                    filtered_iou += 1
                    if calc_area(box) < calc_area(good_boxes[j]):
                        del good_boxes[j]
                        del co[j]
                        j -= 1
                    else:
                        add_im = False
                        break
                j += 1
                if len(good_boxes) == j:
                    run = False
            if add_im:
                good_boxes.append(box)
                co.append(center_of_box(box))
        else:
            filtered_score += 1
    return score_distribution, good_boxes, co, filtered_score, filtered_iou


def sum_score_distributions(score1, score2):
    for k, v in score2.items():
        score1[k] = score1.get(k, 0) + v
    return score1


def norm(co1, co2):
    return sqrt((co1[0]-co2[0])**2 + (co1[1]-co2[1])**2)


def pair_boxes(boxes_target, co_target, boxes_predicted, co_predicted):
    recognised, wrong = 0, 0
    paired_boxes = dict()
    for i, box in enumerate(boxes_target):
        paired_boxes[i] = [(box, co_target)]

    for i, co in enumerate(co_predicted):
        smallest_dist, smallest_id = float("inf"), -1
        for id, target in paired_boxes.items():
            dist = norm(target[0][1], co)
            if dist < smallest_dist:
                smallest_dist = dist
                smallest_id = id

        if len(paired_boxes[smallest_id]) == 1:
            if iou(paired_boxes[smallest_id][0][0], boxes_predicted[i]) > 0:
                recognised += 1
                paired_boxes[smallest_id] = [paired_boxes[smallest_id][0], (boxes_predicted[i], co), smallest_dist]
            else:
                wrong += 1
        else:
            wrong += 1
            if smallest_dist < paired_boxes[smallest_id][3]:
                paired_boxes[smallest_id] = [paired_boxes[smallest_id][0], (boxes_predicted[i], co), smallest_dist]

    all_ious, all_dists = [], []

    for paired in paired_boxes.values():
        if len(paired) > 1:
            all_ious.append(iou(paired[0][0], paired[1][0]))
            all_dists.append(paired[3])

    average_iou, average_dist = 0, 0
    if len(all_ious) > 0:
        average_iou = sum(all_ious)/len(all_ious)
        average_dist = sum(all_dists)/len(all_dists)

    return len(paired_boxes.keys()), recognised, wrong, average_iou, average_dist


def calc_score(targets, output):
    if len(output) != 1:
        raise Exception('More then 1 output. Custom evaluation requires just one output.')

    boxes, scores, labels = (floor_lists(output[0]["boxes"].tolist()),
                                output[0]["scores"].tolist(),
                                output[0]["labels"].tolist())

    heads, heads_score, masks, masks_score = split_arrays(boxes, scores, labels)

    score_distr_heads, good_heads, co_heads, f_score_heads, f_iou_heads = main_filter(heads, heads_score)
    score_distr_masks, good_masks, co_masks, f_score_masks, f_iou_masks = main_filter(masks, masks_score)

    # filtered_score = f_score_heads + f_score_masks
    # filtered_iou = f_iou_heads + f_iou_masks
    # score_distribution = sum_score_distributions(score_distr_heads, score_distr_masks)

    target_boxes, target_labels = floor_lists(targets[0]["boxes"].tolist()), targets[0]["labels"].tolist()

    target_coordinates = []
    for box in target_boxes:
        target_coordinates.append(center_of_box(box))

    target_heads, target_co_heads, target_masks, target_co_masks = [], [], [], []
    for i, label in enumerate(target_labels):
        if label == 1:
            target_heads.append(target_boxes[i])
            target_co_heads.append(target_coordinates[i])
        else:
            target_masks.append(target_heads[i])
            target_co_masks.append(target_coordinates[i])

    nb_heads, nb_recognized_heads, nb_incorrect_heads, matched_area_heads, dist_heads = \
        pair_boxes(target_heads, target_co_heads, good_heads, co_heads)

    nb_masks, nb_recognized_masks, nb_incorrect_masks, matched_area_masks, dist_masks = \
        pair_boxes(target_masks, target_co_masks, good_masks, co_masks)

    return [(score_distr_heads, f_score_heads, f_iou_heads, nb_heads, nb_recognized_heads, nb_incorrect_heads, matched_area_heads, dist_heads),
            (score_distr_masks, f_score_masks, f_iou_masks, nb_masks, nb_recognized_masks, nb_incorrect_masks, matched_area_masks, dist_masks)]

def main():
    path = "./saved_models/PO3_v4/"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        print('Evaluate on GPU.')
    else:
        print('Evaluate on CPU.')

    for file in os.listdir(path):

        full_path = os.path.join(path, file)

        # setup model
        model = torchvision.models.detection.fasterrcnn_resnet50_fpn()
        in_features = model.roi_heads.box_predictor.cls_score.in_features
        model.roi_heads.box_predictor = FastRCNNPredictor(in_features, 3)
        model.load_state_dict(torch.load(full_path))
        model.to(device)

        # evaluating
        model.eval()
        torch.no_grad()

        paths_testing = ('./adjusted_data/meer_pers_0/', './adjusted_data/meer_pers_1/')
        paths_generalisation = ('./adjusted_data/TA_0/', './adjusted_data/TA_1/')

        dataset_test = PO3_dataset.PO3Dataset(paths_testing, PO3_dataset.get_transform(train=False),
                                              has_sub_maps=False, ann_path="./adjusted_data/clean_ann_scaled.pckl")
        dataset_generalisation = PO3_dataset.PO3Dataset(paths_generalisation, PO3_dataset.get_transform(train=False),
                                                        has_sub_maps=False,
                                                        ann_path="./adjusted_data/clean_ann_scaled.pckl")


if __name__ == "__main__":
    main()
