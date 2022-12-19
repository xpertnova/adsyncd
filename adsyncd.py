#!/usr/bin/env python3
import sys
import daemon
import schedule
import time
from lockfile.pidlockfile import PIDLockFile
from AzureSyncHandler import AzureSyncHandler

#Appending Python path to ./lib folder
sys.path.append("/var/adsyncd/lib")
#Creating PID lockfile
pidfile = PIDLockFile("/var/run/adsyncd.pid")
#Creating Daemon
with daemon.DaemonContext(uid=0, gid=0, working_directory="/var/adsyncd", pidfile=pidfile) as context:
    handler = AzureSyncHandler()
    schedule.every(10).minutes.do(handler.syncUsers)  # Every 10 minutes check for new users
    while True:
        schedule.run_pending()
        time.sleep(10)  # Every 10 seconds check if scheduled

