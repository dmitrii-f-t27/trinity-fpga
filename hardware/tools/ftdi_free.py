#!/usr/bin/env python3
"""
ftdi_free.py — Free FTDI device from AppleSerialShim by terminating the IOKit service.
Uses ctypes to call IOKit framework directly. May work where kextunload fails.

Must run as root (use via trinity_flashed daemon or sudo).
"""
import ctypes
import ctypes.util
import sys

# Load IOKit framework
IOKIT = ctypes.CDLL(ctypes.util.find_library("IOKit"))
CORE_FOUNDATION = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))

# Types
kIOMasterPortDefault = 0
kCFStringEncodingUTF8 = 0x08000100
kCFNumberSInt32Type = 3

# IOKit functions
IOKIT.IOMasterPort.restype = ctypes.c_int
IOKIT.IOMasterPort.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]

IOKIT.IOServiceMatching.restype = ctypes.c_void_p
IOKIT.IOServiceMatching.argtypes = [ctypes.c_char_p]

IOKIT.IOServiceGetMatchingService.restype = ctypes.c_void_p
IOKIT.IOServiceGetMatchingService.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

IOKIT.IOServiceGetMatchingServices.restype = ctypes.c_int
IOKIT.IOServiceGetMatchingServices.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

IOKIT.IOIteratorNext.restype = ctypes.c_void_p
IOKIT.IOIteratorNext.argtypes = [ctypes.c_void_p]

IOKIT.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
IOKIT.IORegistryEntryCreateCFProperty.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]

IOKIT.IOServiceTerminate.restype = ctypes.c_int
IOKIT.IOServiceTerminate.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

IOKIT.IOObjectRelease.argtypes = [ctypes.c_void_p]
IOKIT.IOObjectRelease.restype = ctypes.c_int

IOKIT.IOObjectGetClass.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
IOKIT.IOObjectGetClass.restype = ctypes.c_int

# CoreFoundation functions
CORE_FOUNDATION.CFStringCreateWithCString.restype = ctypes.c_void_p
CORE_FOUNDATION.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]

CORE_FOUNDATION.CFRelease.argtypes = [ctypes.c_void_p]

CORE_FOUNDATION.CFNumberGetValue.restype = ctypes.c_bool
CORE_FOUNDATION.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_int32)]

def cf_string(s):
    return CORE_FOUNDATION.CFStringCreateWithCString(None, s.encode(), kCFStringEncodingUTF8)

def get_int_property(service, key):
    cf_key = cf_string(key)
    cf_val = IOKIT.IORegistryEntryCreateCFProperty(service, cf_key, None, 0)
    CORE_FOUNDATION.CFRelease(cf_key)
    if not cf_val:
        return None
    val = ctypes.c_int32(0)
    if CORE_FOUNDATION.CFNumberGetValue(cf_val, kCFNumberSInt32Type, ctypes.byref(val)):
        CORE_FOUNDATION.CFRelease(cf_val)
        return val.value
    CORE_FOUNDATION.CFRelease(cf_val)
    return None

def get_class(service):
    buf = ctypes.create_string_buffer(256)
    IOKIT.IOObjectGetClass(service, buf)
    return buf.value.decode()

def main():
    master_port = ctypes.c_void_p()
    IOKIT.IOMasterPort(0, ctypes.byref(master_port))

    # Find AppleSerialShim services
    matching = IOKIT.IOServiceMatching(b"AppleSerialShim")
    if not matching:
        print("ERROR: IOServiceMatching failed for AppleSerialShim")
        return False

    iterator = ctypes.c_void_p()
    kr = IOKIT.IOServiceGetMatchingServices(master_port, matching, ctypes.byref(iterator))
    if kr != 0:
        print(f"ERROR: IOServiceGetMatchingServices failed (kr={kr})")
        return False

    terminated = 0
    while True:
        service = IOKIT.IOIteratorNext(iterator)
        if not service:
            break

        cls = get_class(service)
        # Check if this service is attached to our FTDI (VID=0x0403, PID=0x6014)
        vid = get_int_property(service, "idVendor")
        pid = get_int_property(service, "idProduct")

        if vid == 0x0403 and pid == 0x6014:
            print(f"Found AppleSerialShim for FTDI (VID={vid:#x} PID={pid:#x}), terminating...")
            kr = IOKIT.IOServiceTerminate(service, 0)
            if kr == 0:
                print(f"  SUCCESS: service terminated (kr=0)")
                terminated += 1
            else:
                print(f"  FAIL: IOServiceTerminate returned kr={kr}")
        else:
            print(f"  Skip: {cls} (VID={vid}, PID={pid})")

        IOKIT.IOObjectRelease(service)

    IOKIT.IOObjectRelease(iterator)
    print(f"\nTerminated {terminated} AppleSerialShim service(s)")
    return terminated > 0

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
