# Enforce TLS 1.2 for web requests
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "Downloading Python 3.12 installer..."
$pythonInstaller = "$env:TEMP\python-installer.exe"
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe" -OutFile $pythonInstaller

Write-Host "Installing Python (this may take a minute)..."
Start-Process -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
Remove-Item -Path $pythonInstaller

Write-Host "Installing uv..."
Invoke-RestMethod -Uri https://astral.sh/uv/install.ps1 | Invoke-Expression

Write-Host "Python and uv installation complete. You may need to restart your terminal to load the updated PATH."