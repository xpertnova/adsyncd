// This package handles requests to the Azure AD
package AzureAD

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"slices"
	"time"
)

type AzureADSyncHandler struct {
	clientId, clientSecret, token, authUrl, azureGroupId string
	ignoreList                                           []string
	httpClient                                           http.Client
	users                                                []azureADUser
}

type authRequestData struct {
	grantType    string `json:"grant_type"`
	clientId     string `json:"client_id"`
	scope        string `json:"scope"`
	clientSecret string `json:"client_secret"`
}

type authRequestResponse struct {
	accessToken string `json:"access_token"`
}

type userRequestResponse struct {
	value []azureADUser `json:"value"`
}

type azureADUser struct {
	displayName       string `json:"displayName"`
	userPrincipalName string `json:"userPrincipalName"`
}

// Get the API token from Azure AD
// Requires valid clientId and clientSecret
func (h *AzureADSyncHandler) fetchApiToken() error {
	log.Println("Fetching Azure AD API Token")
	data := authRequestData{
		"client_credentials",
		h.clientId,
		"https://graph.microsoft.com/.default",
		h.clientSecret}
	marshalled, err := json.Marshal(data)
	if err != nil {
		log.Printf("Cannot serialize request data: %s", err)
		return fmt.Errorf("Cannot serialize request data: %s", err)
	}
	req, err := http.NewRequest("POST", h.authUrl, bytes.NewReader(marshalled))
	if err != nil {
		log.Printf("Cannot build request: %s", err)
		return fmt.Errorf("Cannot build request: %s", err)
	}
	res, err := h.httpClient.Do(req)
	if err != nil {
		log.Printf("Cannot send request: %s", err)
		return fmt.Errorf("Cannot send request: %s", err)
	}
	if res.StatusCode != 200 {
		log.Printf("Response failed with status code %d", res.StatusCode)
		return fmt.Errorf("Response failed with status code %d", res.StatusCode)
	}
	defer res.Body.Close()
	resBody, err := io.ReadAll(res.Body)
	if err != nil {
		log.Printf("Cannot read response body: %s", err)
		return fmt.Errorf("Cannot read response body: %s", err)
	}
	var resMarshalled authRequestResponse
	json.Unmarshal(resBody, &resMarshalled)
	h.token = resMarshalled.accessToken
	log.Println("Access token successfully fetched")
	return nil
}

// Get users from Azure AD
func (h *AzureADSyncHandler) syncUsers() error {
	log.Printf("Getting users from Azure AD")
	req, err := http.NewRequest("GET", "https://graph.microsoft.com/v1.0/groups/"+h.azureGroupId+"/members?$select=displayName,userPrincipalName", nil)
	if err != nil {
		log.Printf("Cannot build request: %s", err)
		return fmt.Errorf("Cannot build request: %s", err)
	}
	req.Header.Set("Content-Type", "application\\json")
	req.Header.Set("Authorization", "Bearer "+h.token)
	res, err := h.httpClient.Do(req)
	if err != nil {
		log.Printf("Cannot fetch users: %s", err)
		return fmt.Errorf("Cannot fetch users: %s", err)
	}
	defer res.Body.Close()
	if res.StatusCode != 200 {
		if res.StatusCode == 403 {
			log.Printf("Request failed with status code 403 - retrying with new API token")
			err := h.fetchApiToken()
			if err != nil {
				log.Fatalf("New API token could not be fetched: %s - terminating", err)
			}
			h.syncUsers()
		} else {
			log.Printf("Request failed with error %d", err)
			return fmt.Errorf("Request failed with error %d", err)
		}
	}
	resBody, err := io.ReadAll(res.Body)
	if err != nil {
		log.Printf("Cannot read response: %s", err)
		return fmt.Errorf("Cannot read response: %s", err)
	}
	var response userRequestResponse
	err = json.Unmarshal(resBody, &response)
	if err != nil {
		log.Panicln("Unable to unmarshal response: %s", err)
		return fmt.Errorf("Unable to unmarshal response: %s", err)
	}
	users := response.value
	for key, user := range users {
		if slices.Contains(h.ignoreList, user.userPrincipalName) {
			users[key] = users[len(users)-1]
			users = users[:len(users)-1]
		}
	}
	h.users = users
	return nil
}

// Returns list of users in Azure AD
func (h *AzureADSyncHandler) getUsernameList() []azureADUser {
	return h.users

}

// Set a new ignore list
func (h *AzureADSyncHandler) setIgnoreList(ignoreList []string) {
	h.ignoreList = ignoreList
}

func New(clientId, clientSecret, token, authUrl, azureGroupId string, ignoreList []string) (*AzureADSyncHandler, error) {
	h := AzureADSyncHandler{clientId, clientSecret, token, authUrl, azureGroupId, ignoreList, http.Client{Timeout: 30 * time.Second}, nil}
	if err := h.fetchApiToken(); err != nil {
		return nil, err
	}
	if err := h.syncUsers(); err != nil {
		return nil, err
	}
	return &h, nil
}
