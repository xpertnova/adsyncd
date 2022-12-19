#!/usr/bin/env python3
import sys
import daemon
import schedule
import time
import logging
from lockfile.pidlockfile import PIDLockFile
from AzureSyncHandler import AzureSyncHandler


#Creating PID lockfile
pidfile = PIDLockFile("/var/run/adsyncd.pid")
#Initializing logging
logging.basicConfig(filename="adsyncd.log", filemode="w",
                        format="%(asctime)s-%(process)d--%(levelname)s-%(message)s", level=logging.INFO)
logging.info("Pre-daemonization setup")
logHandler = logging.FileHandler("adsyncd.log")
# Appending Python path to ./lib folder, let's hope it works...?
sys.path.append("/var/adsyncd/lib")

#Creating Daemon
with daemon.DaemonContext(uid=0, gid=0, working_directory="/var/adsyncd", pidfile=pidfile, signal_map={signal.SIGTERM: terminate}, stderr=logHandler.stream, files_preserve=[logHandler.stream]) as context:
    logging.info("Setting up daemon")
    handler = AzureSyncHandler()
    schedule.every(10).minutes.do(handler.syncUsers)  # Every 10 minutes check for new users
    while True:
        schedule.run_pending()
        time.sleep(300)  # Every 5 minutes check if scheduled

def terminate(signum, frame):
    logging.info("Terminating daemon with SIGTERM")