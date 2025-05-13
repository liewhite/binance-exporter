import json
import sys


conf_name = sys.argv[1]
with open(conf_name + '.json', "r") as f:
    conf = json.load(f)
    conf["db"]["database"] = conf_name
    conf['name'] = conf_name