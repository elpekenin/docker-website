import config
from flask import (
    Flask,
    render_template
)
import json
import logging
from pymongo import MongoClient
from requests import get
import subprocess

# =======
# Setup
logging.basicConfig(
    level=logging.DEBUG,
    filename="logs/log.txt",
    format="%(asctime)s -- %(message)s",
    datefmt="%d/%b/%y %H:%M:%S",
    filemode="w"
)
logging.info("Started !!")

if config.db_uri:
    client = MongoClient(config.db_uri, serverSelectionTimeoutMS=5000)
else:
    client = MongoClient(
        config.db_ip,
        username=config.db_user,
        password=config.db_pass,
        authSource=config.db_auth
    )

database = client["website"]

app = Flask(__name__)

with open("dex-name.json", "r") as f:
    dex_cache = json.load(f)


# =======
# Funcs
def read_from_cache(query):
   return dex_cache.get(query, 0) 


def get_dex(name):   
    # Don't use the DB nor PokeAPI, it's slow
    # FIXME This will break when new pokemons get added
    return read_from_cache(name.lower())

app.jinja_env.globals["get_dex"] = get_dex


def get_name(dex):
    return read_from_cache(str(dex))

app.jinja_env.globals["get_name"] = get_name


with open("./build-timestamp", "r") as f:
    build_date = f.readline()

app.jinja_env.globals["build_date"] = build_date


try:
    commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
except:
    commit = "Couldn't find commit hash"

app.jinja_env.globals["commit"] = commit


def class_from_row(row):
    return " ".join(row.keys())

app.jinja_env.globals["class_from_row"] = class_from_row


# =======
# Routes
@app.get("/")
def hello():
    return "Hello World!"

@app.get("/40dex/stats/")
def dex_stats():
    dex = list(database["40dex"].find())

    total = len(dex)
    
    pokes = 0
    families = 0
    for row in dex:
        add = True
        for key, value in row.items():
            if key in ["_id", "regions"]:
                continue
            
            if value > 0:
                pokes += value
                if add:
                    families += 1
                    add = False

        
    return render_template(
        "40dex-stats.html",
        families=families,
        pokes=pokes,
        total=total
    )

@app.get("/40dex/")
@app.get("/40dex/<_region>/")
def dex(_region="kanto"):
    try:
        region = int(_region) #parse to region id
        if region == 0:
            region = 1
    except:
        region = _region.lower()
        region = { #try parsing name to id, default to kanto
            "kanto":   1,
            "johto":   2,
            "hoenn":   3,
            "sinnoh":  4,
            "unova":   5,
            "teselia": 5,
            "kalos":   6,
            "alola":   7,
            "galar":   8
        }.get(region, 1)
    logging.debug(f"Parsed region {region} from '{_region}'")

    # get all pokedex filtered by region
    # TODO try to make the aggregation on a single query
    _filter = {"regions": {"$all": [region]}}
    _find = lambda x: list(database[x].find(_filter, {"_id": False}))
    _data = [
        _find("40dex"),
        _find("trade-dex")
    ]

    data = []
    for i, family in enumerate(_data[0]):
        temp = {}
        for poke in family:
            if poke == "regions":
                continue

            temp[poke] = [info[i][poke] for info in _data]

        data.append(temp)

    return render_template(
        "40dex.html",
        data=data,
        region=region,
        max_region=8,
        path="/40dex"
    )

