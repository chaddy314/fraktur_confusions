import glob
import getpass
import diff_match_patch as dmp_module
import os
import sys
import multiprocessing
import argparse
import time
import ntpath
import re
from datetime import datetime

from typing import List


class Confusion:
    def __init__(self, gt, pred):
        self.gt = str(gt)
        self.pred = str(pred)
        self.gt_regex = re.compile('^' + self.gt + '+$')
        self.pred_regex = re.compile('^' + self.pred + '+$')

    def is_applicable(self, gt, pred):
        return self.gt_regex.search(gt) and self.pred_regex.search(pred)

    def to_string(self):
        return "{" + self.pred + "|" + self.gt + "}"


Confusions = List[Confusion]
confusionsFixed = 0


class Pair:
    def __init__(self, gt, gt_text, pred, pred_text, img):
        self.gt = gt
        self.gt_text = gt_text
        self.corrected_gt: str = gt_text
        self.pred = pred
        self.pred_text = pred_text
        self.img = img
        self.diff = list(list())
        self.has_confusion = False
        self.foundConfusions = []

    def calc_diff(self):
        global dmp
        dmp.Diff_Timeout = 0
        tmp = dmp.diff_main(str(self.corrected_gt), str(self.pred_text))
        self.diff = [(a[0], a[1]) for a in tmp]

    def correct_confusion(self, confusion):
        if len(self.diff) > 1:
            gt = ""
            i = 0
            while i < len(self.diff):
                if self.diff[i][0] == 0 or i == len(self.diff) - 1 or not self.same(self.diff[i], self.diff[i + 1]):
                    gt += self.diff[i][1]
                    #  print(gt)
                    i += 1
                elif confusion.is_applicable(self.diff[i][1], self.diff[i + 1][1]):
                    self.foundConfusions.append(confusion)
                    #  self.diff[i][1] = self.diff[i + 1][1]
                    gt += self.diff[i + 1][1]
                    global confusionsFixed
                    confusionsFixed += 1
                    #  print(gt)
                    self.has_confusion = True
                    i += 2
                else:
                    gt += self.diff[i][1]
                    #  print(gt)
                    i += 2
                #  print("i: " + str(i))
            self.corrected_gt = gt

    @staticmethod
    def same(list0, list1):
        return int(list0[0]) + int(list1[0]) == 0

    def correct_confusions(self, confusions: Confusions):
        self.calc_diff()
        if len(self.diff) > 1:
            for confusion in confusions:
                confusion: Confusion
                self.correct_confusion(confusion)
                self.calc_diff()
        #  print(stringify_tuple_list(self.diff))

    def patch_gt(self):
        gt = ""
        for tpl in self.diff:
            if tpl[0] <= 0:
                gt += tpl[1]
        self.corrected_gt = gt


gtList = []
predList = []
imgList = []
pairs = []
gtExt = ".gt.txt"
predExt = ".pred.ext"
imgExt = ".png"
oldGtExt = ".oldgt.txt"
path: str = ""
gt_dest: str = ""
pred_dest: str = ""
img_dest: str = ""
dmp = dmp_module.diff_match_patch()

multiThread = False
debug = False


def main():
    tic = time.perf_counter()
    parser = make_parser()
    parse(parser.parse_args())
    get_files()
    print("\npairing " + str(len(gtList)) + " gt files in " + path + "\n")
    pair_files()
    print("\nsuccessfully paired " + str(len(pairs)) + " gt files in " + path + "\n")
    confusions: Confusions = list()
    confusions.append(Confusion('s', 'ſ'))
    confusions.append(Confusion('-', '⸗'))
    confusions.append(Confusion('tz', 'ß'))

    if multiThread:
        pass  # do later
    else:
        for pair in pairs:
            pair.correct_confusions(confusions)
        for pair in pairs:
            if pair.has_confusion:
                print("\npath: " + pair.gt)
                print("  GT: " + pair.gt_text)
                print("pred: " + pair.pred_text)
                print("corr: " + pair.corrected_gt)
                found_confusion = ""
                for confusion in set(pair.foundConfusions):
                    found_confusion += " ".join(map(str, confusion.to_string())) + "  "
                print("Confusions found: " + found_confusion)
                # print("\n" + stringify_tuple_list(pair.diff) + "\n")

    print("\n Matched GT/Predictions:    " + str(len(pairs)))
    print("   Corrected Confusions:    " + str(confusionsFixed))
    toc = time.perf_counter()
    if multiThread:
        print(f"Finished matching in {toc - tic:0.4f} seconds using multiple threads")
    else:
        print(f"Finished matching in {toc - tic:0.4f} seconds using single thread")


