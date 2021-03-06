#--------------------#
#  Import Libraries  #
#--------------------#
import re
import os
import sys
import clr
import time
import json
import codecs
import System
from collections import deque

clr.AddReference("System.Web")
from System.Web import HttpUtility
from System.Net import WebClient

#---------------------------------#
#  [Required] Script Information  #
#---------------------------------#
Description = "Text to speech with Google translate voice"
ScriptName = "TheNewTTS"
Creator = "LuisSanchezDev"
Editor = "Bultz"
Version = "1.1"
Website = "https://www.fiverr.com/luissanchezdev"

#---------------------------
#  Define Global Variables
#---------------------------
global PATH, TEMP_MP3, CACHE_MP3, LOCK_FILE, FINISH_FILE, CONFIG_FILE
PATH = os.path.dirname(os.path.realpath(__file__))
TEMP_MP3 = os.path.join(PATH,"cache","tts2.mp3")
CACHE_MP3 = os.path.join(PATH,"cache","tts.mp3")
LOCK_FILE = os.path.join(PATH,"cache","lock")
FINISH_FILE = os.path.join(PATH,"cache","finished")
CONFIG_FILE = os.path.join(PATH,"config.json")

global SETTINGS, TEXTS_QUEUE
SETTINGS = {}
TEXTS_QUEUE = deque()
BANNED_WORDS = []

global last_check_period
last_check_period = 0

#----------------------------------------------------#
#  [Required] Initialize Data (Only called on load)  #
#----------------------------------------------------#
def Init():
  global SETTINGS, CONFIG_FILE
  cache_folder = os.path.dirname(CACHE_MP3)
  if not os.path.isdir(cache_folder):
    os.mkdir(cache_folder)
  
  to_remove = [CACHE_MP3, LOCK_FILE, FINISH_FILE, TEMP_MP3]
  for file in to_remove: os.popen('del "{0}"'.format(file))
  
  try:
    with codecs.open(CONFIG_FILE, encoding="utf-8-sig", mode='r') as file:
      SETTINGS = json.load(file, encoding="utf-8-sig")
  except:
    SETTINGS = {
      "read_all_text": False,
      "command": "!tts",
      "permission": "Everyone",
      "lang": "English (US) [en-US]",
      "pitch": 100,
      "speed": 100,
      "volume": 90
    }

    load_list()
  
  SETTINGS["lang"] = re.match(r"^.*\[(.+)\]", SETTINGS["lang"]).groups()[0]
  SETTINGS["pitch"] /= 100.0
  SETTINGS["speed"] /= 100.0
  SETTINGS["volume"] /= 100.0

#----------------------------------------------#
#  [Required] Execute Data / Process messages  #
#----------------------------------------------#
def Execute(data):
  if data.IsChatMessage():
    if SETTINGS["read_all_text"]:
      TEXTS_QUEUE.append(data.UserName)
      TEXTS_QUEUE.append(filter_message(data.Message))
      return
    elif data.GetParam(0) == SETTINGS["command"]:
      if not Parent.HasPermission(data.User, SETTINGS["permission"], ""):
        Parent.SendStreamMessage(SETTINGS["msg_permission"])
        return
      if SETTINGS["user_cooldown"] and Parent.GetUserCooldownDuration(ScriptName, SETTINGS["command"], data.User):
        Parent.SendStreamMessage(SETTINGS["msg_user_cooldown"])
        return
      if SETTINGS["cooldown"] and Parent.GetCooldownDuration(ScriptName, SETTINGS["command"]):
        Parent.SendStreamMessage(SETTINGS["msg_cooldown"])
        return
      if not Parent.RemovePoints(data.User, data.UserName, SETTINGS["cost"]):
        Parent.SendStreamMessage(SETTINGS["msg_cost"])
        return
      if not data.GetParam(1):
        Parent.SendStreamMessage("You need to specify a message")
        return
      text = ' '.join(data.Message.split(' ')[1:])
      TEXTS_QUEUE.append(text)
      Parent.AddCooldown(ScriptName, SETTINGS["command"], SETTINGS["cooldown"])
      Parent.AddUserCooldown(ScriptName, SETTINGS["command"], data.User, SETTINGS["user_cooldown"])
      return

