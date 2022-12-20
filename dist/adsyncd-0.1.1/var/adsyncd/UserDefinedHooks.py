
"""
In this file a user can define hooks which are triggered at certain stages.
Functionality will improve in future versions.
Please do not delete any of these functions. If you don't want to use a function, use keyword 'pass'.
To use logging just import logging inside your function, it will display in /var/adsyncd/adsyncd.log
Exceptions occuring during execution of your function will be caught and displayed in the logfile
"""

"""
This function gets an object of class User as parameter with the following methods:
    setPassword(passwordHash): Sets a new (encrypted!) Password for User
    getGroups(): Returns list of user groups
    getUsername(): returns username
    remove(): removes user 
"""
def postUserCreationHook(user):
    pass