import glob
import diff_match_patch as dmp_module
import os
import shutil
import sys
import multiprocessing
import argparse
import time
import ntpath
import re
import xml.etree.ElementTree as ET

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
        return "{" + self.pred + "}->{" + self.gt + "}"


Confusions = List[Confusion]


class Pair:
    def __init__(self, gt, gt_text, pred, pred_text, img):
        self.gt = gt
        self.gt_text = gt_text
        self.old_gt: str = gt_text
        self.pred = pred
        self.pred_text = pred_text
        self.img = img
        self.diff = list(list())
        self.primary_confusions = 0
        self.secondary_confusions = 0
        self.foundConfusions = []

    def calc_diff(self):
        dmp = dmp_module.diff_match_patch()
        dmp.Diff_Timeout = 0
        tmp = dmp.diff_main(str(self.gt_text), str(self.pred_text))
        self.diff = [(a[0], a[1]) for a in tmp]

    def correct_confusion(self, confusion):
        if len(self.diff) > 1 and confusion.get_type() == 0:
            gt = ""
            i = 0
            while i < len(self.diff):
                if self.diff[i][0] == 0 or i == len(self.diff) - 1 or not self.same(self.diff[i], self.diff[i + 1]):
                    gt += self.diff[i][1]
                    i += 1
                elif confusion.is_applicable(self.diff[i][1], self.diff[i + 1][1]):
                    self.foundConfusions.append(confusion)
                    gt += self.diff[i + 1][1]
                    self.primary_confusions += 1
                    i += 2
                else:
                    gt += self.diff[i][1]
                    i += 2
            self.gt_text = gt
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
            secondary_confusions = [x for x in confusions if not x.is_primary]
            for confusion in secondary_confusions:
                confusion: Confusion
                self.mark_secondary(confusion)
        return self

    def mark_secondary(self, confusion):
        if len(self.diff) > 1:
            if confusion.get_type() == 0:
                i = 0
                while i < len(self.diff):
                    if self.diff[i][0] == 0 or i == len(self.diff) - 1 or not self.same(self.diff[i], self.diff[i + 1]):
                        i += 1
                    elif confusion.is_applicable(self.diff[i][1], self.diff[i + 1][1]):
                        self.foundConfusions.append(confusion)
                        self.secondary_confusions += 1
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
                            if (confusion.get_type() == -1 and self.diff[i][1] == confusion.gt) \
                                    or (confusion.get_type() == 1 and self.diff[i][1] == confusion.pred):
                                self.foundConfusions.append(confusion)
                                self.secondary_confusions += 1
                            i += 1
                    else:
                        if self.diff[i][0] != confusion.get_type():
                            i += 1
                        elif self.diff[i][0] == confusion.get_type():
                            if (confusion.get_type() == -1 and self.diff[i][1] == confusion.gt) \
                                    or (confusion.get_type() == 1 and self.diff[i][1] == confusion.pred):
                                self.foundConfusions.append(confusion)
                                self.secondary_confusions += 1
                            i += 1
                        else:
                            print("Something went wrong in type -1 confusion " + confusion.to_string())


gtList = []
xmlList = []
predList = []
imgList = []
gtExt = ".gt.txt"
predExt = ".pred.ext"
imgExt = ".png"
oldGtExt = ".oldgt.txt"
path: str = ""
dest: str = ""

safe_mode = True
supersafe_mode = False
multiThread = False
verbose = False
debug = False
cutoff = 3.5
ct_path = ""


def main():
    tic = time.perf_counter()
    parser = make_parser()
    parse(parser.parse_args())
    get_files()
    print("\nFound " + str(len(gtList)) + " gt files in " + path + "\n")
    pairs = pair_files()
    confusions: Confusions = list()
    if ct_path == "":
        print("\nUsing default Confusions (Corrects if True):")
        confusions.append(Confusion('s', 'ſ', True))
        confusions.append(Confusion('-', '⸗', True))
        confusions.append(Confusion('tz', 'ß', True))

        confusions.append(Confusion('"', '“', False))
        confusions.append(Confusion('"', '”', False))
        confusions.append(Confusion(",", "'", False))
        confusions.append(Confusion("\"", "", False))
        confusions.append(Confusion("", "ͤ", False))
        for confusion in confusions:
            print(confusion.to_string() + "  " + str(confusion.is_primary))
    else:
        confusions = parse_ct(ct_path, cutoff)

    i = 0
    if multiThread:
        processes = []
        queue = multiprocessing.Queue()
        for pair in pairs:
            progress(i + 1, len(pairs), "Starting process " + str(i + 1) + " of " + str(len(pairs)))
            send = list()
            send.append(pair)
            send.append(confusions.copy())
            queue.put(send)
            process = multiprocessing.Process(target=do_mt_conf, args=(queue,))
            processes.append(process)
            process.start()
            i += 1
        processed_pairs = []
        for process in processes:
            progress(i + 1, len(pairs) * 2, "Finishing process " + str((i + 1) - len(pairs)) + " of " + str(len(pairs)))
            process.join()
            processed_pairs.append(queue.get()[0])
            i += 1
        pairs = processed_pairs
    else:
        for pair in pairs:
            progress(i + 1, len(pairs), "Processing pair " + str(i + 1) + " of " + str(len(pairs)))
            pair.process_confusions(confusions)
            if not supersafe_mode and pair.primary_confusions > 0:
                write_gt(pair)
            if pair.secondary_confusions > 0 and not dest == "":
                copy_secondary(pair, dest)
            i += 1
        print()
        i = 0
        for xml in xmlList:
            progress(i + 1, len(xmlList), "Processing xml " + str(i + 1) + " of " + str(len(xmlList)))
            process_xml(xml, confusions)
            i += 1

    if verbose:
        verbose_print(pairs, True, True)
    print_statistics(pairs)
    toc = time.perf_counter()
    if multiThread:
        print(f"Finished matching in {toc - tic:0.4f} seconds using multiple threads")
    else:
        print(f"Finished matching in {toc - tic:0.4f} seconds using single thread")


