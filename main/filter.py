import config
from gamejob import GameJob, get_gamejob
import roblox
import itertools
import os
import shutil
import threading
import time
import csv
import ctypes
from flask import Flask, request
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
set_title = ctypes.windll.kernel32.SetConsoleTitleW


## Config variables
TARGET_PLACE_ID = int(input("Target Place ID >> ").strip())
FILTER_THREADS = 125
SIMULTANEOUS_INSTANCES = 4
RESULT_TIMEOUT = 60
RELOAD_SCRIPT = True
USE_PROXIES_FOR_FILTER = False
INSTANCE_LOCK_TIME = 5 # estimated amount of time for synapse to attach
WEB_PORT = 4920
ACCOUNT_FILTER = lambda s: \
    s.has_recently_played(TARGET_PLACE_ID)
    #len(s.get_owned_gamepasses(TARGET_PLACE_ID))>0


## Global variables
csv_path = "./output/Accounts_%d.csv" % TARGET_PLACE_ID
check_queue = Queue()
instance_start_lock = threading.Lock()
checked = 0
cpm_list = []
cookies = []


## Validate variables & files
if not TARGET_PLACE_ID in config.places:
    exit("Target place id is not defined in config")

if not os.path.exists("./Synapse-X"):
    exit("Synapse-X is not present")

if not os.path.exists("./Synapse-X/autoexec/gather.lua") \
    or RELOAD_SCRIPT:
    shutil.copyfile("./files/gather.lua",
                    "./Synapse-X/autoexec/gather.lua")

if not os.path.exists("./output"):
    os.mkdir("./output")


## Set up additional variables
place_config = config.places[TARGET_PLACE_ID]
output_file = open(csv_path, "a", encoding="UTF-8", errors="ignore",
                   newline="")
csv_writer = csv.DictWriter(output_file, place_config["fields"])
if not output_file.tell():
    csv_writer.writeheader()


## Display information
print("Make sure auto-attach is enabled on Synapse X")
print("Loading files ..")


## Load cookies into queue, and proxies into cycle iter
with open("cookies.txt", encoding="UTF-8", errors="ignore") as f:
    for line in f.read().splitlines():
        cookie = line.replace("WARNING:", "WARNING") \
                     .split(":")
        cookies.append(cookie)
    cookies_count = len(cookies)

proxies = None
if USE_PROXIES_FOR_FILTER:
    with open("proxies.txt", encoding="UTF-8", errors="ignore") as f:
        lines = f.read().splitlines()
        proxies_count = len(lines)
        proxies = itertools.cycle([
            line
            for line in lines
        ])
        del lines


## Display information about loaded files
print("%d cookies loaded" % cookies_count)
print("%d proxies loaded" % (proxies_count \
    if USE_PROXIES_FOR_FILTER else 0))


## Converts list of cookie fields
def convert(fields):
    result = dict(username=None,
                  password=None,
                  cookie=None)
    if len(fields) == 1:
        result["cookie"] = fields[0]
    else:
        result["username"] = fields[0]
        result["password"] = fields[1]
        result["cookie"] = fields[2]
    return result
 

## Function for filtering cookie based on ACCOUNT_FILTER
def filter_cookie(_cookie):
    while 1:
        proxy = None
        if USE_PROXIES_FOR_FILTER:
            proxy = next(proxies)
        
        session = roblox.Session(
            *convert(_cookie).values(),
            proxy)

        try:
            session.load()
            if ACCOUNT_FILTER(session):
                return session
            else:
                return
        
        except roblox.InvalidSession:
            return

        except Exception as err:
            print(err)
        
        finally:
            session.close()


## Worker for checking cookies
class CheckerWorker(threading.Thread):
    def __init__(self):
        super().__init__()
    
    def run(self):
        global checked
        while 1:
            session = check_queue.get(True)

            try:
                session.set_conn()

                # pause everything until synapse attaches
                with instance_start_lock:
                    start_time = time.time()
                    print("Starting game instance with %s" % session.name)
                    instance = session.start_game_instance(TARGET_PLACE_ID)
                    job = GameJob(session.id, instance)
                    time.sleep(INSTANCE_LOCK_TIME)

                # wait for result from synapse
                try:
                    result = job.get_result(RESULT_TIMEOUT)
                finally:
                    job.cleanup()
                
                elapsed = round(time.time()-start_time, 2)
                print("Received results for %s in %.2fs :: %s" % (
                    session.name,
                    elapsed,
                    str(result)
                ))

                # prepare & write row
                row = {}
                for field in place_config["fields"]:
                    if field == "username":
                        value = session.name
                    elif field == "password":
                        value = session.password
                    elif field == "cookie":
                        value = session.cookie
                    else:
                        value = result[field]
                        if type(value) == list:
                            value = ", ".join(value)
                    row[field] = value
                csv_writer.writerow(row)
                output_file.flush()

                # cpm stuff
                checked += 1
                cpm_list.append(time.time())

            except Exception as err:
                print(f"Error while checking {session.name}: {err}")
                check_queue.put(session)
            
            finally:
                session.close()


## Worker for updating title
class TitleWorker(threading.Thread):
    def __init__(self):
        self.interval = 0.1
        super().__init__()
    
    def run(self):
        global cpm_list
        while 1:
            time.sleep(self.interval)
            ct = time.time()
            cpm_list = list(filter(
                lambda x: (ct-x) <= 60,
                cpm_list
            ))
            cpm = len(cpm_list)
            set_title("  |  ".join([
                "Checked: %d" % checked,
                "CPM: %d" % cpm,
                "Filtered Queue: %d" % check_queue.qsize(),
                "Left: %d" % cookies_count
            ]))


## Set up web API
import logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)
os.environ["WERKZEUG_RUN_MAIN"] = "true"
web = Flask("API")

@web.route("/result", methods=["POST"])
def post_result_view():
    data = request.get_json()
    uid = data.get("userId")
    result_data = data.get("result")
    job = get_gamejob(uid)

    if not job:
        return "No job was found for this user id", 400
    
    job.complete(result_data)
    return "Success"


## Start web API
threading.Thread(target=web.run, kwargs=dict(
    port=WEB_PORT
)).start()


## Start title worker
TitleWorker().start()


## Start checker threads
for _ in range(SIMULTANEOUS_INSTANCES):
    CheckerWorker().start()


## Filter cookies
with ThreadPoolExecutor(max_workers=FILTER_THREADS) as e:
    for session in e.map(filter_cookie, cookies):
        cookies_count -= 1
        if not session: continue
        check_queue.put(session)
