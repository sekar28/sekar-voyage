"""API keys in the Windows Credential Manager (encrypted for the signed-in user) - never in a plain file."""

import ctypes
from ctypes import wintypes

PREFIX = "SystemUtilities/"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


class CREDENTIALW(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR)]


_advapi = ctypes.WinDLL("advapi32", use_last_error=True)
_advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
_advapi.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
_advapi.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
_advapi.CredFree.argtypes = [ctypes.c_void_p]


def set_secret(name, value):
    blob = value.encode("utf-16-le")
    buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    cred = CREDENTIALW(Type=CRED_TYPE_GENERIC, TargetName=PREFIX + name, CredentialBlobSize=len(blob),
                       CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)),
                       Persist=CRED_PERSIST_LOCAL_MACHINE, UserName="api-key")
    if not _advapi.CredWriteW(ctypes.byref(cred), 0):
        raise ctypes.WinError(ctypes.get_last_error())


def get_secret(name):
    p = ctypes.POINTER(CREDENTIALW)()
    if not _advapi.CredReadW(PREFIX + name, CRED_TYPE_GENERIC, 0, ctypes.byref(p)):
        return None
    try:
        c = p.contents
        return ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize).decode("utf-16-le")
    finally:
        _advapi.CredFree(p)


def delete_secret(name):
    _advapi.CredDeleteW(PREFIX + name, CRED_TYPE_GENERIC, 0)


def hint(value):
    """What the UI may show of a key: never the key itself."""
    return f"••••{value[-4:]}" if value and len(value) > 8 else ("••••" if value else "")