def do_mt_conf(queue):
    send = queue.get()
    send[0].process_confusions(send[1])
    queue.put(send)


def process_xml(xml, confusions):
    if safe_mode and not supersafe_mode:
        xml: str
        shutil.copy2(xml, xml.replace('.xml', '.old.xml'))
    parser1 = ET.XMLParser(encoding="utf-8")
    etree = ET.parse(xml, parser1)
    namespace = etree.getroot().tag.split('}')[0].replace('{', '').replace('}', '')
    ET.register_namespace('', namespace)
    parser2 = ET.XMLParser(encoding="utf-8")
    tree = ET.parse(xml, parser2)
    for elem in tree.iter():
        tag_name = elem.tag.split('}')[1]
        if tag_name == "TextLine":
            line_children = list(elem)
            line_texts = []
            pred = ""
            gt = ""
            has_pred = False
            has_gt = False
            for text_equiv in line_children:
                if text_equiv.tag.split('}')[1] == "TextEquiv":
                    line_texts.append(text_equiv)
                if len(line_texts) > 1:
                    for text in line_texts:
                        text: ET.Element
                        #  pred
                        if text.attrib['index'] == '0':
                            pred = list(text)[0].text
                            has_pred = True
                        if text.attrib['index'] == '1':
                            gt = list(text)[0].text
                            has_gt = True
            if has_gt and has_pred:
                pair = Pair(xml + " -> " + elem.get('id'), gt, "", pred, "")
                pair.process_confusions(confusions)
                if pair.primary_confusions > 0:
                    verbose_print({pair}, True, False)
                for text in line_texts:
                    if text.attrib['index'] == '1':
                        list(text)[0].text = pair.gt_text
    if not supersafe_mode:
        tree.write(xml, encoding='utf8', xml_declaration=True)


def write_gt(pair):
    gt_path = pair.gt
    if safe_mode:
        old_gt_path = pair.gt.replace(gtExt, oldGtExt, 1)
        old_gt_file = open(old_gt_path, "w")
        old_gt_file.write(pair.old_gt)
        old_gt_file.close()
    gt_file = open(gt_path, "w")
    gt_file.write(pair.gt_text)
    gt_file.close()


def copy_secondary(pair, destination):
    if pair.secondary_confusions > 0:
        shutil.copy2(pair.gt, destination)
        shutil.copy2(pair.pred, destination)
        shutil.copy2(pair.img, destination)


def pair_files():
    i = 0
    pairs = []
    for gt in gtList:
        progress(i + 1, len(gtList), "Pairing file " + str(i + 1) + " of " + str(len(gtList)))
        gt_path = ntpath.dirname(gt)
        if not gt_path.endswith(os.path.sep):
            gt_path += os.path.sep
        name = strip_path(gt.split('.')[0])
        pred = gt_path + name + predExt
        if not os.path.isfile(pred):
            i += 1
            continue
        img = [f for f in glob.glob(gt_path + os.path.sep + name + "*" + imgExt)][0]
        if not os.path.isfile(img):
            img = "undefined"
        pairs.append(Pair(gt, get_text(gt), pred, get_text(pred), img))
        i += 1
    return pairs


def get_files():
    global gtList
    gtList = gtList + [f for f in sorted(glob.glob(path + '*' + gtExt))]
    global predList
    predList = [f for f in sorted(glob.glob(path + '*' + predExt))]
    global imgList
    imgList = [f for f in sorted(glob.glob(path + '*' + predExt))]


