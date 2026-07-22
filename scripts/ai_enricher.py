#!/usr/bin/env python3

import sqlite3
import json
import os
import boto3
import traceback
import tempfile
import subprocess
import shutil
import time
import fitz

from datetime import datetime, timezone
from faster_whisper import WhisperModel


# =============================
# CONFIG
# =============================

DB_PATH = os.getenv(
    "DB_PATH",
    os.path.expanduser("~/whatsapp-summary/data/messages.db")
)

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "30"))

AWS_REGION = os.getenv(
    "AWS_REGION",
    "ap-south-1"
)

BEDROCK_MODEL = os.getenv(
    "BEDROCK_MODEL",
    "amazon.nova-pro-v1:0"
)

BEDROCK_INFERENCE_PROFILE = os.getenv(
    "BEDROCK_INFERENCE_PROFILE",
    None
)

BEDROCK_TARGET = BEDROCK_INFERENCE_PROFILE or BEDROCK_MODEL


# =============================
# CLIENTS
# =============================

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION
)


whisper = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)



# =============================
# HELPERS
# =============================

def now():

    return datetime.now(
        timezone.utc
    ).isoformat()



def get_db_connection():

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_bedrock_text(response):

    try:
        return response["output"]["message"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            "Unexpected Bedrock response format"
        ) from exc


def image_format(path):

    ext=os.path.splitext(path)[1].lower()

    if ext == ".png":
        return "png"

    if ext == ".webp":
        return "webp"

    return "jpeg"



def bedrock_text(prompt):

    response = bedrock.converse(

        modelId=BEDROCK_TARGET,

        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],

        inferenceConfig={
            "maxTokens": 1000,
            "temperature": 0.2
        }
    )

    return parse_bedrock_text(response)



# =============================
# TEXT
# =============================

def enrich_text(text):

    return bedrock_text(
f"""
Analyze this WhatsApp message.

Return:

Summary:
Intent:
Topics:
People:
Organizations:
Locations:
Action Items:
Priority:
Sentiment:


Message:

{text}
"""
    )



# =============================
# IMAGE
# =============================

def enrich_image(row):

    path=row["media_path"]


    if not path or not os.path.exists(path):

        return {
            "content":"Image missing"
        }


    with open(path,"rb") as f:

        image=f.read()



    response=bedrock.converse(

        modelId=BEDROCK_TARGET,

        messages=[
            {
                "role":"user",

                "content":[

                    {
                        "text":
"""
Analyze this WhatsApp image.

Return:

Description:
Objects:
People:
Visible Text:
Important Details:
Actions:
"""
                    },

                    {
                        "image":
                        {
                            "format":
                            image_format(path),

                            "source":
                            {
                                "bytes":image
                            }
                        }
                    }

                ]
            }
        ],

        inferenceConfig={
            "maxTokens":1000
        }
    )


    result=response["output"]["message"]["content"][0]["text"]


    return {

        "content":result,

        "caption":result

    }



# =============================
# PDF / DOCUMENT
# =============================

def enrich_document(row):

    path=row["media_path"]


    if not path or not os.path.exists(path):

        return {
            "content":"Document missing"
        }


    text=""


    doc=fitz.open(path)


    for page in doc:

        text += page.get_text()


    doc.close()



    summary=bedrock_text(
f"""
Analyze this document.

Return:

Summary:
Important Information:
Numbers:
Dates:
Names:
Action Items:


Document:

{text[:12000]}
"""
    )


    return {

        "content":summary,

        "ocr":text

    }



# =============================
# AUDIO
# =============================

def enrich_audio(row):

    path=row["media_path"]


    if not path or not os.path.exists(path):

        return {
            "content":"Audio missing"
        }



    temp=tempfile.mkdtemp()


    try:

        wav=f"{temp}/audio.wav"


        subprocess.run(

            [
                "ffmpeg",
                "-i",
                path,
                "-ar",
                "16000",
                "-ac",
                "1",
                wav,
                "-y"
            ],

            stdout=subprocess.DEVNULL,

            stderr=subprocess.DEVNULL

        )



        segments,info = whisper.transcribe(
            wav
        )


        transcript=""


        for segment in segments:

            transcript += segment.text + " "



        summary=bedrock_text(
f"""
Analyze this WhatsApp voice message.

Transcript:

{transcript}


Return:

Summary:
Intent:
Important Information:
Action Items:
Priority:
"""
        )


        return {

            "content":summary,

            "transcript":transcript

        }


    finally:

        shutil.rmtree(
            temp,
            ignore_errors=True
        )



