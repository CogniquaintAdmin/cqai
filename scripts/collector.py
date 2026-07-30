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
            CREATE TABLE IF NOT EXISTS groups (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- WhatsApp Group JID
                group_id TEXT UNIQUE NOT NULL,

                -- WhatsApp Group Name
                group_name TEXT,

                -- Group Participants
                participants TEXT NOT NULL DEFAULT '[]',

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP

            )
        """)

        #Create messages table with FK to groups
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- ==========================================================
                -- Conversation
                -- ==========================================================
                group_id TEXT NOT NULL,
                group_name TEXT,

                -- ==========================================================
                -- Sender
                -- ==========================================================
                sender TEXT,
                participant TEXT,
                sender_e164 TEXT,
                push_name TEXT,

                -- ==========================================================
                -- Message
                -- ==========================================================
                body TEXT,
                command_body TEXT,
                message_type TEXT,

                -- ==========================================================
                -- Reply
                -- ==========================================================
                reply TEXT,

                -- ==========================================================
                -- Mentions
                -- ==========================================================
                mentioned_jids TEXT,

                -- ==========================================================
                -- Media
                -- ==========================================================
                media_path TEXT,
                media_type TEXT,
                media_filename TEXT,

                -- ==========================================================
                -- Location
                -- ==========================================================
                location TEXT,

                -- ==========================================================
                -- WhatsApp Metadata
                -- ==========================================================
                remote_jid TEXT,
                message_id TEXT UNIQUE,
                from_me INTEGER DEFAULT 0,
                timestamp INTEGER,

                -- ==========================================================
                -- Raw Event
                -- ==========================================================
                normalized_event TEXT,

                -- ==========================================================
                -- AI Processing
                -- ==========================================================
                normalized_content TEXT,

                enrichment_status TEXT DEFAULT 'pending',

                ai_content TEXT,
                ai_metadata TEXT,

                ocr_text TEXT,
                transcript TEXT,
                ai_caption TEXT,

                enriched_at DATETIME,
                last_error TEXT,

                -- ==========================================================
                -- Audit
                -- ==========================================================
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (group_id)
                    REFERENCES groups(group_id)

            )
        """)
    
        self.conn.commit()

    def save(self, message):

        # Ensure group exists
        participants = json.dumps(payload := (message.normalized_event or {}).get("groupParticipants", []))

        self.conn.execute(
            """
            INSERT INTO groups (group_id, group_name, participants)
            VALUES (?, ?, ?)
            ON CONFLICT(group_id)
            DO UPDATE SET
                group_name=excluded.group_name,
                participants=excluded.participants,
                updated_at=CURRENT_TIMESTAMP
            """,
            (message.group_id, message.group_name, participants)
        )

        self.conn.execute(
                        """
                        INSERT INTO messages (

                            group_id,
                            group_name,

                            sender,
                            participant,
                            sender_e164,
                            push_name,

                            body,
                            command_body,
                            message_type,

                            reply,

                            mentioned_jids,

                            media_path,
                            media_type,
                            media_filename,

                            location,

                            timestamp,
                            remote_jid,
                            message_id,
                            from_me,

                            normalized_event

                        )

                        VALUES (
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?
                        )
                        """,
                        (

                            # ======================================================
                            # Conversation
                            # ======================================================
                            message.group_id,
                            message.group_name,

                            # ======================================================
                            # Sender
                            # ======================================================
                            message.sender,
                            message.participant,
                            message.sender_e164,
                            message.push_name,

                            # ======================================================
                            # Message
                            # ======================================================
                            message.body,
                            getattr(message, "command_body", None),
                            message.message_type.value,

                            # ======================================================
                            # Reply
                            # ======================================================
                            json.dumps(getattr(message, "reply", None)),

                            # ======================================================
                            # Mentions
                            # ======================================================
                            json.dumps(message.mentioned_jids or []),

                            # ======================================================
                            # Media
                            # ======================================================
                            message.media_path,
                            message.media_type,
                            message.media_filename,

                            # ======================================================
                            # Location
                            # ======================================================
                            json.dumps(getattr(message, "location", None)),

                            # ======================================================
                            # WhatsApp Metadata
                            # ======================================================
                            message.timestamp,
                            message.remote_jid,
                            message.message_id,
                            int(message.from_me),

                            # ======================================================
                            # Raw Event
                            # ======================================================
                            json.dumps(message.normalized_event or {}),

                        ),
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

                # ==========================================================
                # Conversation
                # ==========================================================
                group_id=payload.get("from", ""),
                group_name=payload.get("groupName"),

                # ==========================================================
                # Sender
                # ==========================================================
                sender=payload.get("to", ""),
                participant=payload.get("participant"),
                sender_e164=payload.get("senderE164"),
                push_name=payload.get("pushName"),

                # ==========================================================
                # Message
                # ==========================================================
                body=payload.get("body", ""),
                command_body=payload.get("commandBody"),
                message_type=self.detect_type(payload),

                # ==========================================================
                # Reply
                # ==========================================================
                reply=payload.get("reply"),

                # ==========================================================
                # Mentions
                # ==========================================================
                mentioned_jids=payload.get("mentionedJids", []),

                # ==========================================================
                # Media
                # ==========================================================
                media_path=payload.get("mediaPath"),
                media_type=payload.get("mediaType"),
                media_filename=payload.get("mediaFileName"),

                # ==========================================================
                # Location
                # ==========================================================
                location=payload.get("location"),

                # ==========================================================
                # WhatsApp Metadata
                # ==========================================================
                timestamp=payload.get("timestamp", 0),
                remote_jid=payload.get("remoteJid"),
                message_id=payload.get("messageId"),
                from_me=payload.get("fromMe", False),

                # ==========================================================
                # Raw Event
                # ==========================================================
                normalized_event=payload,

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