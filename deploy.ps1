# Download cloudcli
Invoke-WebRequest -Uri "https://github.com/Kamatera/cloudcli/releases/latest/download/cloudcli-windows-amd64.exe" -OutFile "cloudcli.exe"

# Initialize cloudcli (manual step)
Write-Output "Please enter your Kamatera API credentials when prompted"
.\cloudcli.exe init

# Create server
$server = .\cloudcli.exe server create `
  --name docbox-prod `
  --cpu 4 `
  --ram 8192 `
  --disk-size 100 `
  --disk-type SSD `
  --datacenter US-NY `
  --image Ubuntu_22.04_64-bit `
  --network "name=wan,ip=auto" `
  --ssh-key "$env:USERPROFILE\.ssh\id_rsa.pub"

# Extract server IP
$serverIP = ($server | ConvertFrom-Json).ip

# Wait for SSH to be available
$sshReady = $false
$attempts = 0
while (-not $sshReady -and $attempts -lt 10) {
    try {
        $null = New-Object System.Net.Sockets.TcpClient($serverIP, 22)
        $sshReady = $true
    } catch {
        $attempts++
        Start-Sleep -Seconds 30
    }
}

# Run provisioning script
scp -o StrictHostKeyChecking=no provision.sh root@${serverIP}:/root/
ssh -o StrictHostKeyChecking=no root@$serverIP "chmod +x /root/provision.sh && /root/provision.sh"
