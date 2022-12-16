#!/usr/bin/env python3

import daemon
import schedule
import time
import AzureSyncHandler

with daemon.DaemonContext(uid=0, gid=0, working_directory="/var/adsyncd", pidfile=daemon.pidfile.PIDLockFile("/var/run/lock/adsyncd.pid")):
    handler = AzureSyncHandler()
    schedule.every(10).minutes.do(handler.syncUsers()) #Every 10 minutes check for new users
    while True:
        schedule.run_pending()
        time.sleep(10) #Every 10 seconds check if scheduled