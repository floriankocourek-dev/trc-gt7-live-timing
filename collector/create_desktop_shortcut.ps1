$collectorDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $collectorDir "TRC GT7 Collector.vbs"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "TRC GT7 Collector.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $collectorDir
$shortcut.Description = "Start TRC GT7 Collector"
$shortcut.Save()

Write-Host "Desktop shortcut created: $shortcutPath"

