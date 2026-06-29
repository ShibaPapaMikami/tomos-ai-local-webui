using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace Gemma4Launcher
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            string mode = args.Length > 0 ? args[0].ToLowerInvariant() : "web";
            string batchFile;

            switch (mode)
            {
                case "all":
                    batchFile = "Gemma4_12B_All_Start.bat";
                    break;
                case "stop-heavy":
                    batchFile = "Gemma4_12B_Stop_Heavy.bat";
                    break;
                case "web":
                default:
                    batchFile = "Gemma4_12B_Web.bat";
                    break;
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string batchPath = Path.Combine(baseDir, batchFile);
            if (!File.Exists(batchPath))
            {
                MessageBox.Show(
                    batchFile + " が見つかりません。Gemma4_12B を再インストールしてください。",
                    "Gemma4 12B",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }

            try
            {
                var info = new ProcessStartInfo
                {
                    FileName = "cmd.exe",
                    Arguments = "/c start \"\" /min \"" + batchPath + "\"",
                    WorkingDirectory = baseDir,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                Process.Start(info);
                return 0;
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "起動できませんでした。\n\n" + ex.Message,
                    "Gemma4 12B",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }
        }
    }
}
