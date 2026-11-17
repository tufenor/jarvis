#include <new>
#include <shlwapi.h>
#include "JarvisProvider.h"

CJarvisProvider::CJarvisProvider()
    : _refCount(1),
      _usageScenario(CPUS_LOGON),
      _credential(nullptr)
{
    DllAddRef();
}

CJarvisProvider::~CJarvisProvider()
{
    if (_credential != nullptr)
    {
        _credential->Release();
    }
    DllRelease();
}

ULONG CJarvisProvider::AddRef()
{
    return static_cast<ULONG>(InterlockedIncrement(&_refCount));
}

ULONG CJarvisProvider::Release()
{
    const long count = InterlockedDecrement(&_refCount);
    if (count == 0)
    {
        delete this;
    }
    return static_cast<ULONG>(count);
}

HRESULT CJarvisProvider::QueryInterface(REFIID riid, void **ppv)
{
    if (ppv == nullptr)
    {
        return E_POINTER;
    }
    *ppv = nullptr;
    if (riid == IID_IUnknown || riid == IID_ICredentialProvider)
    {
        *ppv = static_cast<ICredentialProvider *>(this);
        AddRef();
        return S_OK;
    }
    return E_NOINTERFACE;
}

HRESULT CJarvisProvider::SetUsageScenario(CREDENTIAL_PROVIDER_USAGE_SCENARIO usageScenario, DWORD)
{
    if (usageScenario != CPUS_LOGON && usageScenario != CPUS_UNLOCK_WORKSTATION)
    {
        return E_NOTIMPL;
    }
    _usageScenario = usageScenario;
    if (_credential != nullptr)
    {
        _credential->Release();
        _credential = nullptr;
    }
    return S_OK;
}

HRESULT CJarvisProvider::SetSerialization(const CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION *)
{
    return E_NOTIMPL;
}

HRESULT CJarvisProvider::Advise(ICredentialProviderEvents *, UINT_PTR)
{
    return S_OK;
}

HRESULT CJarvisProvider::UnAdvise()
{
    return S_OK;
}

HRESULT CJarvisProvider::GetFieldDescriptorCount(DWORD *count)
{
    if (count == nullptr)
    {
        return E_POINTER;
    }
    *count = JFI_NUM_FIELDS;
    return S_OK;
}

HRESULT CJarvisProvider::GetFieldDescriptorAt(
    DWORD index,
    CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR **descriptor)
{
    if (descriptor == nullptr || index >= JFI_NUM_FIELDS)
    {
        return E_INVALIDARG;
    }
    *descriptor = static_cast<CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR *>(
        CoTaskMemAlloc(sizeof(CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR)));
    if (*descriptor == nullptr)
    {
        return E_OUTOFMEMORY;
    }
    (*descriptor)->dwFieldID = s_rgFieldDescriptors[index].dwFieldID;
    (*descriptor)->cpft = s_rgFieldDescriptors[index].cpft;
    (*descriptor)->guidFieldType = s_rgFieldDescriptors[index].guidFieldType;
    const HRESULT hr = SHStrDupW(s_rgFieldDescriptors[index].pszLabel, &(*descriptor)->pszLabel);
    if (FAILED(hr))
    {
        CoTaskMemFree(*descriptor);
        *descriptor = nullptr;
    }
    return hr;
}

HRESULT CJarvisProvider::GetCredentialCount(
    DWORD *count,
    DWORD *defaultIndex,
    BOOL *autoLogon)
{
    if (count == nullptr || defaultIndex == nullptr || autoLogon == nullptr)
    {
        return E_POINTER;
    }
    if (_credential == nullptr)
    {
        _credential = new (std::nothrow) CJarvisCredential();
        if (_credential == nullptr)
        {
            return E_OUTOFMEMORY;
        }
        const HRESULT hr = _credential->Initialize(_usageScenario);
        if (FAILED(hr))
        {
            _credential->Release();
            _credential = nullptr;
            return hr;
        }
    }
    *count = 1;
    *defaultIndex = CREDENTIAL_PROVIDER_NO_DEFAULT;
    *autoLogon = FALSE;
    return S_OK;
}

HRESULT CJarvisProvider::GetCredentialAt(
    DWORD index,
    ICredentialProviderCredential **credential)
{
    if (credential == nullptr)
    {
        return E_POINTER;
    }
    *credential = nullptr;
    if (index != 0 || _credential == nullptr)
    {
        return E_INVALIDARG;
    }
    return _credential->QueryInterface(IID_PPV_ARGS(credential));
}

HRESULT CJarvis_CreateInstance(REFIID riid, void **ppv)
{
    if (ppv == nullptr)
    {
        return E_POINTER;
    }
    *ppv = nullptr;
    CJarvisProvider *provider = new (std::nothrow) CJarvisProvider();
    if (provider == nullptr)
    {
        return E_OUTOFMEMORY;
    }
    const HRESULT hr = provider->QueryInterface(riid, ppv);
    provider->Release();
    return hr;
}
