#!/usr/bin/env python3

import os
import sqlite3

DB = os.path.expanduser(
    os.getenv("DB_PATH", "~/whatsapp-summary/data/messages.db")
)


class MessageNormalizer:

    def __init__(self):
        self.conn = sqlite3.connect(DB)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def normalize(self, row):

        body = (row["body"] or "").strip()
        media_path = (row["media_path"] or "").strip()
        media_type = (row["media_type"] or "").strip().lower()
        filename = (row["media_filename"] or "").strip()

        # Derive filename from media path if missing
        if not filename and media_path:
            filename = os.path.basename(media_path)

        # Remove placeholder caption
        caption = body
        if caption.startswith("<media:"):
            caption = ""

        # -------------------------------------------------
        # Location
        # -------------------------------------------------
        if body.startswith("📍"):

            coordinates = body.replace("📍", "").strip()

            return f"""LOCATION

Coordinates:
{coordinates}

Description:
Pending AI reverse geocoding.
"""

        # -------------------------------------------------
        # Contacts
        # -------------------------------------------------
        if body.startswith("<contacts:"):

            return f"""CONTACTS

Details:
{body}

Summary:
Pending AI analysis.
"""

        # -------------------------------------------------
        # Sticker
        # -------------------------------------------------
        if body == "<sticker>":

            return """STICKER

Sticker shared.
"""

        # -------------------------------------------------
        # MEDIA
        # -------------------------------------------------
        if media_path:

            # ---------------- IMAGE ----------------

            if media_type.startswith("image/"):

                return f"""IMAGE

Filename:
{filename}

Media Type:
{media_type}

Path:
{media_path}

Caption:
{caption or "(No Caption)"}

AI Description:
Pending AI analysis.
"""

            # ---------------- VIDEO ----------------

            elif media_type.startswith("video/"):

                return f"""VIDEO

Filename:
{filename}

Media Type:
{media_type}

Path:
{media_path}

Caption:
{caption or "(No Caption)"}

AI Summary:
Pending AI analysis.
"""

            # ---------------- AUDIO ----------------

            elif media_type.startswith("audio/"):

                return f"""AUDIO

Filename:
{filename}

Media Type:
{media_type}

Path:
{media_path}

Transcript:
Pending AI transcription.

AI Summary:
Pending AI analysis.
"""

            # ---------------- PDF ----------------

            elif media_type == "application/pdf":

                return f"""DOCUMENT

Filename:
{filename}

Media Type:
{media_type}

Path:
{media_path}

Caption:
{caption or "(No Caption)"}

Extracted Text:
Pending extraction.

AI Summary:
Pending AI analysis.
"""

            # ---------------- OTHER FILES ----------------

            else:

                return f"""FILE

Filename:
{filename}

Media Type:
{media_type}

Path:
{media_path}

Caption:
{caption or "(No Caption)"}

AI Summary:
Pending AI analysis.
"""

        # -------------------------------------------------
        # Plain Text
        # -------------------------------------------------

        return body

    def run(self):

        self.cursor.execute("""
            SELECT *
            FROM messages
            WHERE normalized_content IS NULL
            ORDER BY timestamp
        """)

        rows = self.cursor.fetchall()

        print(f"Found {len(rows)} messages to normalize.\n")

        for row in rows:

            normalized = self.normalize(row)

            self.cursor.execute("""
                UPDATE messages
                SET normalized_content = ?
                WHERE id = ?
            """, (
                normalized,
                row["id"]
            ))

            print(
                f"✓ Message {row['id']} normalized"
            )

        self.conn.commit()

        print("\nNormalization completed.")

        self.conn.close()


if __name__ == "__main__":

    MessageNormalizer().run()
