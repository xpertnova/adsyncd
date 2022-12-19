#!/usr/bin/env python3

import sys
# Appending Python path to ./lib folder, let's hope it works...?
sys.path.append("/var/adsyncd/lib")

import os
import daemon
import schedule
import time
import logging
import signal
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

logging.info("Pre-daemonization setup successful")

#Adding termination handler
def terminate(signum, frame):
    logging.info("Terminating daemon with SIGTERM")

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
    schedule.every(10).minutes.do(handler.syncUsers)  # Every 10 minutes check for new users
    handler.syncUsers()
    while True:
        schedule.run_pending()
        time.sleep(300)  # Every 5 minutes check if scheduled

