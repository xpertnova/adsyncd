#!/usr/bin/env python3

import sys
# Appending Python path to ./lib folder
sys.path.append("/var/adsyncd/lib")

import os
import daemon
import schedule
import time
import logging
import signal
import configparser
from lockfile.pidlockfile import PIDLockFile
from lockfile import AlreadyLocked
from AzureSyncHandler import AzureSyncHandler

#Initializing logging
logHandler = logging.FileHandler("/var/adsyncd/adsyncd.log")
logging.basicConfig(handlers=[logHandler],
                        format="%(asctime)s-%(process)d--%(levelname)s-%(message)s", level=logging.INFO)


#Initializing PID file
pidfile = PIDLockFile("/var/run/adsyncd.pid")
try:
    pidfile.acquire()
except AlreadyLocked:
    try:
        os.kill(pidfile.read_pid(), 0)
        print("adsyncd is already running. Aborting.")
        exit(1)
    except OSError: #No process with locked PID
        print("No processs running for lockfile, releasing lock")
pidfile.break_lock()
logging.info("adsyncd Version 0.1.1")
logging.info("Pre-daemonization setup successful")

#Reading config
config = configparser.ConfigParser()
config.read("/var/adsyncd/config.cfg")
try:
    schedule_length = int(config["Daemon"]["syncInterval"])
    wait_length = int(config["Daemon"]["checkInterval"])
except Exception as e:
    print("Error reading config: " + str(e))
    logging.error("Error reading config: " + str(e))
    sys.exit(1)
#Adding termination handler
def terminate(signum, frame):
    logging.info("Terminating daemon with SIGTERM")
    sys.exit(0)

#Adding synchronization trigger handler
def syncnow(signum, frame):
    logging.info("Recieved SIGUSR1, triggering sync")
    handler.syncUsers()

#Creating Daemon
with daemon.DaemonContext(uid=0, gid=0, working_directory="/var/adsyncd", pidfile=pidfile, signal_map={signal.SIGTERM: terminate, signal.SIGUSR1: syncnow}, stderr=logHandler.stream, files_preserve=[logHandler.stream]) as context:
    logging.basicConfig(handlers=[logHandler],
                        format="%(asctime)s-%(process)d--%(levelname)s-%(message)s", level=logging.INFO)
    logging.info("Setting up daemon")
    handler = AzureSyncHandler()
    schedule.every(schedule_length).minutes.do(handler.syncUsers)
    handler.syncUsers()
    while True:
        schedule.run_pending()
        time.sleep(wait_length)

