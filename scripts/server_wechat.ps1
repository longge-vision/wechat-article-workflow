param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

$ErrorActionPreference = "Stop"

$Key = "C:\Users\User\.ssh\codex_server_generated"
$HostName = "175.178.71.163"
$User = "deploy"
$RemoteScript = "/home/deploy/wechat-publisher/tools/wechat_ops.py"

if (-not $env:WECHAT_APP_ID -or -not $env:WECHAT_APP_SECRET) {
  throw "WECHAT_APP_ID and WECHAT_APP_SECRET must be set in local environment."
}

if (-not $Args -or $Args.Count -eq 0) {
  $Args = @("--help")
}

function Quote-Remote([string]$Value) {
  return "'" + ($Value -replace "'", "'\''") + "'"
}

$remoteArgs = ($Args | ForEach-Object { Quote-Remote $_ }) -join " "
$appId = Quote-Remote $env:WECHAT_APP_ID
$secret = Quote-Remote $env:WECHAT_APP_SECRET

$remote = @"
export WECHAT_APP_ID=$appId
export WECHAT_APP_SECRET=$secret
python3 $RemoteScript $remoteArgs
"@

ssh -i $Key "$User@$HostName" $remote
