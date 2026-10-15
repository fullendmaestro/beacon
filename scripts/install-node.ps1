# Enforce TLS 1.2 for web requests
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "Downloading Node.js installer..."
$nodeInstaller = "$env:TEMP\node.msi"
Invoke-WebRequest -Uri "https://nodejs.org/dist/v22.14.0/node-v22.14.0-x64.msi" -OutFile $nodeInstaller

Write-Host "Installing Node.js..."
Start-Process -FilePath msiexec.exe -ArgumentList "/i $nodeInstaller /quiet /norestart" -Wait
Remove-Item -Path $nodeInstaller

Write-Host "Installing Bun..."
Invoke-RestMethod -Uri https://bun.sh/install.ps1 | Invoke-Expression

Write-Host "Node.js and Bun installation complete. You may need to restart your terminal to load the updated PATH."