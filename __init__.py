import daemon
import schedule
import time

#TODO Daemon scheint nicht zu funktionieren -> Cron? Daemon fixen?
#TODO irgendwo wird was geprintet? Die Azure Nutzer? kp...
#TODO invalid username fix ->

from main import AzureSyncHandler

with daemon.DaemonContext():
    handler = AzureSyncHandler()
    schedule.every(60).minutes.do(handler.syncUsers())
    while True:
        schedule.run_pending()
        time.sleep(10) #Every 10 seconds