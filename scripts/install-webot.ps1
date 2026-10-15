# Enforce TLS 1.2 for web requests
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "Downloading Webots R2025a..."
$webotsInstaller = "$env:TEMP\webots-R2025a_setup.exe"
$webotsUrl = "https://github.com/cyberbotics/webots/releases/download/R2025a/webots-R2025a_setup.exe"

Invoke-WebRequest -Uri $webotsUrl -OutFile $webotsInstaller

Write-Host "Installing Webots silently (this will take a few minutes)..."
# Webots uses Inno Setup, /VERYSILENT performs a background installation
Start-Process -FilePath $webotsInstaller -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait
Remove-Item -Path $webotsInstaller

Write-Host "Webots R2025a installation complete."