def check_dest(destination, is_source=False):
    if not os.path.exists(destination) and not is_source:
        print(destination + " not found, creating directory")
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
    global gtList
    gtList = args.gt_list
    global xmlList
    xmlList = args.xml_list
    global safe_mode
    safe_mode = args.safe
    global supersafe_mode
    supersafe_mode = args.supersafe
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
    global dest
    if not args.dest == "":
        dest = check_dest(args.dest)
    else:
        dest = check_dest(path + "check" + os.path.sep)
    #    global multiThread
    #    multiThread = args.multiThread
    global ct_path
    ct_path = args.ct
    global cutoff
    cutoff = args.threshold


def make_parser():
    parser = argparse.ArgumentParser(description='python script to solve confusions in fraktur script')
    parser.add_argument('-g',
                        nargs="*",
                        action='store',
                        dest='gt_list',
                        default=[],
                        help='List of .gt.txt files')
    parser.add_argument('-x',
                        nargs="*",
                        action='store',
                        dest='xml_list',
                        default=[],
                        help='List of pagexml files')
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
                        help='Ground Truth File extension')
    parser.add_argument('--pred-ext',
                        action='store',
                        dest='predExt',
                        default='.pred.txt',
                        help='Prediction File extension')
    parser.add_argument('--img-ext',
                        action='store',
                        dest='imgExt',
                        default='.png',
                        help='IMG extension')

    parser.add_argument('-c'
                        '--ct-file',
                        action='store',
                        dest='ct',
                        default="",
                        help='CT file to parse confusions from')

    parser.add_argument('-t',
                        action='store',
                        dest='threshold',
                        type=float,
                        default=3.5,
                        help='Everything above this percentage will be corrected')

    parser.add_argument('-d'
                        '--destination',
                        action='store',
                        dest='dest',
                        default="",
                        help='Output folder for confusions')
    parser.add_argument('-s',
                        '--safe',
                        action='store_true',
                        dest='safe',
                        default=True,
                        help='Overwrites files, but saves copies')
    parser.add_argument('--supersafe',
                        action='store_true',
                        dest='supersafe',
                        default=False,
                        help='Does not overwrite gt/xml file, cli output only')
    parser.add_argument('--debug',
                        action='store_true',
                        dest='debug',
                        default=False,
                        help='debug mode')
    #    parser.add_argument('-f'
    #                        '--fast',
    #                        action='store_true',
    #                        dest='multiThread',
    #                        default=False,
    #                        help='use multiple threads (testing only, does not write)')
    parser.add_argument('-v'
                        '--verbose',
                        action='store_true',
                        dest='verbose',
                        default=False,
                        help='Output every found confusion to cli')
    return parser


def progress(count, total, status=''):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '█' * filled_len + '_' * (bar_len - filled_len)

    sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stdout.flush()


def verbose_print(pairs, show_primary, show_secondary):
    show_primary: bool
    show_secondary: bool
    for pair in pairs:
        if show_primary and pair.primary_confusions > 0:
            print("\npath: " + pair.gt)
            print("oldGT: " + pair.old_gt)
            print("predn: " + pair.pred_text)
            print("corrn: " + pair.gt_text)
            found_confusion = ""
            for confusion in set(pair.foundConfusions):
                found_confusion += "".join(map(str, confusion.to_string())) + " "
            print("Confusions found: " + found_confusion)
        if show_secondary and pair.secondary_confusions > 0:
            print("\npath: " + pair.gt)
            print("  GT: " + pair.gt_text)
            print("pred: " + pair.pred_text)
            found_confusion = ""
            for confusion in set(pair.foundConfusions):
                found_confusion += "".join(map(str, confusion.to_string())) + " "
            print("Confusions found: " + found_confusion)


def print_statistics(pairs):
    found = 0
    fixed = 0
    for pair in pairs:
        found += pair.primary_confusions + pair.secondary_confusions
        fixed += pair.primary_confusions
    print("\n Matched GT/Predictions:    " + str(len(pairs)))
    print("       Found Confusions:    " + str(found))
    print("   Corrected Confusions:    " + str(fixed))


def stringify_tuple_list(plist):
    string = "["
    for ltuple in plist:
        string += "(" + str(ltuple[0]) + ", " + str(ltuple[1]) + "),\n"
    return string[:-2] + "]"


def parse_ct(ct, threshold):
    with open(ct, "r") as ct_file:
        confusions: Confusions = list()
        print("\nFound the Confusions (Corrects if True):")
        for line in ct_file.readlines():
            #  is_primary = False
            if line.startswith("{"):
                th = float(line.split()[-1].replace("%", ""))
                is_primary = th > threshold
                regex = re.compile('{(.*?)}')
                match = regex.findall(line)
                if len(match) == 2:
                    confusion = Confusion(match[0], match[1], is_primary)
                    confusions.append(confusion)
                    print(confusion.to_string() + "  " + str(is_primary))
                else:
                    print("ct file contains errors")
    return confusions


if __name__ == "__main__":
    main()
