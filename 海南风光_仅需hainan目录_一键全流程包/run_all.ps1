param([Parameter(Mandatory=$true)][string]$HainanDir)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
& python main.py --hainan $HainanDir
if ($LASTEXITCODE -ne 0) { throw "完整流程失败，退出码：$LASTEXITCODE" }
