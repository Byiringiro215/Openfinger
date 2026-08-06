/*
 * FingerprintBridge.exe  —  openfinger capture bridge (DigitalPersona U.are.U)
 *
 * Uses the DigitalPersona DPFP managed SDK (DPFPDevNET.dll + DPFPShrNET.dll),
 * which drives the U.are.U 4500 through its "Authentication Devices" driver.
 * WBF (Windows Biometric Framework) is NOT used — the U.are.U 4500 is not a
 * WBF biometric unit.
 *
 * Each fingerprint capture is streamed as one JSON line on stdout:
 *   {"type":"status","status":"ready"}
 *   {"type":"scan","width":-1,"height":3,"data":"<base64-png>"}
 *   {"type":"error","code":"...","message":"..."}
 *
 * Modes:
 *   --pipe-server : Named-pipe server for scheduled-task / service path
 *   (no args)     : Write JSON directly to stdout (parent-process spawn path)
 *
 * Build:
 *   build.bat        (Windows, .NET Framework 4.x + csc.exe)
 */

using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.IO.Pipes;
using System.Threading;
using DPFP;
using DPFP.Capture;

namespace OpenFinger.Bridge
{
    static class Program
    {
        // Pipe / mutex identifiers — kept generic so any host process can attach.
        const string PIPE_NAME  = "OpenFingerCapture";
        const string MUTEX_NAME = "OpenFingerBridgeSingleton";

        #region JSON output helpers

        static readonly object WriteLock = new object();

        static void WriteJson(string json)
        {
            lock (WriteLock)
            {
                Console.WriteLine(json);
                Console.Out.Flush();
            }
        }

        static string Esc(string s)
        {
            if (s == null) return "";
            return s.Replace("\\", "\\\\")
                    .Replace("\"", "\\\"")
                    .Replace("\r", "\\r")
                    .Replace("\n", "\\n");
        }

        static void WriteStatus(string status)
        {
            WriteJson("{\"type\":\"status\",\"status\":\"" + Esc(status) + "\"}");
        }

        static void WriteError(string code, string message)
        {
            WriteJson("{\"type\":\"error\",\"code\":\"" + Esc(code) + "\",\"message\":\"" + Esc(message) + "\"}");
        }

        static void WriteScan(int width, int height, byte[] data)
        {
            string b64 = Convert.ToBase64String(data);
            WriteJson("{\"type\":\"scan\",\"width\":" + width + ",\"height\":" + height + ",\"data\":\"" + b64 + "\"}");
        }

        static void WriteDebug(string msg)
        {
            lock (WriteLock)
            {
                Console.WriteLine("[Bridge] " + msg);
                Console.Out.Flush();
            }
        }

        #endregion

        #region DPFP capture

        class DpfpCapture : DPFP.Capture.EventHandler
        {
            private Capture _cap;
            private volatile bool _running = true;

            public void Run()
            {
                try
                {
                    _cap = new Capture(Priority.Low);
                    _cap.EventHandler = this;
                    _cap.StartCapture();
                    WriteDebug("DPFP capture started (U.are.U series)");
                    WriteStatus("ready");

                    while (_running)
                    {
                        Thread.Sleep(300);
                        try { Console.Out.Flush(); }
                        catch (IOException) { _running = false; }
                    }
                }
                catch (Exception ex)
                {
                    WriteError("DPFP_INIT_ERROR",
                        "Failed to start fingerprint reader: " + ex.Message +
                        " — ensure the U.are.U reader is plugged in and the DigitalPersona driver is installed.");
                }
                finally
                {
                    if (_cap != null) try { _cap.StopCapture(); } catch { }
                }
            }

            public void OnComplete(object capture, string serial, Sample sample)
            {
                if (!_running) return;
                try
                {
                    WriteDebug("Finger captured — converting to PNG");
                    var conv = new SampleConversion();
                    Bitmap bmp = null;
                    conv.ConvertToPicture(sample, ref bmp);

                    if (bmp != null)
                    {
                        using (var ms = new MemoryStream())
                        {
                            bmp.Save(ms, ImageFormat.Png);
                            WriteScan(-1, 3, ms.ToArray());
                        }
                        bmp.Dispose();
                    }
                    else
                    {
                        WriteError("DPFP_NO_BITMAP",
                            "SampleConversion.ConvertToPicture returned null — SDK version mismatch?");
                    }
                }
                catch (IOException) { _running = false; }
                catch (Exception ex) { WriteError("DPFP_COMPLETE_ERROR", ex.Message); }
            }

            public void OnFingerGone(object capture, string serial) { }

            public void OnFingerTouch(object capture, string serial)
            {
                WriteDebug("Finger touched sensor");
            }

            public void OnReaderConnect(object capture, string serial)
            {
                WriteDebug("Reader connected: " + serial);
                try { WriteStatus("ready"); }
                catch (IOException) { _running = false; }
            }

            public void OnReaderDisconnect(object capture, string serial)
            {
                WriteDebug("Reader disconnected: " + serial);
                try { WriteStatus("disconnected"); }
                catch (IOException) { _running = false; }
            }

            public void OnSampleQuality(object capture, string serial, CaptureFeedback feedback) { }
        }

        #endregion

        #region Pipe-server mode

        static void RunPipeServer()
        {
            bool createdNew;
            using (var mutex = new Mutex(true, MUTEX_NAME, out createdNew))
            {
                if (!createdNew) return;

                while (true)
                {
                    NamedPipeServerStream pipe = null;
                    try
                    {
                        pipe = new NamedPipeServerStream(
                            PIPE_NAME,
                            PipeDirection.Out, 1,
                            PipeTransmissionMode.Byte,
                            PipeOptions.None);

                        pipe.WaitForConnection();
                        Console.SetOut(new StreamWriter(pipe) { AutoFlush = true });

                        new DpfpCapture().Run();
                    }
                    catch (IOException) { /* client disconnected — loop */ }
                    catch (Exception ex)
                    {
                        Console.Error.WriteLine("[PipeServer] " + ex.Message);
                    }
                    finally
                    {
                        Console.SetOut(TextWriter.Null);
                        if (pipe != null) try { pipe.Close(); } catch { }
                        Thread.Sleep(500);
                    }
                }
            }
        }

        #endregion

        static void Main(string[] args)
        {
            if (args.Length >= 1 && args[0] == "--pipe-server")
            {
                RunPipeServer();
                return;
            }
            new DpfpCapture().Run();
        }
    }
}
