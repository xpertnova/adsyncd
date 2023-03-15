import sys

sys.path.append("C:\\Program Files\\adsyncd\\lib")

import win32serviceutil
import win32service
import win32event
import servicemanager
import schedule
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import configparser
from AzureSyncHandler import AzureSyncHandler

class adsyncdService(win32serviceutil.ServiceFramework):
    _svc_name_ = "adsyncd"
    _svc_display_name_ = "Azure AD Synchronization Daemon for Windows"
    _svc_description_ = "Synchronizes your Azure AD with your local Active Directory without Azure AD Basic or Premium"

    @classmethod
    def parse_command_line(cls):
        win32serviceutil.HandleCommandLine(cls)
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
    def SvcStop(self):
        self.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE, servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ''))
        self.start()
        servicemanager.LogInfoMsg("adsyncd - main exited")
    def stop(self):
        logging.info("Terminating service")
    def main(self):
        handler = AzureSyncHandler()
        schedule.every(self.schedule_length).minutes.do(handler.syncUsers)
        handler.syncUsers()
        while True:
            schedule.run_pending()
            time.sleep(self.wait_length)
    def start(self):
        config = configparser.ConfigParser()
        config.read("C:\\Program Files\\adsyncd\\config.cfg")
        try:
            self.schedule_length = int(config["Daemon"]["syncInterval"])
            self.wait_length = int(config["Daemon"]["checkInterval"])
            self.backup_count = int(config["Daemon"]["logBackupCount"])
        except Exception as e:
            print("Error reading config: " + str(e))
            sys.exit(1)
        # Initializing logging
        logHandler = TimedRotatingFileHandler(filename="/var/adsyncd/adsyncd.log", when="D", interval=1,
                                              backupCount=self.backup_count)
        logging.basicConfig(handlers=[logHandler],
                            format="%(asctime)s-%(process)d--%(levelname)s-%(message)s", level=logging.INFO)
        logging.info("adsyncd for Windows Version 0.2")
        servicemanager.LogInfoMsg("adsyncd for Windows Version 0.2")
        logging.info("Service start successful")
        servicemanager.LogInfoMsg("Service start successful")
        logging.info("Setting up adsyncd")
        servicemanager.LogInfoMsg("Setting up adsyncd")

if __name__ == '__main__':
    adsyncdService.parse_command_line()