#ifndef WIN32_NO_STATUS
#include <ntstatus.h>
#define WIN32_NO_STATUS
#endif

#include <unknwn.h>
#include <new>
#include <shlwapi.h>
#include "JarvisCredential.h"

CJarvisCredential::CJarvisCredential()
    : _refCount(1),
      _usageScenario(CPUS_LOGON),
      _events(nullptr)
{
    ZeroMemory(_fieldStrings, sizeof(_fieldStrings));
    DllAddRef();
}

CJarvisCredential::~CJarvisCredential()
{
    for (DWORD i = 0; i < JFI_NUM_FIELDS; ++i)
    {
        CoTaskMemFree(_fieldStrings[i]);
    }
    if (_events != nullptr)
    {
        _events->Release();
    }
    DllRelease();
}

ULONG CJarvisCredential::AddRef()
{
    return static_cast<ULONG>(InterlockedIncrement(&_refCount));
}

ULONG CJarvisCredential::Release()
{
    const long count = InterlockedDecrement(&_refCount);
    if (count == 0)
    {
        delete this;
    }
    return static_cast<ULONG>(count);
}

HRESULT CJarvisCredential::QueryInterface(REFIID riid, void **ppv)
{
    if (ppv == nullptr)
    {
        return E_POINTER;
    }
    *ppv = nullptr;
    if (riid == IID_IUnknown || riid == IID_ICredentialProviderCredential)
    {
        *ppv = static_cast<ICredentialProviderCredential *>(this);
    }
    else if (riid == IID_ICredentialProviderCredential2)
    {
        *ppv = static_cast<ICredentialProviderCredential2 *>(this);
    }
    else if (riid == IID_ICredentialProviderCredentialWithFieldOptions)
    {
        *ppv = static_cast<ICredentialProviderCredentialWithFieldOptions *>(this);
    }
    else
    {
        return E_NOINTERFACE;
    }
    AddRef();
    return S_OK;
}

HRESULT CJarvisCredential::Initialize(CREDENTIAL_PROVIDER_USAGE_SCENARIO usageScenario)
{
    _usageScenario = usageScenario;
    HRESULT hr = SHStrDupW(L"JARVIS", &_fieldStrings[JFI_TITLE]);
    if (SUCCEEDED(hr))
    {
        hr = SHStrDupW(L"Microfone: aguardando o login do Windows", &_fieldStrings[JFI_STATUS]);
    }
    if (SUCCEEDED(hr))
    {
        hr = SHStrDupW(L"Use Windows Hello ou PIN para entrar; a voz inicia depois", &_fieldStrings[JFI_INSTRUCTION]);
    }
    return hr;
}

HRESULT CJarvisCredential::Advise(ICredentialProviderCredentialEvents *events)
{
    if (events == nullptr)
    {
        return E_POINTER;
    }
    if (_events != nullptr)
    {
        _events->Release();
    }
    _events = events;
    _events->AddRef();
    return S_OK;
}

HRESULT CJarvisCredential::UnAdvise()
{
    if (_events != nullptr)
    {
        _events->Release();
        _events = nullptr;
    }
    return S_OK;
}

HRESULT CJarvisCredential::SetSelected(BOOL *autoLogon)
{
    if (autoLogon == nullptr)
    {
        return E_POINTER;
    }
    *autoLogon = FALSE;
    return S_OK;
}

HRESULT CJarvisCredential::SetDeselected()
{
    return S_OK;
}

HRESULT CJarvisCredential::GetFieldState(
    DWORD fieldId,
    CREDENTIAL_PROVIDER_FIELD_STATE *state,
    CREDENTIAL_PROVIDER_FIELD_INTERACTIVE_STATE *interactive)
{
    if (state == nullptr || interactive == nullptr || fieldId >= JFI_NUM_FIELDS)
    {
        return E_INVALIDARG;
    }
    *state = s_rgFieldStatePairs[fieldId].state;
    *interactive = s_rgFieldStatePairs[fieldId].interactive;
    return S_OK;
}

HRESULT CJarvisCredential::GetStringValue(DWORD fieldId, PWSTR *value)
{
    if (value == nullptr || fieldId >= JFI_NUM_FIELDS || fieldId == JFI_TILE_IMAGE)
    {
        return E_INVALIDARG;
    }
    *value = nullptr;
    return SHStrDupW(_fieldStrings[fieldId], value);
}

HRESULT CJarvisCredential::GetBitmapValue(DWORD fieldId, HBITMAP *bitmap)
{
    if (bitmap == nullptr || fieldId != JFI_TILE_IMAGE)
    {
        return E_INVALIDARG;
    }
    *bitmap = LoadBitmapW(HINST_THISDLL, MAKEINTRESOURCEW(IDB_JARVIS_TILE));
    return *bitmap != nullptr ? S_OK : HRESULT_FROM_WIN32(GetLastError());
}

HRESULT CJarvisCredential::GetCheckboxValue(DWORD, BOOL *, PWSTR *)
{
    return E_INVALIDARG;
}

HRESULT CJarvisCredential::GetComboBoxValueCount(DWORD, DWORD *, DWORD *)
{
    return E_INVALIDARG;
}

HRESULT CJarvisCredential::GetComboBoxValueAt(DWORD, DWORD, PWSTR *)
{
    return E_INVALIDARG;
}

HRESULT CJarvisCredential::GetSubmitButtonValue(DWORD, DWORD *)
{
    return E_INVALIDARG;
}

HRESULT CJarvisCredential::SetStringValue(DWORD, PCWSTR)
{
    return E_INVALIDARG;
}

HRESULT CJarvisCredential::SetCheckboxValue(DWORD, BOOL)
{
    return E_INVALIDARG;
}

HRESULT CJarvisCredential::SetComboBoxSelectedValue(DWORD, DWORD)
{
    return E_INVALIDARG;
}

HRESULT CJarvisCredential::CommandLinkClicked(DWORD)
{
    return E_INVALIDARG;
}

HRESULT CJarvisCredential::GetSerialization(
    CREDENTIAL_PROVIDER_GET_SERIALIZATION_RESPONSE *response,
    CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION *serialization,
    PWSTR *statusText,
    CREDENTIAL_PROVIDER_STATUS_ICON *statusIcon)
{
    if (response == nullptr || serialization == nullptr || statusText == nullptr || statusIcon == nullptr)
    {
        return E_POINTER;
    }
    *response = CPGSR_NO_CREDENTIAL_NOT_FINISHED;
    *statusText = nullptr;
    *statusIcon = CPSI_WARNING;
    ZeroMemory(serialization, sizeof(*serialization));
    SHStrDupW(L"Este bloco visual nao autentica. Use Windows Hello ou PIN.", statusText);
    return S_OK;
}

HRESULT CJarvisCredential::ReportResult(
    NTSTATUS,
    NTSTATUS,
    PWSTR *statusText,
    CREDENTIAL_PROVIDER_STATUS_ICON *statusIcon)
{
    if (statusText == nullptr || statusIcon == nullptr)
    {
        return E_POINTER;
    }
    *statusText = nullptr;
    *statusIcon = CPSI_NONE;
    return S_OK;
}

HRESULT CJarvisCredential::GetUserSid(PWSTR *sid)
{
    if (sid == nullptr)
    {
        return E_POINTER;
    }
    *sid = nullptr;
    return S_FALSE;
}

HRESULT CJarvisCredential::GetFieldOptions(
    DWORD,
    CREDENTIAL_PROVIDER_CREDENTIAL_FIELD_OPTIONS *options)
{
    if (options == nullptr)
    {
        return E_POINTER;
    }
    *options = CPCFO_NONE;
    return S_OK;
}
