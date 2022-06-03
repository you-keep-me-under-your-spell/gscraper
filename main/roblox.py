import http.client
import subprocess
import random
import os
import time
import json
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.89 Safari/537.36"

def get_client_version():
    conn = http.client.HTTPConnection("setup.roblox.com")
    conn.request("GET", "/version")
    resp = conn.getresponse()
    version = resp.read().decode("UTF-8").strip()
    conn.close()
    return version

CLIENT_PATH = "%s/AppData/Local/Roblox/Versions/%s" % (
    os.environ["USERPROFILE"],
    get_client_version()
)

if not os.path.exists(CLIENT_PATH):
    CLIENT_PATH = "C:/Program Files (x86)/Roblox/Versions/%s" % (
        get_client_version()
    )

if not os.path.exists(CLIENT_PATH):
    CLIENT_PATH = "C:/Program Files/Roblox/Versions/%s" % (
        get_client_version()
    )

if not os.path.exists(CLIENT_PATH):
    exit("Could not detect path to Roblox client")


class InvalidSession(Exception): pass
class GameJobTimeout(Exception): pass

class Session:
    def __init__(self, username, password, cookie, proxy):
        self.id = None
        self.name = username
        self.password = password
        self.cookie = cookie
        self.conn = None

        self.proxy = None
        if proxy:
            self.proxy = proxy.split(":")
            self.proxy[1] = int(self.proxy[1])

        self.subdomain = "www"
        self.xsrf_token = None
    
    def load(self):
        self.set_conn()
        self.load_profile()
    
    def close(self):
        if self.conn:
            self.conn.close()

    def set_conn(self, full=None):
        self.close()
        host = "%s.roblox.com" % self.subdomain if not full else full
        if self.proxy:
            self.conn = http.client.HTTPSConnection(*self.proxy)
            self.conn.set_tunnel(host)
        else:
            self.conn = http.client.HTTPSConnection(host)
    
    def start_game_instance(self, pid):
        bid = random.randint(4838923665, 5838923665)
        lt = int(time.time() * 1000)
        lurl = "https://assetgame.roblox.com/game/PlaceLauncher.ashx" + \
            "?request=RequestGame&browserTrackerId=%d" % bid + \
            "&placeId=%d&isPlayTogetherGame=false" % pid
        at = self.get_auth_ticket()
        p = subprocess.Popen([
            os.path.join(CLIENT_PATH, "RobloxPlayerBeta.exe"),
            "--play",
            "-a", "https://www.roblox.com/Login/Negotiate.ashx",
            "-t", at,
            "-j", lurl,
            "-b", str(bid),
            "--launchtime=%d" % lt,
            "--rloc", "en_us",
            "--gloc", "en_us"
        ])
        return p


    def get_auth_ticket(self):
        self.set_conn("auth.roblox.com")
        ticket = self.request("POST", "/v1/authentication-ticket",
                              pdata={},
                              header="rbx-authentication-ticket")
        return ticket

    
    def load_profile(self):
        profile = self.request("GET", "/my/profile")
        self.id = profile["UserId"]
        self.name = profile["Username"]
        

    def has_recently_played(self, target_pid):
        self.set_conn("games.roblox.com")
        sorts = self.request("GET", "/v1/games/sorts?model.gameSortsContext=HomeSorts")["sorts"]
        token = [x for x in sorts if x["name"]=="MyRecent"]
        if not token: return
        token = token[0]["token"]
        resp = self.request("GET", f"/v1/games/list?sortToken={token}&startRows=0&maxRows=60&hasMoreRows=true&sortPosition=0")
        games = resp.get("games")
        if not games: return
        self.set_conn()
        return target_pid in list(map(
            lambda x: x["placeId"],
            games))

    
    def get_owned_gamepasses(self, target_pid):
        items = []
        url = "/games/getgamepassesinnerpartial" \
            f"?startIndex=0&maxRows=50&placeId={target_pid}"
        resp = self.request("GET", url)
        soup = BeautifulSoup(resp, "lxml")

        for el in soup.find_all(None, {"class": "list-item"}):
            owned = el.find(None, string="Owned") is not None
            if owned:
                items.append(
                    int(el.find(None, {"class": "gear-passes-asset"}).get("href") \
                        .split("/game-pass/")[1] \
                        .split("/")[0])
                )
    
        return items


    def request(self, method, url, pdata=None, header=None):
        self.conn.putrequest(method, url)
        self.conn.putheader("User-Agent", USER_AGENT)
        self.conn.putheader("Origin", "https://www.roblox.com")
        self.conn.putheader("Referer", "https://www.roblox.com/games/1818/--")
        self.conn.putheader("Cookie", ".ROBLOSECURITY=%s" % self.cookie)
        if method != "GET" and self.xsrf_token:
            self.conn.putheader("X-CSRF-TOKEN", self.xsrf_token)
        if pdata != None:
            pdata = json.dumps(pdata)
            self.conn.putheader("Content-Type", "application/json; charset=UTF-8")
            self.conn.putheader("Content-Length", len(pdata))
            self.conn.endheaders()
            self.conn.send(pdata.encode("UTF-8"))
        else:
            self.conn.endheaders()
        
        resp = self.conn.getresponse()
        data = resp.read().decode("UTF-8")

        if "x-csrf-token" in resp.headers:
            self.xsrf_token = resp.headers["x-csrf-token"]
            return self.request(method, url, data, header)
        
        if "location" in resp.headers:
            if "/notapproved.aspx" in resp.headers["location"].lower() \
                or "/newlogin" in resp.headers["location"].lower():
                emsg = None
                if "/newlogin" in resp.headers["location"].lower():
                    emsg = "The session is invalid"
                elif "/notapproved.aspx" in resp.headers["location"].lower():
                    emsg = "The session is suspended"
                raise InvalidSession(emsg)

            elif "web." in resp.headers["location"] \
                and self.subdomain != "web":
                self.subdomain = "web"
                self.set_conn()
                return self.request(method, url, pdata, header)

        if header:
            return resp.headers[header]
        
        if "content-type" in resp.headers \
            and "/json" in resp.headers["content-type"]:
            data = json.loads(data)
        
        return data