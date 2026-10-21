$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
function Segredo { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ }) }
$linhas = (Get-Content (Join-Path $raiz ".env.example")) -replace "^ARGO_DB_PASSWORD=.*", "ARGO_DB_PASSWORD=$(Segredo)" -replace "^ARGO_JWT_SECRET=.*", "ARGO_JWT_SECRET=$(Segredo)" -replace "^ARGO_INTERNAL_TOKEN=.*", "ARGO_INTERNAL_TOKEN=$(Segredo)"
[IO.File]::WriteAllLines((Join-Path $raiz ".env"), $linhas)
Write-Host "Arquivo .env criado com segredos aleatorios."
