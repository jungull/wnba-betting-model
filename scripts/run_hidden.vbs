' run_hidden.vbs -- run one command with NO console window, wait for it, return its exit code.
'
' WHY THIS EXISTS. The WNBA scheduled tasks pop console windows because Task Scheduler
' launches console hosts (python.exe, cmd.exe) inside the interactive desktop session. The
' textbook fix is to switch the task principal to S4U so it runs in session 0 -- but that
' requires administrator rights, which are not available on this machine.
'
' Changing a task's ACTION does NOT require admin. So instead of moving the task out of the
' session, we change what it launches: wscript.exe is a WINDOWLESS host, and WshShell.Run
' with window style 0 starts the real command hidden. Net effect is the same -- no window
' ever appears -- and it needs no elevation.
'
' It also fixes the real damage. A visible window can be closed, and closing one sends Ctrl+C
' to the capture process and kills that cycle; roughly 28 cycles had been destroyed that way.
' A window that never exists cannot be closed.
'
' WAITING MATTERS. Run(..., True) blocks until the command finishes and returns its exit
' code, which is then propagated with WScript.Quit. Without that, Task Scheduler would record
' every run as an instant success and "Last Run Result" would stop being a health signal.
'
' Usage:  wscript.exe //nologo run_hidden.vbs "C:\path\to\wrapper.cmd"

Option Explicit

Dim args, target, shell, rc
Set args = WScript.Arguments

If args.Count < 1 Then
    ' No target. Exit non-zero so a misconfigured task shows up as failed rather than passing.
    WScript.Quit 2
End If

target = args(0)

Set shell = CreateObject("WScript.Shell")

On Error Resume Next
' 0 = hidden window, True = wait for completion.
rc = shell.Run(Chr(34) & target & Chr(34), 0, True)
If Err.Number <> 0 Then
    ' Could not launch at all. 3 distinguishes "never started" from the command's own codes.
    WScript.Quit 3
End If
On Error GoTo 0

WScript.Quit rc
