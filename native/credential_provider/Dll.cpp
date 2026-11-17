#include <windows.h>
#include <unknwn.h>
#include <strsafe.h>
#include <string>
#include "Dll.h"
#include "JarvisProvider.h"
#include "guid.h"

static long g_cRef = 0;
HINSTANCE g_hinst = nullptr;

class CClassFactory final : public IClassFactory
{
public:
    CClassFactory() : _refCount(1) {}

    IFACEMETHODIMP_(ULONG) AddRef() override
    {
        return static_cast<ULONG>(InterlockedIncrement(&_refCount));
    }

    IFACEMETHODIMP_(ULONG) Release() override
    {
        const long count = InterlockedDecrement(&_refCount);
        if (count == 0)
        {
            delete this;
        }
        return static_cast<ULONG>(count);
    }

    IFACEMETHODIMP QueryInterface(REFIID riid, void **ppv) override
    {
        if (ppv == nullptr)
        {
            return E_POINTER;
        }
        *ppv = nullptr;
        if (riid == IID_IUnknown || riid == IID_IClassFactory)
        {
            *ppv = static_cast<IClassFactory *>(this);
            AddRef();
            return S_OK;
        }
        return E_NOINTERFACE;
    }

    IFACEMETHODIMP CreateInstance(IUnknown *outer, REFIID riid, void **ppv) override
    {
        if (outer != nullptr)
        {
            if (ppv != nullptr) *ppv = nullptr;
            return CLASS_E_NOAGGREGATION;
        }
        return CJarvis_CreateInstance(riid, ppv);
    }

    IFACEMETHODIMP LockServer(BOOL lock) override
    {
        if (lock) DllAddRef(); else DllRelease();
        return S_OK;
    }

private:
    ~CClassFactory() = default;
    long _refCount;
};

void DllAddRef()
{
    InterlockedIncrement(&g_cRef);
}

void DllRelease()
{
    InterlockedDecrement(&g_cRef);
}

STDAPI DllCanUnloadNow()
{
    return g_cRef == 0 ? S_OK : S_FALSE;
}

STDAPI DllGetClassObject(REFCLSID rclsid, REFIID riid, void **ppv)
{
    if (ppv == nullptr)
    {
        return E_POINTER;
    }
    *ppv = nullptr;
    if (rclsid != CLSID_CJarvis)
    {
        return CLASS_E_CLASSNOTAVAILABLE;
    }
    CClassFactory *factory = new (std::nothrow) CClassFactory();
    if (factory == nullptr)
    {
        return E_OUTOFMEMORY;
    }
    const HRESULT hr = factory->QueryInterface(riid, ppv);
    factory->Release();
    return hr;
}

static HRESULT GetClsidText(wchar_t *text, size_t count)
{
    return StringFromGUID2(CLSID_CJarvis, text, static_cast<int>(count)) > 0
        ? S_OK : E_FAIL;
}

static HRESULT SetDefaultValue(HKEY root, const std::wstring &subkey, const std::wstring &value)
{
    HKEY key = nullptr;
    const LONG result = RegCreateKeyExW(root, subkey.c_str(), 0, nullptr, 0,
        KEY_WRITE, nullptr, &key, nullptr);
    if (result != ERROR_SUCCESS)
    {
        return HRESULT_FROM_WIN32(result);
    }
    const LONG setResult = RegSetValueExW(key, nullptr, 0, REG_SZ,
        reinterpret_cast<const BYTE *>(value.c_str()),
        static_cast<DWORD>((value.size() + 1) * sizeof(wchar_t)));
    RegCloseKey(key);
    return HRESULT_FROM_WIN32(setResult);
}

static HRESULT SetNamedValue(HKEY root, const std::wstring &subkey,
    const wchar_t *name, const std::wstring &value)
{
    HKEY key = nullptr;
    const LONG result = RegCreateKeyExW(root, subkey.c_str(), 0, nullptr, 0,
        KEY_WRITE, nullptr, &key, nullptr);
    if (result != ERROR_SUCCESS)
    {
        return HRESULT_FROM_WIN32(result);
    }
    const LONG setResult = RegSetValueExW(key, name, 0, REG_SZ,
        reinterpret_cast<const BYTE *>(value.c_str()),
        static_cast<DWORD>((value.size() + 1) * sizeof(wchar_t)));
    RegCloseKey(key);
    return HRESULT_FROM_WIN32(setResult);
}

STDAPI DllRegisterServer()
{
    wchar_t clsidText[64] = {};
    wchar_t modulePath[MAX_PATH * 4] = {};
    if (FAILED(GetClsidText(clsidText, ARRAYSIZE(clsidText))) ||
        GetModuleFileNameW(g_hinst, modulePath, ARRAYSIZE(modulePath)) == 0)
    {
        return HRESULT_FROM_WIN32(GetLastError());
    }

    const std::wstring clsid = clsidText;
    const std::wstring clsidKey = L"SOFTWARE\\Classes\\CLSID\\" + clsid;
    const std::wstring inprocKey = clsidKey + L"\\InprocServer32";
    const std::wstring providerKey =
        L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Authentication\\Credential Providers\\" + clsid;

    HRESULT hr = SetDefaultValue(HKEY_LOCAL_MACHINE, clsidKey, L"JARVIS Voice Tile");
    if (SUCCEEDED(hr)) hr = SetDefaultValue(HKEY_LOCAL_MACHINE, inprocKey, modulePath);
    if (SUCCEEDED(hr)) hr = SetNamedValue(HKEY_LOCAL_MACHINE, inprocKey, L"ThreadingModel", L"Apartment");
    if (SUCCEEDED(hr)) hr = SetDefaultValue(HKEY_LOCAL_MACHINE, providerKey, L"JARVIS Voice Tile");
    return hr;
}

static void DeleteTree(HKEY root, const std::wstring &subkey)
{
    RegDeleteTreeW(root, subkey.c_str());
}

STDAPI DllUnregisterServer()
{
    wchar_t clsidText[64] = {};
    if (FAILED(GetClsidText(clsidText, ARRAYSIZE(clsidText))))
    {
        return E_FAIL;
    }
    const std::wstring clsid = clsidText;
    DeleteTree(HKEY_LOCAL_MACHINE,
        L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Authentication\\Credential Providers\\" + clsid);
    DeleteTree(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Classes\\CLSID\\" + clsid);
    return S_OK;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(instance);
        g_hinst = instance;
    }
    return TRUE;
}
