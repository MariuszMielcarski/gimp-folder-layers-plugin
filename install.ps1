[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$PluginDirectory,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

if (-not $PluginDirectory) {
    if (-not $env:APPDATA) {
        throw 'Brak APPDATA. Podaj katalog wtyczek przez -PluginDirectory.'
    }
    $gimpRoot = Join-Path $env:APPDATA 'GIMP'
    $profile = Get-ChildItem -LiteralPath $gimpRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^\d+\.\d+$' } |
        Sort-Object { [version]$_.Name } -Descending |
        Select-Object -First 1
    $profileName = if ($profile) { $profile.Name } else { '3.0' }
    $PluginDirectory = Join-Path $gimpRoot "$profileName\plug-ins"
}

$sourceDirectory = Join-Path $PSScriptRoot 'folder-layers'
$destinationDirectory = Join-Path $PluginDirectory 'folder-layers'
$fileNames = @('folder-layers.py', 'folder_layers_core.py')
$pendingFiles = @()

foreach ($fileName in $fileNames) {
    $source = Join-Path $sourceDirectory $fileName
    $destination = Join-Path $destinationDirectory $fileName
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Brak pliku pluginu: $source"
    }
    if (Test-Path -LiteralPath $destination) {
        if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
            throw "Sciezka docelowa nie jest plikiem: $destination"
        }
        if ((Get-FileHash -LiteralPath $source).Hash -eq (Get-FileHash -LiteralPath $destination).Hash) {
            continue
        }
        if (-not $Force) {
            throw "Istnieje inna wersja: $destination. Aby ja nadpisac, uzyj -Force."
        }
    }
    $pendingFiles += $fileName
}

if ($pendingFiles.Count -eq 0) {
    Write-Output "Plugin jest juz aktualny: $destinationDirectory"
} elseif ($PSCmdlet.ShouldProcess($destinationDirectory, 'Instalacja pluginu Folder Layers')) {
    New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    foreach ($fileName in $pendingFiles) {
        Copy-Item -LiteralPath (Join-Path $sourceDirectory $fileName) -Destination (Join-Path $destinationDirectory $fileName) -Force
    }
    Write-Output "Zainstalowano Folder Layers: $destinationDirectory"
    Write-Output 'Uruchom ponownie Gimpa. Polecenia pluginu znajdziesz w menu Plik.'
}