# =============================
# VIDEO
# =============================

def enrich_video(row):

    path=row["media_path"]


    if not path or not os.path.exists(path):

        return {
            "content":"Video missing"
        }


    temp=tempfile.mkdtemp()


    try:

        output=f"{temp}/frame_%03d.jpg"


        subprocess.run(

            [
                "ffmpeg",
                "-i",
                path,
                "-vf",
                "fps=1",
                "-t",
                "10",
                output
            ],

            stdout=subprocess.DEVNULL,

            stderr=subprocess.DEVNULL

        )


        frames=[]


        for file in sorted(os.listdir(temp))[:5]:

            frame=os.path.join(
                temp,
                file
            )


            with open(frame,"rb") as f:

                img=f.read()



            response=bedrock.converse(

                modelId=BEDROCK_TARGET,

                messages=[

                    {
                        "role":"user",

                        "content":[

                            {
                                "text":
                                "Describe this video frame"
                            },

                            {
                                "image":
                                {
                                    "format":"jpeg",

                                    "source":
                                    {
                                        "bytes":img
                                    }
                                }
                            }

                        ]
                    }

                ]

            )


            frames.append(
                response["output"]
                ["message"]
                ["content"][0]
                ["text"]
            )



        return {

            "content":
            bedrock_text(
f"""
Summarize this video.

Frames:

{frames}

Return:

Events:
Important Details:
Actions:
"""
            )

        }


    finally:

        shutil.rmtree(
            temp,
            ignore_errors=True
        )



# =============================
# ROUTER
# =============================

def enrich(row):

    msg=row["message_type"]


    if msg=="text":

        return {
            "content":
            enrich_text(
                row["normalized_content"]
                or row["body"]
                or ""
            )
        }


    if msg=="image":

        return enrich_image(row)


    if msg in ["document","pdf"]:

        return enrich_document(row)


    if msg=="audio":

        return enrich_audio(row)


    if msg=="video":

        return enrich_video(row)


    return {
        "content":
        enrich_text(
            row["body"] or ""
        )
    }



# =============================
# PROCESSOR
# =============================

def process():

    conn = get_db_connection()

    cur = conn.cursor()


    cur.execute(
"""
SELECT *

FROM messages

WHERE enrichment_status='pending'

ORDER BY timestamp

LIMIT ?

""",
(BATCH_SIZE,)
)


    rows=cur.fetchall()



    for row in rows:

        try:

            cur.execute(
"""
UPDATE messages

SET enrichment_status='processing'

WHERE id=?
""",
(row["id"],)
)

            conn.commit()



            result=enrich(row)



            metadata={

                "model":BEDROCK_TARGET,

                "type":row["message_type"],

                "time":now()

            }



            cur.execute(
"""
UPDATE messages

SET

ai_content=?,

ai_caption=?,

ocr_text=?,

transcript=?,

ai_metadata=?,

enrichment_status='completed',

enriched_at=?,

last_error=NULL

WHERE id=?

""",
(
result.get("content"),
result.get("caption"),
result.get("ocr"),
result.get("transcript"),
json.dumps(metadata),
now(),
row["id"]
)
)

            conn.commit()


            print(
                "Completed:",
                row["id"]
            )


        except Exception as e:

            traceback.print_exc()


            cur.execute(
"""
UPDATE messages

SET

enrichment_status='failed',

last_error=?

WHERE id=?

""",
(
str(e),
row["id"]
)
)

            conn.commit()



    conn.close()



# =============================
# DAEMON
# =============================

def main():

    print(
        "AI Enricher Started"
    )


    while True:

        try:

            process()

        except Exception:

            traceback.print_exc()


        time.sleep(
            SLEEP_SECONDS
        )


if __name__ == "__main__":

    main()
