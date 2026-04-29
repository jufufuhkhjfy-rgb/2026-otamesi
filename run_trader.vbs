Set objFSO   = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")

' このファイルがある場所を取得
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' ANTHROPIC_API_KEY を設定したい場合はここに書く（不要なら空のまま）
' objShell.Environment("PROCESS")("ANTHROPIC_API_KEY") = "sk-ant-xxxxxx"

' 黒い画面なしで python を起動（0 = 非表示）
objShell.Run "cmd /c cd /d """ & strDir & """ && python trader_app.py >> trader.log 2>&1", 0, False

' 少し待ってからブラウザで開く（trader_app.py 側でも開くが念のため）
WScript.Sleep 2000
