# fraktur_confusions
Corrects and checks Ground Truth from txt-files and pageXml for common OCR mistakes.

# Usage

```
# python3 fraktur_conf.py -h                    
usage: fraktur_conf.py [-h] [-g [GT_LIST [GT_LIST ...]]] [-x [XML_LIST [XML_LIST ...]]] [--pred-xml [XML_PRED_LIST [XML_PRED_LIST ...]]] [-p PATH] [--gt-ext GTEXT] [--pred-ext PREDEXT] [--img-ext IMGEXT] [-c--ct-file CT]
                       [-t THRESHOLD] [-d--destination DEST] [-s] [--supersafe] [--debug] [-v--verbose]


python script to solve confusions in fraktur script

optional arguments:
  -h, --help                    show this help message and exit
  -g [GT_LIST [GT_LIST ...]]    List of .gt.txt files
  -x [XML_LIST [XML_LIST ...]]  List of pagexml files
  --pred-xml [XML_PRED_LIST [XML_PRED_LIST ...]]
                                List of pred xml files (if not specified, pred will be searched in xml_list using 0|1 indices)
  -p PATH, --path PATH          Path to GT and Prediction
  --gt-ext GTEXT                Ground Truth File extension
  --pred-ext PREDEXT            Prediction File extension
  --img-ext IMGEXT              IMG extension
  -c--ct-file CT                CT file to parse confusions from
  -t THRESHOLD                  Everything above this percentage will be corrected
  -d--destination DEST          Output folder for confusions
  -s, --safe                    Overwrites files, but saves copies
  --supersafe                   Does not overwrite gt/xml file, cli output only
  --debug                       debug mode
  -v--verbose                   Output every found confusion to cli


```

#### Page XML
Please note that currently only PageXml 2017 and 2019 are supported.


# ZPD
Developed at [Zentrum für Philologie und Digitalität](https://www.uni-wuerzburg.de/en/zpd/startseite/) at the [Julius-Maximilians-Universität of Würzburg](https://www.uni-wuerzburg.de/en/home/)
