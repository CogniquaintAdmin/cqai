#!/usr/bin/env python3

from pathlib import Path
import re
import shutil

MONITOR = (
    Path.home()
    / ".openclaw/extensions/whatsapp/dist/monitor-DD8bXohk.js"
)

NEW_LOGGER = """inboundLogger.info({
\t\t\tfrom: inbound.from,
\t\t\tto: self.e164 ?? "me",

\t\t\t// ==========================================================
\t\t\t// Conversation
\t\t\t// ==========================================================
\t\t\tremoteJid: inbound.remoteJid,
\t\t\tgroupName: inbound.groupSubject,

\t\t\t// ==========================================================
\t\t\t// Sender
\t\t\t// ==========================================================
\t\t\tparticipant: inbound.participantJid,
\t\t\tsenderJid: inbound.participantJid,
\t\t\tsenderE164: inbound.senderE164,
\t\t\tpushName: msg.pushName,

\t\t\t// ==========================================================
\t\t\t// Group
\t\t\t// ==========================================================
\t\t\tgroupParticipants: inbound.groupParticipants,

\t\t\t// ==========================================================
\t\t\t// Reply Context
\t\t\t// ==========================================================
\t\t\treply: enriched.replyContext,

\t\t\t// ==========================================================
\t\t\t// Mentions
\t\t\t// ==========================================================
\t\t\tmentionedJids,

\t\t\t// ==========================================================
\t\t\t// Message
\t\t\t// ==========================================================
\t\t\tbody: enriched.body,
\t\t\tcommandBody: enriched.commandBody,
\t\t\tmediaPath: enriched.mediaPath,
\t\t\tmediaType: enriched.mediaType,
\t\t\tmediaFileName: enriched.mediaFileName,
\t\t\tlocation: enriched.location,

\t\t\t// ==========================================================
\t\t\t// Contact / Ads
\t\t\t// ==========================================================
\t\t\tcontactContext: enriched.contactContext,
\t\t\texternalAdReplyContext: enriched.externalAdReplyContext,

\t\t\t// ==========================================================
\t\t\t// WhatsApp Metadata
\t\t\t// ==========================================================
\t\t\tmessageId: msg.key?.id,
\t\t\tfromMe: msg.key?.fromMe,
\t\t\ttimestamp

\t\t}, "inbound message");"""

pattern = re.compile(
    r'inboundLogger\.info\s*\(\s*\{.*?\}\s*,\s*"inbound message"\s*\);',
    re.DOTALL,
)

if not MONITOR.exists():
    print(f"❌ Monitor file not found: {MONITOR}")
    raise SystemExit(1)

text = MONITOR.read_text(encoding="utf-8")

match = pattern.search(text)

if not match:
    print("❌ Could not locate inboundLogger.info()")
    raise SystemExit(1)

backup = MONITOR.with_suffix(".js.bak")
shutil.copy2(MONITOR, backup)

patched = pattern.sub(
    NEW_LOGGER,
    text,
    count=1,
)

MONITOR.write_text(
    patched,
    encoding="utf-8",
)

print("✅ monitor patched successfully")
print(f"Backup : {backup}")
print(f"Monitor: {MONITOR}")