#!/bin/bash

set -e

echo "Disabling WhatsApp Summary services..."

sudo systemctl stop whatsapp-collector.service
sudo systemctl stop whatsapp-normaliser.service

sudo systemctl disable whatsapp-collector.service
sudo systemctl disable whatsapp-normaliser.service

sudo systemctl daemon-reload
sudo systemctl reset-failed

echo ""
echo "Current Status"
echo "=============="

systemctl status whatsapp-collector --no-pager || true
echo ""
systemctl status whatsapp-normaliser --no-pager || true

echo ""
echo "Done."
