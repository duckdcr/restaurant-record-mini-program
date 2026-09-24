param(
    [switch]$Reload,
    [switch]$Seed
    , [switch]$Production
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot

if ($Production) {
    $env:APP_ENV = "production"
}

if (-not $env:APP_ENV) {
    $env:APP_ENV = "development"
}

$argsList = @()
if ($Reload) { $argsList += "--reload" }
if ($Seed) { $argsList += "--seed" }

python backend/run.py @argsList
