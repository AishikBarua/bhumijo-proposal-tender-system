' Launches server_loop.bat with no window at all.
'
' Used by install_autostart.bat so the tracker starts silently every time you
' log in. Because nothing appears on screen, the access token and address are
' not printed anywhere you can see them — read them from
' data\SERVER_INFO.txt instead, which is rewritten on every start.

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strPath

objShell.Run """" & strPath & "\server_loop.bat""", 0, False
