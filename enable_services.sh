#!/bin/bash

set -e

echo "Enabling WhatsApp Summary services..."

sudo systemctl daemon-reload

sudo systemctl enable whatsapp-collector.service
sudo systemctl enable whatsapp-normaliser.service

sudo systemctl start whatsapp-collector.service
sudo systemctl start whatsapp-normaliser.service

echo ""
echo "Current Status"
echo "=============="

systemctl status whatsapp-collector --no-pager
echo ""
systemctl status whatsapp-normaliser --no-pager

echo ""
echo "Done."
