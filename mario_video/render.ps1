$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$ffmpegPath = node -p "require('@ffmpeg-installer/ffmpeg').path"
$ffprobePath = node -p "require('@ffprobe-installer/ffprobe').path"
$env:Path = "$(Split-Path $ffmpegPath);$(Split-Path $ffprobePath);$env:Path"
$env:HYPERFRAMES_CACHE_DIR = Join-Path $PSScriptRoot '.cache'

if (-not $env:HYPERFRAMES_BROWSER_PATH) {
  $browserPaths = @(
    'C:\Program Files\Google\Chrome\Application\chrome.exe',
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
  )
  $browser = $browserPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
  if ($browser) { $env:HYPERFRAMES_BROWSER_PATH = $browser }
}

& .\node_modules\.bin\hyperframes.cmd render --output mario.mp4 --fps 30
exit $LASTEXITCODE
