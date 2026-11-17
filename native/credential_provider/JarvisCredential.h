#pragma once

#include <windows.h>
#include <credentialprovider.h>
#include "common.h"
#include "dll.h"
#include "resource.h"

class CJarvisCredential final : public ICredentialProviderCredential2,
                                public ICredentialProviderCredentialWithFieldOptions
{
public:
    CJarvisCredential();

    // IUnknown
    IFACEMETHODIMP_(ULONG) AddRef();
    IFACEMETHODIMP_(ULONG) Release();
    IFACEMETHODIMP QueryInterface(REFIID riid, void **ppv);

    // ICredentialProviderCredential
    IFACEMETHODIMP Advise(ICredentialProviderCredentialEvents *events);
    IFACEMETHODIMP UnAdvise();
    IFACEMETHODIMP SetSelected(BOOL *autoLogon);
    IFACEMETHODIMP SetDeselected();
    IFACEMETHODIMP GetFieldState(DWORD fieldId,
        CREDENTIAL_PROVIDER_FIELD_STATE *state,
        CREDENTIAL_PROVIDER_FIELD_INTERACTIVE_STATE *interactive);
    IFACEMETHODIMP GetStringValue(DWORD fieldId, PWSTR *value);
    IFACEMETHODIMP GetBitmapValue(DWORD fieldId, HBITMAP *bitmap);
    IFACEMETHODIMP GetCheckboxValue(DWORD fieldId, BOOL *checked, PWSTR *label);
    IFACEMETHODIMP GetComboBoxValueCount(DWORD fieldId, DWORD *count, DWORD *selected);
    IFACEMETHODIMP GetComboBoxValueAt(DWORD fieldId, DWORD item, PWSTR *value);
    IFACEMETHODIMP GetSubmitButtonValue(DWORD fieldId, DWORD *adjacentTo);
    IFACEMETHODIMP SetStringValue(DWORD fieldId, PCWSTR value);
    IFACEMETHODIMP SetCheckboxValue(DWORD fieldId, BOOL checked);
    IFACEMETHODIMP SetComboBoxSelectedValue(DWORD fieldId, DWORD selected);
    IFACEMETHODIMP CommandLinkClicked(DWORD fieldId);
    IFACEMETHODIMP GetSerialization(
        CREDENTIAL_PROVIDER_GET_SERIALIZATION_RESPONSE *response,
        CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION *serialization,
        PWSTR *statusText,
        CREDENTIAL_PROVIDER_STATUS_ICON *statusIcon);
    IFACEMETHODIMP ReportResult(NTSTATUS status, NTSTATUS substatus,
        PWSTR *statusText, CREDENTIAL_PROVIDER_STATUS_ICON *statusIcon);

    // ICredentialProviderCredential2
    IFACEMETHODIMP GetUserSid(PWSTR *sid);

    // ICredentialProviderCredentialWithFieldOptions
    IFACEMETHODIMP GetFieldOptions(DWORD fieldId,
        CREDENTIAL_PROVIDER_CREDENTIAL_FIELD_OPTIONS *options);

    HRESULT Initialize(CREDENTIAL_PROVIDER_USAGE_SCENARIO usageScenario);

private:
    ~CJarvisCredential();
    long _refCount;
    CREDENTIAL_PROVIDER_USAGE_SCENARIO _usageScenario;
    PWSTR _fieldStrings[JFI_NUM_FIELDS];
    ICredentialProviderCredentialEvents *_events;
};
