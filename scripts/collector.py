#!/usr/bin/env python3

import json
import os
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


# =========================
# CONFIG
# =========================

HOME = Path.home()

DB_PATH = Path(os.getenv(
    "DB_PATH",
    HOME / "whatsapp-summary" / "data" / "messages.db"
))

OPENCLAW = os.getenv(
    "OPENCLAW_BINARY",
    "/usr/bin/openclaw"
)

OPENCLAW_CONFIG = Path(os.getenv(
    "OPENCLAW_CONFIG",
    HOME / ".openclaw" / "openclaw.json"
))


# =========================
# MODEL
# =========================

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    UNKNOWN = "unknown"


@dataclass
class WhatsAppMessage:

    group_id: str
    sender: str
    body: str
    timestamp: int

    message_type: MessageType = MessageType.TEXT

    media_path: Optional[str] = None
    media_type: Optional[str] = None
    media_filename: Optional[str] = None
    remote_jid: Optional[str] = None
    participant: Optional[str] = None
    sender_e164: Optional[str] = None
    push_name: Optional[str] = None
    message_id: Optional[str] = None
    from_me: bool = False
    mentioned_jids: Optional[list] = None
    normalized_event: Optional[dict] = None

    @property
    def has_media(self):
        return self.media_path is not None


# =========================
# DATABASE
# =========================

class MessageRepository:

    def __init__(self, db_path):

        self.conn = sqlite3.connect(db_path)

        # Create groups table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS "groups" (

                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE NOT NULL,
                participants TEXT NOT NULL DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP

            )
        """)

        # Create messages table with FK to groups
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS "messages" (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                group_id TEXT NOT NULL,
                sender TEXT,
                body TEXT,

                message_type TEXT,

                media_path TEXT,
                media_type TEXT,
                media_filename TEXT,

                timestamp INTEGER,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                normalized_content TEXT,

                enrichment_status TEXT DEFAULT 'pending',

                ai_content TEXT,

                ai_metadata TEXT,

                enriched_at DATETIME,

                ocr_text TEXT,
                transcript TEXT,
                ai_caption TEXT,
                last_error TEXT,

                remote_jid TEXT,
                participant TEXT,
                sender_e164 TEXT,
                push_name TEXT,
                message_id TEXT,
                from_me INTEGER DEFAULT 0,
                mentioned_jids TEXT,
                normalized_event TEXT,

                FOREIGN KEY (group_id) REFERENCES groups(group_id)

            )
        """)

        self.conn.commit()

    def save(self, message):

        # Ensure group exists
        participants = json.dumps(payload := (message.normalized_event or {}).get("groupParticipants", []))

        self.conn.execute(
            """
            INSERT INTO groups (group_id, participants)
            VALUES (?, ?)
            ON CONFLICT(group_id)
            DO UPDATE SET
                participants=excluded.participants,
                updated_at=CURRENT_TIMESTAMP
            """,
            (message.group_id, participants)
        )

        self.conn.execute(
            """
            INSERT INTO messages (

                group_id,
                sender,
                body,

                message_type,

                media_path,
                media_type,
                media_filename,

                timestamp,
                remote_jid,
                participant,
                sender_e164,
                push_name,
                message_id,
                from_me,
                mentioned_jids,
                normalized_event

            )

            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (

                message.group_id,
                message.sender,
                message.body,

                message.message_type.value,

                message.media_path,
                message.media_type,
                message.media_filename,

                message.timestamp,
                message.remote_jid,
                message.participant,
                message.sender_e164,
                message.push_name,
                message.message_id,
                int(message.from_me),
                json.dumps(message.mentioned_jids or []),
                json.dumps(message.normalized_event or {})

            )
        )

        self.conn.commit()


# =========================
# PARSER
# =========================
class WebInboundParser:

    @staticmethod
    def detect_type(payload):

        media_type = payload.get("mediaType")

        if media_type:

            media_type = media_type.lower()

            if media_type.startswith("image/"):
                return MessageType.IMAGE

            if media_type.startswith("video/"):
                return MessageType.VIDEO

            if media_type.startswith("audio/"):
                return MessageType.AUDIO

            if media_type.startswith("application/"):
                return MessageType.DOCUMENT

        body = payload.get("body", "")

        if body == "<media:image>":
            return MessageType.IMAGE

        if body == "<media:video>":
            return MessageType.VIDEO

        if body == "<media:audio>":
            return MessageType.AUDIO

        if body == "<media:document>":
            return MessageType.DOCUMENT

        return MessageType.TEXT


    def parse(self, line):

        if "web-inbound" not in line:
            return None

        try:

            start = line.find('{"from"')

            if start == -1:
                return None

            end = line.rfind("} inbound message")

            if end == -1:
                end = line.rfind("}")

            payload = json.loads(line[start:end + 1])

            return WhatsAppMessage(

                group_id=payload.get("from", ""),

                sender=payload.get("to", ""),

                body=payload.get("body", ""),

                timestamp=payload.get("timestamp", 0),

                message_type=self.detect_type(payload),

                media_path=payload.get("mediaPath"),

                media_type=payload.get("mediaType"),

                media_filename=payload.get("mediaFileName"),
                remote_jid=payload.get("remoteJid"),
                participant=payload.get("participant"),
                sender_e164=payload.get("senderE164"),
                push_name=payload.get("pushName"),
                message_id=payload.get("messageId"),
                from_me=payload.get("fromMe", False),
                mentioned_jids=payload.get("mentionedJids", []),
                normalized_event=payload

            )

        except Exception as e:

            print("PARSE ERROR:", e)
            print(line)

            return None


# =========================
# TOKEN
# =========================

def get_gateway_token():

    try:

        with open(OPENCLAW_CONFIG) as f:

            cfg = json.load(f)

        return cfg["gateway"]["auth"]["token"]

    except Exception:

        return None


# =========================
# COLLECTOR
# =========================

class OpenClawCollector:

    def __init__(self):

        self.parser = WebInboundParser()

        self.repo = MessageRepository(str(DB_PATH))

    def start_logs(self):

        cmd = [

            OPENCLAW,

            "logs",

            "--follow",

            "--plain"

        ]

        token = get_gateway_token()

        if token:

            cmd.extend([
                "--token",
                token
            ])

        print("Launching:", " ".join(cmd[:-1] + ["******"]) if token else " ".join(cmd), flush=True)

        return subprocess.Popen(

            cmd,

            stdout=subprocess.PIPE,

            stderr=subprocess.STDOUT,

            text=True,

            bufsize=1

        )

    def run(self):

        print("Starting OpenClaw WhatsApp Collector...", flush=True)

        while True:

            process = self.start_logs()

            try:

                for line in process.stdout:

                    message = self.parser.parse(line)

                    if not message:
                        continue

                    self.repo.save(message)

                    print(

                        f"[SAVED] "

                        f"group={message.group_id} "

                        f"type={message.message_type.value} "

                        f"body={message.body}",

                        flush=True

                    )

            except KeyboardInterrupt:

                process.kill()

                break

            except Exception as e:

                print("Collector Error:", e, flush=True)

            finally:

                process.kill()

            print("openclaw logs exited. Restarting in 5 seconds...", flush=True)

            time.sleep(5)


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    OpenClawCollector().run()