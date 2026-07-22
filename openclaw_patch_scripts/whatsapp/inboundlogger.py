#!/usr/bin/env python3

from pathlib import Path
import re
import shutil

MONITOR = Path.home() / ".openclaw/extensions/whatsapp/dist/monitor-DD8bXohk.js"

NEW_LOGGER = """inboundLogger.info({
\t\t\tfrom: inbound.from,
\t\t\tto: self.e164 ?? "me",

\t\t\t// Group / sender
\t\t\tremoteJid: inbound.remoteJid,
\t\t\tparticipant: inbound.participantJid,
\t\t\tsenderJid: inbound.senderJid,
\t\t\tsenderE164: inbound.senderE164,
\t\t\tpushName: msg.pushName,

\t\t\t// Group metadata
\t\t\tgroupParticipants: inbound.groupParticipants,

\t\t\t// Mentions
\t\t\tmentionedJids,

\t\t\t// Message
\t\t\tbody: enriched.body,
\t\t\tmediaPath: enriched.mediaPath,
\t\t\tmediaType: enriched.mediaType,
\t\t\tmediaFileName: enriched.mediaFileName,

\t\t\t// WhatsApp metadata
\t\t\tmessageId: msg.key?.id,
\t\t\tfromMe: msg.key?.fromMe,
\t\t\ttimestamp
\t\t}, "inbound message");"""

pattern = re.compile(
    r'inboundLogger\.info\s*\(\s*\{.*?\}\s*,\s*"inbound message"\s*\);',
    re.DOTALL,
)

text = MONITOR.read_text(encoding="utf-8")

match = pattern.search(text)

if not match:
    print("❌ Could not locate inboundLogger.info()")
    exit(1)

backup = MONITOR.with_suffix(".js.bak")
shutil.copy2(MONITOR, backup)

patched = pattern.sub(NEW_LOGGER, text, count=1)

MONITOR.write_text(patched, encoding="utf-8")

print("✅ monitor patched")
print(f"Backup: {backup}")