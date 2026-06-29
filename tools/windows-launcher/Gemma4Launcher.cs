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

            if (mode != "stop-heavy" && string.IsNullOrEmpty(FindOllamaExecutable()))
            {
                ShowOllamaInstallPrompt();
                return 1;
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

        private static string FindOllamaExecutable()
        {
            string pathResult = FindOnPath("ollama.exe");
            if (!string.IsNullOrEmpty(pathResult))
            {
                return pathResult;
            }

            string localAppData = Environment.GetEnvironmentVariable("LOCALAPPDATA") ?? "%LOCALAPPDATA%";
            string programFiles = Environment.GetEnvironmentVariable("ProgramFiles") ?? "%ProgramFiles%";
            string programFilesX86 = Environment.GetEnvironmentVariable("ProgramFiles(x86)") ?? "%ProgramFiles(x86)%";
            string[] candidates =
            {
                Path.Combine(localAppData, "Programs", "Ollama", "ollama.exe"),
                Path.Combine(programFiles, "Ollama", "ollama.exe"),
                Path.Combine(programFilesX86, "Ollama", "ollama.exe")
            };

            foreach (string candidate in candidates)
            {
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }

            return string.Empty;
        }

        private static string FindOnPath(string executableName)
        {
            string pathValue = Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
            foreach (string rawDir in pathValue.Split(Path.PathSeparator))
            {
                string dir = rawDir.Trim();
                if (dir.Length == 0)
                {
                    continue;
                }

                try
                {
                    string candidate = Path.Combine(dir, executableName);
                    if (File.Exists(candidate))
                    {
                        return candidate;
                    }
                }
                catch (ArgumentException)
                {
                }
                catch (NotSupportedException)
                {
                }
            }

            return string.Empty;
        }

        private static void ShowOllamaInstallPrompt()
        {
            DialogResult result = MessageBox.Show(
                "Ollama が見つかりません。\n\nGemma4_12B を使うには Ollama のインストールが必要です。\n公式ダウンロードページを開きますか？\n\nインストール後、Ollama を一度起動してから Gemma4_12B を再実行してください。",
                "Gemma4 12B",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Warning
            );

            if (result != DialogResult.Yes)
            {
                return;
            }

            try
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = "https://ollama.com/download",
                    UseShellExecute = true
                });
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Ollama のダウンロードページを開けませんでした。\n\nhttps://ollama.com/download\n\n" + ex.Message,
                    "Gemma4 12B",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }
    }
}
