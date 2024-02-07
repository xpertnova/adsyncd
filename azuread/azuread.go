// This package handles requests to the Azure AD
package azuread

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"slices"
	"time"

	"github.com/xpertnova/adsyncd/config"
)

type AzureADSyncHandler struct {
	Config     *config.AzureADConfig
	token      string
	httpClient http.Client
	users      []AzureADUser
}

type authRequestData struct {
	GrantType    string `json:"grant_type"`
	ClientId     string `json:"client_id"`
	Scope        string `json:"scope"`
	ClientSecret string `json:"client_secret"`
}

type authRequestResponse struct {
	AccessToken string `json:"access_token"`
}

type userRequestResponse struct {
	Value []AzureADUser `json:"value"`
}

type AzureADUser struct {
	DisplayName       string `json:"displayName"`
	UserPrincipalName string `json:"userPrincipalName"`
}

// Get the API token from Azure AD
// Requires valid clientId and clientSecret
func (h *AzureADSyncHandler) fetchApiToken() error {
	log.Printf("[AzureAD] Fetching Azure AD API Token")
	data := authRequestData{
		"client_credentials",
		h.Config.ClientId,
		"https://graph.microsoft.com/.default",
		h.Config.ClientSecret}
	marshalled, err := json.Marshal(data)
	if err != nil {
		log.Printf("[AzureAD] Cannot serialize request data: %s", err)
		return fmt.Errorf("cannot serialize request data: %s", err)
	}
	req, err := http.NewRequest("POST", h.Config.AuthURL, bytes.NewReader(marshalled))
	if err != nil {
		log.Printf("[AzureAD] Cannot build request: %s", err)
		return fmt.Errorf("cannot build request: %s", err)
	}
	res, err := h.httpClient.Do(req)
	if err != nil {
		log.Printf("[AzureAD] Cannot send request: %s", err)
		return fmt.Errorf("cannot send request: %s", err)
	}
	if res.StatusCode != 200 {
		log.Printf("[AzureAD] Response failed with status code %d", res.StatusCode)
		return fmt.Errorf("response failed with status code %d", res.StatusCode)
	}
	defer res.Body.Close()
	resBody, err := io.ReadAll(res.Body)
	if err != nil {
		log.Printf("[AzureAD] Cannot read response body: %s", err)
		return fmt.Errorf("cannot read response body: %s", err)
	}
	var resMarshalled authRequestResponse
	json.Unmarshal(resBody, &resMarshalled)
	h.token = resMarshalled.AccessToken
	log.Printf("[AzureAD] Access token successfully fetched")
	return nil
}

// Get users from Azure AD
func (h *AzureADSyncHandler) SyncUsers() error {
	log.Printf("[AzureAD] Getting users from Azure AD")
	req, err := http.NewRequest("GET", "https://graph.microsoft.com/v1.0/groups/"+h.Config.AADGroupId+"/members?$select=displayName,userPrincipalName", nil)
	if err != nil {
		log.Printf("[AzureAD] Cannot build request: %s", err)
		return err
	}
	req.Header.Set("Content-Type", "application\\json")
	req.Header.Set("Authorization", "Bearer "+h.token)
	res, err := h.httpClient.Do(req)
	if err != nil {
		log.Printf("[AzureAD] Cannot fetch users: %s", err)
		return err
	}
	defer res.Body.Close()
	if res.StatusCode != 200 {
		if res.StatusCode == 403 {
			log.Printf("[AzureAD] Request failed with status code 403 - retrying with new API token")
			err := h.fetchApiToken()
			if err != nil {
				log.Printf("[AzureAD] New API token could not be fetched: %s", err)
				return err
			}
			h.SyncUsers()
		} else {
			log.Printf("[AzureAD] Request failed with error %d", err)
			return err
		}
	}
	resBody, err := io.ReadAll(res.Body)
	if err != nil {
		log.Printf("[AzureAD] Cannot read response: %s", err)
		return err
	}
	var response userRequestResponse
	err = json.Unmarshal(resBody, &response)
	if err != nil {
		log.Printf("[AzureAD] Unable to unmarshal response: %s", err)
		return err
	}
	users := response.Value
	for key, user := range users {
		if slices.Contains(h.Config.IgnoreList, user.UserPrincipalName) {
			users[key] = users[len(users)-1]
			users = users[:len(users)-1]
		}
	}
	h.users = users
	return nil
}

// Returns list of users in Azure AD
func (h *AzureADSyncHandler) GetUsernameList() []AzureADUser {
	return h.users
}

func New(c *config.AzureADConfig) (*AzureADSyncHandler, error) {
	h := AzureADSyncHandler{c, "", http.Client{Timeout: 30 * time.Second}, nil}
	if err := h.fetchApiToken(); err != nil {
		return nil, err
	}
	if err := h.SyncUsers(); err != nil {
		return nil, err
	}
	return &h, nil
}