#----------------------------------------------------------------------------------------------------#
#   [Required] Tick method (Gets called during every iteration even when there is no incoming data)  #
#----------------------------------------------------------------------------------------------------#
def Tick():
  global LOCK_FILE, FINISH_FILE, last_check_period
  if time.time() - last_check_period >= 0.25:
    try:
      last_check_period = time.time()
      if os.path.isfile(LOCK_FILE) or os.path.isfile(FINISH_FILE):
        if os.path.isfile(FINISH_FILE):
          os.popen('del "{0}" & del "{1}"'.format(
            LOCK_FILE, FINISH_FILE
          ))
          os.remove(CACHE_MP3)
          os.rename(TEMP_MP3, CACHE_MP3)
          Parent.PlaySound(CACHE_MP3, 100)
          TEXTS_QUEUE.popleft()
          return
        else:
          return
      if os.path.isfile(CACHE_MP3):
        os.popen('del "{0}"'.format(CACHE_MP3))
        last_check_period = time.time()
        return
      if len(TEXTS_QUEUE) > 0:
        text = TEXTS_QUEUE[0]
        download_tts(CACHE_MP3, text)
        filter_audio(CACHE_MP3)
    except Exception as e:
      Parent.Log(ScriptName, "Please report this to the github page.\nERROR: " + str(e))
    return

#-----------------------------------------------------------------------------------------------------#
#  [Optional] Reload Settings (Called when a user clicks the Save Settings button in the Chatbot UI)  #
#-----------------------------------------------------------------------------------------------------#
def ReloadSettings(jsonData):
  global SETTINGS, TEXTS_QUEUE, BANNED_WORDS
  Init()
  clear_queue()
  TEXTS_QUEUE.append("Configuration updated successfuly") 

#-----------------------------------------------------------------------#
#  [TheNewTTS] Changes the pitch, speed and volume of downloaded mp3  #
#-----------------------------------------------------------------------#
def filter_audio(file_path):
  global SETTINGS, PATH, LOCK_FILE, FINISH_FILE, TEMP_MP3
  with open(LOCK_FILE,"w") as f: f.write(" ")
  
  commands = [
    'cd "'+PATH+'"',
    'ffmpeg.exe -i "{0}" -af asetrate=24000*{1},atempo={2}/{1},aresample=48000,volume={3} "{4}" -y'.format(
      file_path, SETTINGS["pitch"], SETTINGS["speed"], SETTINGS["volume"], TEMP_MP3
    ),
    'echo 1 > "' + FINISH_FILE + '"'
  ]
  os.popen(" & ".join(commands))
  return

#-----------------------------------------------------------------------------------------#
#  [TheNewTTS] Download from Google Translate voice generator using defined TTS language  #
#-----------------------------------------------------------------------------------------#
def download_tts(file_path,text):
  global SETTINGS
  with WebClient() as wc:
    url = "https://translate.google.com/translate_tts?ie=UTF-8&q={0}&tl={1}&client=tw-ob".format(
      HttpUtility.UrlEncode(text), SETTINGS["lang"]
    )
    wc.Headers["Referer"] = "http://translate.google.com/"
    wc.Headers["User-Agent"] = "stagefright/1.2 (Linux;Android 5.0)"
    wc.DownloadFile(url,file_path)
    return

#---------------------------#
#  [TheNewTTS] Clear queue  #
#---------------------------#
def clear_queue():
  global TEXTS_QUEUE
  while len(TEXTS_QUEUE) > 0: TEXTS_QUEUE.pop()

#-------------------------------#
#  [TheNewTTS] UI Link buttons  #
#-------------------------------#
def donate():
  os.startfile("https://streamlabs.com/luissanchezdev/tip")
def open_contact_me():
  os.startfile("www.fiverr.com/luissanchezdev/makea-custom-streamlabs-chatbot-script")
def open_readme():
  os.startfile("https://github.com/LuisSanchez-Dev/TheNewTTS")

#-------------------------------#
#  [Custom] Remove Swear Words  #
#-------------------------------#

def load_list():
    f = open("swear.txt", "r")
    words = f.readlines()

    for word in words:
        BANNED_WORDS.append(word.strip())

def filter_message(msg):
    big_regex = re.compile('|'.join(map(re.escape, BANNED_WORDS)))
    msg = big_regex.sub("beep", msg)
    return msg