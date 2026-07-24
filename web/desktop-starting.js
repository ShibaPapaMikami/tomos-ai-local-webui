(() => {
  const messages = {
    "missing_resource_root": "TOMOSの実行環境を確認できませんでした。再インストールしてください。",
    "missing_python": "TOMOSの実行環境を確認できませんでした。再インストールしてください。",
    "port_in_use": "TOMOSが使う場所を別のアプリが使用しています。ほかのTOMOSを終了して、もう一度開いてください。",
    "server_exited": "TOMOSを起動できませんでした。診断情報を確認してください。",
    "timeout": "TOMOSの起動に時間がかかっています。Ollamaを確認して、もう一度開いてください。",
  };
  const title = document.querySelector("#desktop-startup-title");
  const message = document.querySelector("#desktop-startup-message");

  window.TOMOS_DESKTOP_STARTUP = {
    showReady() {
      title.textContent = "TOMOSを開いています";
      message.textContent = "準備ができました。";
    },
    showError(code) {
      title.textContent = "TOMOSを起動できませんでした";
      message.textContent = messages[code] || "TOMOSを起動できませんでした。診断情報を確認してください。";
    },
  };
})();
