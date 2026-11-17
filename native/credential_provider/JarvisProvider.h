#pragma once

#include <windows.h>
#include <credentialprovider.h>
#include "common.h"
#include "JarvisCredential.h"
#include "dll.h"

class CJarvisProvider final : public ICredentialProvider
{
public:
    CJarvisProvider();

    // IUnknown
    IFACEMETHODIMP_(ULONG) AddRef();
    IFACEMETHODIMP_(ULONG) Release();
    IFACEMETHODIMP QueryInterface(REFIID riid, void **ppv);

    // ICredentialProvider
    IFACEMETHODIMP SetUsageScenario(CREDENTIAL_PROVIDER_USAGE_SCENARIO usageScenario, DWORD flags);
    IFACEMETHODIMP SetSerialization(const CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION *serialization);
    IFACEMETHODIMP Advise(ICredentialProviderEvents *events, UINT_PTR adviseContext);
    IFACEMETHODIMP UnAdvise();
    IFACEMETHODIMP GetFieldDescriptorCount(DWORD *count);
    IFACEMETHODIMP GetFieldDescriptorAt(DWORD index, CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR **descriptor);
    IFACEMETHODIMP GetCredentialCount(DWORD *count, DWORD *defaultIndex, BOOL *autoLogon);
    IFACEMETHODIMP GetCredentialAt(DWORD index, ICredentialProviderCredential **credential);

private:
    ~CJarvisProvider();
    long _refCount;
    CREDENTIAL_PROVIDER_USAGE_SCENARIO _usageScenario;
    CJarvisCredential *_credential;
};

HRESULT CJarvis_CreateInstance(REFIID riid, void **ppv);
