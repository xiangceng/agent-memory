# 下载 LongMemEval 数据集（官方 cleaned 版本，2025-09 更新）
# 用法：powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root 'data'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$base = 'https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main'
$files = @(
    'longmemeval_oracle.json',
    'longmemeval_s_cleaned.json',
    'longmemeval_m_cleaned.json'
)

foreach ($f in $files) {
    $out = Join-Path $dataDir $f
    if ((Test-Path $out) -and ((Get-Item $out).Length -gt 100000)) {
        Write-Host ("SKIP  " + $f + "  已存在 " + [math]::Round((Get-Item $out).Length/1MB,1) + " MB")
        continue
    }
    Write-Host ("DOWN  " + $f + " ...")
    try {
        Invoke-WebRequest -Uri "$base/$f" -OutFile $out -TimeoutSec 900 -UserAgent 'Mozilla/5.0'
        $mb = [math]::Round((Get-Item $out).Length/1MB, 1)
        Write-Host ("OK    " + $f + "  " + $mb + " MB")
    } catch {
        Write-Host ("FAIL  " + $f + " : " + $_.Exception.Message)
    }
}

Write-Host ""
Write-Host "下载完成，data/ 目录内容："
Get-ChildItem $dataDir -File | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize

Write-Host "提示："
Write-Host "  - longmemeval_oracle.json     仅含证据会话（上限基线，最省 token，建议先跑这个）"
Write-Host "  - longmemeval_s_cleaned.json  约 11.5 万 token/题（主实验用）"
Write-Host "  - longmemeval_m_cleaned.json  约 500 会话/题（很贵，最后再做可扩展性验证）"
