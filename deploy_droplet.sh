#!/bin/bash
# Deployment script for Trader MCP Server on DigitalOcean Droplet
# Run this script on your droplet to set up the trading server

set -e

echo "🚀 Deploying Trader MCP Server to DigitalOcean Droplet"
echo "=" * 60

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and pip
echo "🐍 Installing Python and pip..."
sudo apt install -y python3 python3-pip python3-venv

# Create application directory
echo "📁 Setting up application directory..."
mkdir -p /opt/trader
cd /opt/trader

# Clone repository
echo "📥 Cloning trader repository..."
git clone https://github.com/ajberenstein/trader.git .
git checkout main

# Set up virtual environment
echo "🔧 Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Configure environment
echo "⚙️  Setting up environment configuration..."
cp .env.example .env
echo "❗ Please edit /opt/trader/.env with your Alpaca API credentials"
echo "   nano /opt/trader/.env"

# Create systemd service
echo "🔄 Creating systemd service..."
sudo tee /etc/systemd/system/trader-mcp.service > /dev/null <<EOF
[Unit]
Description=Trader MCP Server for Claude for Work
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/trader
ExecStart=/opt/trader/.venv/bin/python /opt/trader/mcp_server.py
Restart=always
RestartSec=5
Environment=PATH=/opt/trader/.venv/bin

[Install]
WantedBy=multi-user.target
EOF

# Set proper permissions
sudo chown -R www-data:www-data /opt/trader
sudo chmod 600 /opt/trader/.env

# Enable and start service
echo "▶️  Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable trader-mcp
sudo systemctl start trader-mcp

# Configure firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 8080/tcp
sudo ufw --force enable

# Check service status
echo "📊 Checking service status..."
sudo systemctl status trader-mcp --no-pager

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit /opt/trader/.env with your Alpaca credentials"
echo "2. Restart service: sudo systemctl restart trader-mcp"
echo "3. Check logs: sudo journalctl -u trader-mcp -f"
echo "4. Configure Claude for Work to connect to: http://your-droplet-ip:8000"
echo ""
echo "🔒 Security notes:"
echo "- The server runs on port 8000"
echo "- Only allow Claude for Work connections"
echo "- Consider setting up SSL/TLS for production"
echo ""
echo "📊 Monitor with:"
echo "sudo systemctl status trader-mcp"
echo "sudo journalctl -u trader-mcp -f"