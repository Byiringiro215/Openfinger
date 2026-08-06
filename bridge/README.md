# Capture bridge (Windows / DigitalPersona U.are.U)

`FingerprintBridge.exe` is a tiny .NET Framework 4.x program that wraps the
DigitalPersona **DPFP** managed SDK and streams each fingerprint capture as
one JSON line on stdout. The Python pipeline (`scanner/bridge_client.py`)
spawns it or attaches to its named pipe.

```
FingerprintBridge.exe
   │
   ├── DPFPDevNET.dll   ← DigitalPersona managed SDK (device layer)
   ├── DPFPShrNET.dll   ← DigitalPersona managed SDK (shared)
   │
   └── nbis/
         ├── mindtct.exe    ← NIST minutiae extractor
         └── bozorth3.exe   ← NIST fingerprint matcher
```

## What you need on your machine

1. **A DigitalPersona / HID U.are.U fingerprint reader.** This code was
   developed against the **U.are.U 4500** (USB, ~$70 second-hand). The
   U.are.U 5100 and 5300 use the same SDK and should also work; the newer
   HID DigitalPersona 4500-USB variant is identical.

2. **The DigitalPersona driver.** Windows will not enumerate the reader as
   a WBF biometric unit — you must install the vendor driver.
   * [HID DigitalPersona downloads](https://www.hidglobal.com/drivers)
   * Look for **"DigitalPersona U.are.U SDK — Windows"** or the
     **"HID Authentication Devices"** driver package.
   * After install, Device Manager should show
     **DigitalPersona U.are.U Fingerprint Reader** under a **Biometric**
     or **DigitalPersona** node.

3. **DPFP SDK DLLs** (`DPFPDevNET.dll`, `DPFPShrNET.dll`) — required to
   link `FingerprintBridge.exe`. These ship in this repo for convenience,
   but note that they are DigitalPersona / HID Global property under
   their SDK license. If you plan to redistribute, download them fresh
   from the vendor as part of the SDK install and keep the vendor
   attribution.

## Rebuilding FingerprintBridge.exe

Requires only the built-in .NET Framework compiler (installed with Windows).

```powershell
cd bridge
.\build.bat
```

This produces `FingerprintBridge.exe`. Run it directly to smoke-test:

```powershell
.\FingerprintBridge.exe
```

You should see JSON lines like:

```json
{"type":"status","status":"ready"}
{"type":"scan","width":-1,"height":3,"data":"iVBORw0KGgo..."}
```

Press Ctrl+C to stop.

## Porting to other readers

`FingerprintBridge.cs` is intentionally small (~200 LOC). To adapt to
another reader, replace the `DpfpCapture` class with the equivalent from
your reader's SDK — as long as the output remains one JSON line per event,
the Python side does not care which SDK produced it.

For non-Windows platforms:
- Under WSL / Linux, replace this exe with a `libfprint`-based Python
  capture module and use the same JSON event shape.
- Under macOS, no first-party U.are.U driver exists; run this exe in a
  Windows VM and forward captures over TCP.
