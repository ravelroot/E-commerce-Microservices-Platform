param(
    [Parameter(Position = 0)][string]$Comando = "ajuda",
    [Parameter(Position = 1)][string]$Argumento = ""
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz

function Ler-Env([string]$nome, [string]$padrao = "") {
    if (-not (Test-Path .env)) { return $padrao }
    $linha = Select-String -Path .env -Pattern "^$nome=(.*)$" | Select-Object -First 1
    if ($linha -and $linha.Matches[0].Groups[1].Value) { return $linha.Matches[0].Groups[1].Value }
    return $padrao
}

function Garantir-Env {
    if (-not (Test-Path .env)) { & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "criar-env.ps1") }
}

function Saude {
    $porta = Ler-Env "ARGO_PORT" "8080"
    foreach ($s in "identity", "catalog", "orders", "billing") {
        try {
            $r = Invoke-RestMethod -TimeoutSec 3 "http://localhost:$porta/api/$s/health"
            Write-Host ("{0,-10} {1} {2}" -f $s, $r.status, $r.version)
        } catch {
            Write-Host ("{0,-10} fora do ar" -f $s)
        }
    }
}

switch ($Comando) {
    "subir" { Garantir-Env; docker compose up -d --build; Saude }
    "parar" { docker compose stop }
    "reiniciar" { docker compose restart }
    "logs" { if ($Argumento) { docker compose logs -f --tail 200 $Argumento } else { docker compose logs -f --tail 200 } }
    "situacao" { docker compose ps }
    "saude" { Saude }
    "diagnostico" { foreach ($s in "identity", "catalog", "orders") { Write-Host "== $s"; docker compose exec -T $s python manage.py doctor } }
    "admin" { docker compose exec identity python manage.py create_admin }
    "recuperar" { docker compose exec orders python manage.py recover_orders }
    "limpar-sessoes" { docker compose exec identity python manage.py cleanup_tokens }
    "backup" {
        $usuario = Ler-Env "ARGO_DB_USER" "argo"
        $senha = Ler-Env "ARGO_DB_PASSWORD"
        New-Item -ItemType Directory -Force -Path backups | Out-Null
        $arquivo = "backups\argo-{0}.sql" -f (Get-Date -Format "yyyyMMdd-HHmmss")
        cmd /c "docker compose exec -T -e MYSQL_PWD=$senha mysql mysqldump -u $usuario --single-transaction --no-tablespaces --set-gtid-purged=OFF --routines --triggers --databases argo_identity argo_catalog argo_orders argo_billing > $arquivo"
        if ($LASTEXITCODE -ne 0) { throw "O backup falhou." }
        Write-Host "Backup salvo em $arquivo"
    }
    "restaurar" {
        if (-not $Argumento -or -not (Test-Path $Argumento)) {
            Write-Host "Uso: argo restaurar backups\argo-AAAAMMDD-HHMMSS.sql"
            Get-ChildItem backups\*.sql -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | ForEach-Object { Write-Host "  $($_.FullName)" }
            exit 1
        }
        $r = Read-Host "Restaurar $Argumento substitui os dados atuais. Digite RESTAURAR para continuar"
        if ($r -ne "RESTAURAR") { Write-Host "Nada foi alterado."; exit 0 }
        $usuario = Ler-Env "ARGO_DB_USER" "argo"
        $senha = Ler-Env "ARGO_DB_PASSWORD"
        docker compose stop worker scheduler identity catalog orders billing | Out-Null
        cmd /c "docker compose exec -T -e MYSQL_PWD=$senha mysql mysql -u $usuario < `"$Argumento`""
        docker compose up -d | Out-Null
        Write-Host "Backup restaurado. Os serviços estão subindo de novo."
    }
    "atualizar" { git pull --ff-only; docker compose up -d --build }
    "zerar" {
        $r = Read-Host "Isso apaga TODOS os dados (pedidos, usuários, notas). Digite ZERAR para confirmar"
        if ($r -eq "ZERAR") { docker compose down -v } else { Write-Host "Nada foi apagado." }
    }
    default {
        Write-Host "Argo · comandos (argo <comando>)"
        Write-Host ""
        Write-Host "  subir            sobe os contêineres (cria o .env na primeira vez)"
        Write-Host "  parar            para os contêineres, mantendo os dados"
        Write-Host "  reiniciar        reinicia os contêineres"
        Write-Host "  logs [serviço]   acompanha os logs"
        Write-Host "  situacao         lista os contêineres e o estado de saúde"
        Write-Host "  saude            consulta /health de cada serviço pelo gateway"
        Write-Host "  diagnostico      roda o manage.py doctor em cada serviço"
        Write-Host "  admin            cria ou promove um Administrador"
        Write-Host "  recuperar        põe na fila de novo pedidos parados ou sem nota"
        Write-Host "  limpar-sessoes   apaga refresh tokens antigos"
        Write-Host "  backup           gera backups\argo-<data>.sql com os quatro bancos"
        Write-Host "  restaurar <arq>  restaura um backup"
        Write-Host "  atualizar        git pull, reconstrói as imagens e sobe de novo"
        Write-Host "  zerar            apaga contêineres e volumes (pede confirmação)"
    }
}
