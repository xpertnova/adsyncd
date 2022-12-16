#!/usr/bin/env python3
import daemon
import lockfile
import schedule
import time


from main import AzureSyncHandler

with daemon.DaemonContext(uid=0, gid=0, working_directory="/var/adsyncd", pidfile=lockfile.FileLock("/var/run/adsyncd.pid")):
    handler = AzureSyncHandler()
    schedule.every(60).minutes.do(handler.syncUsers())
    while True:
        schedule.run_pending()
        time.sleep(10) #Every 10 seconds