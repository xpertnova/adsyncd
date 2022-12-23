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
    _clientID : str
        Azure AD client ID
    _clientSecret : str
        Azure AD client secret
    _token : str
        Azure AD client token to be retrieved from Azure
    _ignoreList : list[str]
        List of to be ignored principals

    Methods
    -------
    getApiToken()
        Get API token from Azure AD
    syncUsers()
        Get users from Azure AD
    getUsernameList()
        Returns list of users in Azure AD (which are not in the ignoreList)
    setIgnoreList(ignoreList)
        Sets a new ignore list
    """
    _clientId = ""
    _clientSecret = ""
    _token = ""
    _ignoreList = []

    def __init__(self, clientId, clientSecret, ignoreList=[]):
        """
        Constructor

        Parameters
        ----------
        clientId : str
            Azure AD client ID
        clientSecret : str
            Azure AD client ID
        ignoreList : list[str]
            List of to be ignored principals
        """
        super().__init__()
        self._clientId = clientId
        self._clientSecret = clientSecret
        self._ignoreList = ignoreList
        self.getApiToken()
        self.syncUsers()

    def getApiToken(self):
        """
        Get API token from Azure AD
        Requires valid clientId and clientSecret to be successful

        Returns
        -------
        None
        """
        logging.info("Getting API token")
        url = 'https://login.microsoftonline.com/xpertnovade.onmicrosoft.com/oauth2/v2.0/token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': self._clientId,
            'scope': 'https://graph.microsoft.com/.default',
            'client_secret': self._clientSecret
        }
        r = requests.post(url, data=data)
        self._token = r.json().get('access_token')
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
            'Authorization': 'Bearer {}'.format(self._token)
        }
        r = requests.get(url, headers=headers)
        result = r.json()
        try:
            userJson = result["value"]
            users = []
            for u in userJson:
                u["userPrincipalName"].replace("\n", "")
                if not u["userPrincipalName"] in self._ignoreList: users.append([u["displayName"], u["userPrincipalName"]])
            self._users = users
        except:
            logging.error("Could not get AD users. Response: %s", result)
            logging.info("Trying again with new API token")
            self.getApiToken()
            self.syncUsers()
    def getUsernameList(self):
        """
        Returns list of users with names and principals in Azure AD (which are not in the ignoreList)

        Returns
        -------
        list[list[str]]
            List of usernames (principals)
        """
        self.syncUsers()
        users = []
        for u in self._users:
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
        self._ignoreList = ignoreList
