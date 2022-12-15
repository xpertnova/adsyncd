import os
import grp
import signal
import daemon
import lockfile
import schedule
import time

from main import AzureSyncHandler

with daemon.DaemonContext():
    handler = AzureSyncHandler()
    schedule.every(60).minutes.do(handler.syncUsers())
    while True:
        schedule.run_pending()
        time.sleep(600) #Every 10 minutes