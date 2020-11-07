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
    def __init__(self, gt, pred, is_primary):
        self.gt = str(gt)
        self.pred = str(pred)
        if len(self.gt) > 0 and len(self.pred) > 0:
            self.gt_regex = re.compile('^' + re.escape(self.gt) + '+$')
            self.pred_regex = re.compile('^' + re.escape(self.pred) + '+$')
        self.is_primary = is_primary

    def is_applicable(self, gt, pred):
        return self.gt_regex.search(gt) and self.pred_regex.search(pred)

    #  untested
    def get_type(self):
        #  returns 0 if deletion and insertion
        if len(self.gt) > 0 and len(self.pred) > 0:
            return 0
        #  returns -1 if only deletion
        elif len(self.gt) > 0 and len(self.pred) == 0:
            self.is_primary = False
            return -1
        # returns 1 if only insertion
        elif len(self.gt) == 0 and len(self.pred) > 0:
            self.is_primary = False
            return 1
        else:
            print("could not get type of confusion {" + self.gt + "} -> {" + self.pred + "}")

    def to_string(self):
        return "{" + self.pred + "} -> {" + self.gt + "}"


Confusions = List[Confusion]
confusionsFixed = 0
confusionsFound = 0


class Pair:
    def __init__(self, gt, gt_text, pred, pred_text, img):
        self.gt = gt
        self.gt_text = gt_text
        self.corrected_gt: str = gt_text
        self.pred = pred
        self.pred_text = pred_text
        self.img = img
        self.diff = list(list())
        self.has_primary_confusion = False
        self.has_secondary_confusion = False
        self.foundConfusions = []

    def calc_diff(self):
        global dmp
        dmp.Diff_Timeout = 0
        tmp = dmp.diff_main(str(self.corrected_gt), str(self.pred_text))
        self.diff = [(a[0], a[1]) for a in tmp]

    def correct_confusion(self, confusion):
        if len(self.diff) > 1 and confusion.get_type() == 0:
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
                    global confusionsFound
                    confusionsFound += 1
                    confusionsFixed += 1
                    #  print(gt)
                    self.has_primary_confusion = True
                    i += 2
                else:
                    gt += self.diff[i][1]
                    #  print(gt)
                    i += 2
                #  print("i: " + str(i))
            self.corrected_gt = gt
        elif not confusion.get_type() == 0:
            print("Not able to correct " + confusion.to_string() + " as of yet.")

    @staticmethod
    def same(list0, list1):
        return int(list0[0]) + int(list1[0]) == 0

    def process_confusions(self, confusions: Confusions):
        self.calc_diff()
        if len(self.diff) > 1:
            primary_confusions = [x for x in confusions if x.is_primary]
            for confusion in primary_confusions:
                confusion: Confusion
                self.correct_confusion(confusion)
                self.calc_diff()
            #  untested
            secondary_confusions = [x for x in confusions if not x.is_primary]
            for confusion in secondary_confusions:
                confusion: Confusion
                self.mark_secondary(confusion)
        #  print(stringify_tuple_list(self.diff))

    #  untested
    def mark_secondary(self, confusion):
        if len(self.diff) > 1:
            global confusionsFound
            if confusion.get_type() == 0:
                i = 0
                while i < len(self.diff):
                    if self.diff[i][0] == 0 or i == len(self.diff) - 1 or not self.same(self.diff[i], self.diff[i + 1]):
                        i += 1
                    elif confusion.is_applicable(self.diff[i][1], self.diff[i + 1][1]):
                        self.foundConfusions.append(confusion)
                        confusionsFound += 1
                        self.has_secondary_confusion = True
                        i += 2
                    else:
                        i += 2
            else:
                i = 0
                while i < len(self.diff):
                    if i < len(self.diff) - 1:
                        if self.same(self.diff[i], self.diff[i + 1]):
                            i += 2
                        elif self.diff[i][0] != confusion.get_type():
                            i += 1
                        elif self.diff[i][0] == confusion.get_type():
                            if (confusion.get_type() == -1 and self.diff[i][1] == confusion.gt)\
                                    or (confusion.get_type() == 1 and self.diff[i][1] == confusion.pred):
                                self.foundConfusions.append(confusion)
                                confusionsFound += 1
                                self.has_secondary_confusion = True
                            i += 1
                    else:
                        if self.diff[i][0] != confusion.get_type():
                            i += 1
                        elif self.diff[i][0] == confusion.get_type():
                            if (confusion.get_type() == -1 and self.diff[i][1] == confusion.gt) \
                                    or (confusion.get_type() == 1 and self.diff[i][1] == confusion.pred):
                                self.foundConfusions.append(confusion)
                                confusionsFound += 1
                                self.has_secondary_confusion = True
                            i += 1
                        else:
                            print("Something went wrong in type -1 confusion " + confusion.to_string())

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
verbose = False
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
    confusions.append(Confusion('s', 'ſ', True))
    confusions.append(Confusion('-', '⸗', True))
    confusions.append(Confusion('tz', 'ß', True))

    confusions.append(Confusion('"', '“', False))
    confusions.append(Confusion('"', '”', False))
    confusions.append(Confusion(",", "'", False))
    #  difficult
    confusions.append(Confusion("\"", "", False))
    confusions.append(Confusion("", "ͤ", False))

    if multiThread:
        pass  # do later
    else:
        for pair in pairs:
            pair.process_confusions(confusions)
        if verbose:
            for pair in pairs:
                if pair.has_primary_confusion:
                    print("\npath: " + pair.gt)
                    print("  GT: " + pair.gt_text)
                    print("pred: " + pair.pred_text)
                    print("corr: " + pair.corrected_gt)
                    found_confusion = ""
                    for confusion in set(pair.foundConfusions):
                        found_confusion += " ".join(map(str, confusion.to_string())) + "  "
                    print("Confusions found: " + found_confusion)
                    # print("\n" + stringify_tuple_list(pair.diff) + "\n")
                if pair.has_secondary_confusion:
                    print("\npath: " + pair.gt)
                    print("  GT: " + pair.gt_text)
                    print("pred: " + pair.pred_text)
                    found_confusion = ""
                    for confusion in set(pair.foundConfusions):
                        found_confusion += " ".join(map(str, confusion.to_string())) + "  "
                    print("Confusions found: " + found_confusion)

    print("\n Matched GT/Predictions:    " + str(len(pairs)))
    print("       Found Confusions:    " + str(confusionsFound))
    print("   Corrected Confusions:    " + str(confusionsFixed))
    toc = time.perf_counter()
    if multiThread:
        print(f"Finished matching in {toc - tic:0.4f} seconds using multiple threads")
    else:
        print(f"Finished matching in {toc - tic:0.4f} seconds using single thread")


def pair_files():
    global pairs

    for gt in gtList:
        gt_path = ntpath.dirname(gt)
        name = strip_path(gt.split('.')[0])
        pred = path + name + predExt
        if not os.path.isfile(pred):
            continue
        img = [f for f in glob.glob(gt_path + os.path.sep + name + "*" + imgExt)][0]
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
    global verbose
    verbose = args.verbose
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
                        help='use multiple threads')
    parser.add_argument('-v'
                        '--verbose',
                        action='store_true',
                        dest='verbose',
                        default=False,
                        help='output every change')
    return parser


def stringify_tuple_list(plist):
    string = "["
    for ltuple in plist:
        string += "(" + str(ltuple[0]) + ", " + str(ltuple[1]) + "),\n"
    return string[:-2] + "]"


if __name__ == "__main__":
    main()
