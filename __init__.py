import daemon
import schedule
import time

#TODO invalid username fix -> invalid usernames not alowed. plain and simple.

from main import AzureSyncHandler

with daemon.DaemonContext():
    handler = AzureSyncHandler()
    schedule.every(60).minutes.do(handler.syncUsers())
    while True:
        schedule.run_pending()
        time.sleep(10) #Every 10 seconds