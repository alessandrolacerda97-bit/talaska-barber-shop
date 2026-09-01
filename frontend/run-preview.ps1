$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
py -m http.server 4173