def pair_files():
    global pairs

    for gt in gtList:
        name = strip_path(gt.split('.')[0])
        pred = path + name + predExt
        if not os.path.isfile(pred):
            continue
        img = [f for f in glob.glob(path + name + "*" + imgExt)][0]
        if not os.path.isfile(img):
            img = "undefined"
        pairs.append(Pair(gt, get_text(gt), pred, get_text(pred), img))


def get_files():
    global gtList
    gtList = [f for f in sorted(glob.glob(path + '*' + gtExt))]
    global predList
    predList = [f for f in sorted(glob.glob(path + '*' + predExt))]
    global imgList
    imgList = [f for f in sorted(glob.glob(path + '*' + predExt))]


def check_dest(destination, is_source=False):
    if not os.path.exists(destination) and not is_source:
        print(destination + "dir not found, creating directory")
        os.mkdir(destination)
    if not destination.endswith(os.path.sep):
        destination += os.path.sep
    return destination


def get_text(filename):
    with open(filename, 'r') as my_file:
        data = my_file.read().rstrip()
        return data


def strip_path(spath):
    return ntpath.basename(spath)


def parse(args):
    global debug
    debug = args.debug
    global path
    path = check_dest(args.path, True)
    global gtExt
    gtExt = args.gtExt
    global predExt
    predExt = args.predExt
    global imgExt
    imgExt = args.imgExt
    global gt_dest
    gt_dest = check_dest(args.gt_dest)
    global pred_dest
    pred_dest = check_dest(args.pred_dest)
    global img_dest
    img_dest = check_dest(args.img_dest)
    global multiThread
    multiThread = args.multiThread


def make_parser():
    parser = argparse.ArgumentParser(description='python script to solve confusions in fraktur script')
    parser.add_argument('-p',
                        '--path',
                        action='store',
                        dest='path',
                        default=os.getcwd(),
                        help='Path to GT and Prediction')

    parser.add_argument('--gt-ext',
                        action='store',
                        dest='gtExt',
                        default='.gt.txt',
                        help='gt extension')
    parser.add_argument('--pred-ext',
                        action='store',
                        dest='predExt',
                        default='.pred.txt',
                        help='pred extension')
    parser.add_argument('--img-ext',
                        action='store',
                        dest='imgExt',
                        default='.png',
                        help='image extension')

    parser.add_argument('--gt-folder',
                        action='store',
                        dest='gt_dest',
                        default=os.getcwd() + os.path.sep + 'gt' + os.path.sep,
                        help='Path to gt destination')
    parser.add_argument('--pred-folder',
                        action='store',
                        dest='pred_dest',
                        default=os.getcwd() + os.path.sep + 'predictions' + os.path.sep,
                        help='Path to prediction destination')
    parser.add_argument('--img-folder',
                        action='store',
                        dest='img_dest',
                        default=os.getcwd() + os.path.sep + 'images' + os.path.sep,
                        help='Path to image destination')

    parser.add_argument('--debug',
                        action='store_true',
                        dest='debug',
                        default=False,
                        help='debug mode')
    parser.add_argument('-f'
                        '--fast',
                        action='store_true',
                        dest='multiThread',
                        default=False,
                        help='use multiple threads (non interactive)')
    return parser


def stringify_tuple_list(plist):
    string = "["
    for ltuple in plist:
        string += "(" + str(ltuple[0]) + ", " + str(ltuple[1]) + "),\n"
    return string[:-2] + "]"


if __name__ == "__main__":
    main()
