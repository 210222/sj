$TaskName = "Coherence_P2_Daily_Observation"
$PythonExe = "python"
$ScriptPath = "D:\Claudedaoy\coherence\scripts\p2_observation_daily.py"
$WorkingDir = "D:\Claudedaoy\coherence"

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`"" -WorkingDirectory $WorkingDir
$Trigger = New-ScheduledTaskTrigger -Daily -At 09:00
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Force

Write-Host "Scheduled task '$TaskName' created."
Write-Host "Manual run command:"
Write-Host "python D:/Claudedaoy/coherence/scripts/p2_observation_daily.py"
Write-Host "Finalize (day 3) command:"
Write-Host "python D:/Claudedaoy/coherence/scripts/p2_observation_finalize.py"
