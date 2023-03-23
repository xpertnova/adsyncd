"""
Azure AD User Administration

This is a helper script for the Azure AD Synchronization Daemon.

Classes:
    DomainUserAdministration - Object to handle connection to Azure AD

"""

import requests

from UserAdministration import UserAdministration

import logging


class DomainUserAdministration(UserAdministration):
    """
    This class handles connection to the Azure AD and can return a list of users.

    Attributes
    ----------
    __clientID : str
        Azure AD client ID
    __clientSecret : str
        Azure AD client secret
    __token : str
        Azure AD client token to be retrieved from Azure
    __ignoreList : list[str]
        List of to be ignored principals

    Methods
    -------
    fetchApiToken()
        Get API token from Azure AD
    syncUsers()
        Get users from Azure AD
    getUsernameList()
        Returns list of users in Azure AD (which are not in the ignore_list)
    setIgnoreList(ignore_list)
        Sets a new ignore list
    """
    __clientId = ""
    __clientSecret = ""
    __token = ""
    __ignoreList = []
    __users = []

    def __init__(self, client_id, client_secret, ignore_list=[]):
        """
        Constructor

        Parameters
        ----------
        client_id : str
            Azure AD client ID
        client_secret : str
            Azure AD client ID
        ignore_list : list[str]
            List of to be ignored principals
        """
        super().__init__()
        self.__clientId = client_id
        self.__clientSecret = client_secret
        self.__ignoreList = ignore_list
        self.fetchApiToken()
        self.syncUsers()

    def fetchApiToken(self):
        """
        Get API token from Azure AD
        Requires valid client_id and client_secret to be successful

        Returns
        -------
        None
        """
        logging.info("Getting API token")
        url = 'https://login.microsoftonline.com/xpertnovade.onmicrosoft.com/oauth2/v2.0/token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.__clientId,
            'scope': 'https://graph.microsoft.com/.default',
            'client_secret': self.__clientSecret
        }
        r = requests.post(url, data=data)
        self.__token = r.json().get('access_token')
        logging.info("Token retrieved")

    def syncUsers(self):
        """
        Get users from Azure AD
        Requires a valid API token to be set in the object

        Returns
        -------
        None
        """

        logging.info("Getting users from Azure AD")
        url = 'https://graph.microsoft.com/v1.0/users'
        headers = {
            'Content-Type': 'application\json',
            'Authorization': 'Bearer {}'.format(self.__token)
        }
        r = requests.get(url, headers=headers)
        logging.info("Response: %s", r)
        result = r.json()
        try:
            userJson = result["value"]
            users = []
            for u in userJson:
                u["userPrincipalName"].replace("\n", "")
                if not u["userPrincipalName"] in self.__ignoreList: users.append(
                    [u["displayName"], u["userPrincipalName"]])
            logging.info("Fetched users: %s", users)
            self.__users = users
            logging.info(str(len(u)) + " Users retrieved")
        except:
            logging.error("Could not get AD users. Response: %s", result)
            logging.info("Trying again with new API token")
            self.fetchApiToken()
            self.syncUsers()

    def getUsernameList(self):
        """
        Returns list of users with names and principals in Azure AD (which are not in the ignore_list)

        Returns
        -------
        list[list[str]]
            List of usernames (principals)
        """
        self.syncUsers()
        users = []
        for u in self.__users:
            users.append(u)
        return users

    def setIgnoreList(self, ignoreList):
        """
        Sets a new ignore list

        Parameters
        ----------
        ignoreList : list[str]
            List of principals to be ignored

        Returns
        -------
        None
        """
        self.__ignoreList = ignoreList
