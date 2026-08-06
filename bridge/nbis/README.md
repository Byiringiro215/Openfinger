# NBIS binaries — NIST Biometric Image Software

This folder ships two NIST Biometric Image Software (NBIS) binaries:

```
mindtct.exe     — minutiae extractor
bozorth3.exe    — fingerprint matcher
```

Both are used by `pipeline/nbis.py` as the biometric-grade matcher backend
(the default when `USE_NBIS_MATCHER=True` in `pipeline_config.py`).

## License

NBIS was developed by NIST under the NIST Image Group and is **released to
the public domain** — you are free to use, copy, modify, and redistribute
without restriction. See the [NIST NBIS documentation](https://www.nist.gov/services-resources/software/nist-biometric-image-software-nbis)
and NIST Special Publication 500-290 for the full statement.

## If your binaries are missing

Set `NBIS_PATH` to the directory containing the binaries, or rebuild:

### Option 1 — pre-built binaries

Look for a recent NBIS Windows build on GitHub (search `nbis-windows` or
`NBIS-5.0.0`). Drop `mindtct.exe` and `bozorth3.exe` into this folder.

### Option 2 — build under WSL

```bash
sudo apt update && sudo apt install build-essential cmake
git clone https://github.com/lessandro/nbis.git
cd nbis
./setup.sh /usr/local
make config && make it
sudo make install LIBDIR=/usr/local/lib INCLUDEDIR=/usr/local/include
```

Copy `/usr/local/bin/{mindtct,bozorth3}` here and rename with `.exe`, or set
`NBIS_PATH=/usr/local/bin` and run the pipeline under WSL directly.

## Sanity check

```powershell
python -c "from pipeline.nbis import is_available; print('NBIS ready:', is_available())"
```
