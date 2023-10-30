import os
import uvicorn
import logging
from sarufi import Sarufi
from dotenv import load_dotenv
from pymessenger.bot import Bot
from fastapi import FastAPI,Response, Request,BackgroundTasks


# Initialize Flask App
app = FastAPI()

# Load .env file
load_dotenv()

# Make sure all required environment variables are set
if os.getenv("PAGE_ACCESS_TOKEN") is None:
  raise ValueError("PAGE_ACCESS_TOKEN not set")
if os.getenv("VERIFY_TOKEN") is None:
  raise ValueError("VERIFY_TOKEN not set")
if os.getenv("SARUFI_API_KEY") is None:
  raise ValueError("SARUFI_API_KEY not set")
if os.getenv("SARUFI_BOT_ID") is None:
  raise ValueError("SARUFI_BOT_ID not set")


VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PORT= os.getenv("PORT", 8000)

# facebook messenger object 
facebook=Bot(os.getenv("PAGE_ACCESS_TOKEN") ,api_version=16.0)

# sarufi object
sarufi_bot=Sarufi(os.getenv("SARUFI_API_KEY"))
bot=sarufi_bot.get_bot(os.getenv("SARUFI_BOT_ID"))

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def execute_actions(actions: dict, sender_id: str):
  try:

    if actions.get("actions"):
      media_actions = []  # store media actions
      text_button_actions = []  # text/button actions

      for action in actions.get("actions"):
        if action.get("send_images") or action.get("send_videos") or action.get("send_documents") or action.get("send_audios"):
          media_actions.append(action)
        else:
          text_button_actions.append(action)

      facebook.send_action(sender_id, "typing_on")
      # Send media actions first
      for media_action in media_actions:
        if media_action.get("send_images"):
          images = media_action.get("send_images")
          elements = [{"title": image.get("caption"),"image_url": image.get("link")} for image in images]
          facebook.send_generic_message(sender_id, elements=elements)

        elif media_action.get("send_videos"):
          videos = media_action.get("send_videos")
          for video in videos:
            link = video.get("link")
            facebook.send_video_url(sender_id, video_url=link)

        elif media_action.get("send_documents"):
          documents = media_action.get("send_documents")
          for document in documents:
            link = document.get("link")
            facebook.send_file_url(sender_id, file_url=link)

        elif media_action.get("send_audios"):
          audios = media_action.get("send_audios")
          for audio in audios:
            link = audio.get("link")
            facebook.send_audio_url(sender_id, audio_url=link)
      
      # Send text/button actions
      for text_button_action in text_button_actions:
        if text_button_action.get("send_message"):
          message = text_button_action.get("send_message")
          if isinstance(message, list):
            message = "\n".join(message)
          facebook.send_text_message(message=message, recipient_id=sender_id)

        elif text_button_action.get("send_reply_button"):
          message = text_button_action["send_reply_button"]["body"]["text"]
          buttons = text_button_action["send_reply_button"]["action"]['buttons']
          buttons = [{"type": "postback", "title": button["reply"]["title"], "payload": button["reply"]["id"]} for button in buttons]
          facebook.send_button_message(text=message, buttons=buttons, recipient_id=sender_id)

        elif text_button_action.get("send_button"):
          actions = text_button_action.get("send_button")
          message = actions.get("body")
          buttons = actions["action"]["sections"][0]["rows"]
          buttons = [{"content_type": "text", "title": button["title"], "payload": button["id"]} for button in buttons]
          message_template = {
              "text": message,
              "quick_replies": buttons
          }
          facebook.send_message(recipient_id=sender_id, message=message_template)
        
        else:
            logging.info("The message type is not supported by now")

  except Exception as error:
    logging.error(f"{error} in execute_actions")


def respond(sender_id: str, message: str, message_type: str = "text"):
  """
    Send message to user
  """
  try:
    response =bot.respond(message=message,
                          chat_id=sender_id,
                          message_type=message_type,
                          channel="whatsapp")
    
    return execute_actions(response,sender_id)
  except Exception as error:
    logging.error(f"{error} in respond")
  

@app.get("/")
async def webhook_verification(request: Request):
  """
  Handle webhook verification from Facebook Messenger
  """
  if request.query_params.get("hub.verify_token") == VERIFY_TOKEN:
    content=request.query_params.get("hub.challenge")
    logging.info("Verified webhook")
    return Response(content=content, media_type="text/plain", status_code=200)

  logging.error("Webhook Verification failed")
  return "Invalid verification token"


@app.post("/")
async def webhook_handler(request: Request,tasks:BackgroundTasks):
  """
  Handle webhook events from Facebook Messenger
  """
  data = await request.json()
  logging.info("Received webhook data: %s", data)
  data_received = data['entry'][0]

  if data_received.get("messaging"):
    data=data_received['messaging'][0]
    sender_id = data['sender']['id']

    # mark as seen
    facebook.send_action(sender_id, "mark_seen")

    if data.get("message"):
      message=data["message"].get("text")
      tasks.add_task(respond,sender_id=sender_id,message=message)

    elif data.get("postback"):
      message_id=data["postback"]["payload"]
      tasks.add_task(respond,
                     sender_id=sender_id,
                     message=message_id,
                     message_type="interactive")

  return Response(content="ok",status_code=200)


if __name__ == "__main__":
  uvicorn.run("main:app",port=PORT)