import os
import logging
from pymessenger.bot import Bot
from sarufi import Sarufi
from dotenv import load_dotenv
from flask import Flask, request, make_response
from fastapi import FastAPI,Response, Request,BackgroundTasks

# Initialize Flask App
app = FastAPI()

# Load .env file
load_dotenv()

VERIFY_TOKEN = "30cca545-3838-48b2-80a7-9e43b1ae8ce4"

# facebook messenger object 
facebook=Bot(os.getenv("PAGE_ACCESS_TOKEN") ,api_version=16.0)

# sarufi object
sarufi_bot=Sarufi(os.getenv("SARUFI_API_KEY"))
bot=sarufi_bot.get_bot(os.getenv("SARUFI_BOT_ID"))

# Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def execute_actions(actions: dict, sender_id: str):
  
  if actions.get("actions"):
    actions = reversed(actions["actions"])
    for action in actions:
      if action.get("send_message"):
        message = action.get("send_message")
        if isinstance(message, list):
          message = "\n".join(message)
        facebook.send_text_message(message=message,recipient_id=sender_id)
    
      if action.get("send_reply_button"):
        message=action["send_reply_button"]["body"]["text"]
        buttons=action["send_reply_button"]["action"]['buttons']
        buttons=[{"type":"postback","title":button["reply"]["title"],"payload":button["reply"]["id"]} for button in buttons ]

        facebook.send_button_message(text=message,buttons=buttons,recipient_id=sender_id)
  
      if action.get("send_button"):
        actions=action.get("send_button")
        message=actions.get("body")
        buttons=actions["action"]["sections"][0]["rows"]
        buttons=[{"content_type": "text","title": button["title"],
            "payload": button["id"]} for button in buttons]
        
        message_template = {
        "text": message,
        "quick_replies": buttons
          }
        facebook.send_message(recipient_id=sender_id,message=message_template)

      elif action.get("send_images"):
        images=action.get("send_images")
        for image in images:
          link=image.get("link")
          facebook.send_image_url(sender_id,image_url=link)
  
      elif action.get("send_videos"):
        images=action.get("send_videos")
        for image in images:
          link=image.get("link")
          facebook.send_video_url(sender_id,video_url=link)
  
      elif action.get("send_documents"):
        images=action.get("send_documents")
        for image in images:
          link=image.get("link")
          facebook.send_file_url(sender_id,file_url=link)
  
      elif action.get("send_audios"):
        images=action.get("send_audios")
        for image in images:
          link=image.get("link")
          facebook.send_audio_url(sender_id,audio_url=link)
  
      else:
        logging.info("The message type is not supported by now")
  

def respond(sender_id: str, message: str, message_type: str = "text"):
  """
    Send message to user
  """
  response =bot.respond(message=message,
                        chat_id=sender_id,
                        message_type=message_type,
                        channel="whatsapp")
  
  return execute_actions(response,sender_id)
  

@app.get("/")
async def webhook_verification(request: Request):
  if request.method == "GET":
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
      logging.info("Verified webhook")
      response = make_response(request.args.get("hub.challenge"), 200)
      response.mimetype = "text/plain"
      return response

    logging.error("Webhook Verification failed")
    return "Invalid verification token"


@app.post("/")
async def webhook_handler(request: Request,tasks:BackgroundTasks):
  # Handle Webhook Subscriptions
  data = await request.json()
  logging.info("Received webhook data: %s", data)
  data_received = data['entry'][0]

  if data_received.get("messaging"):
    data=data_received['messaging'][0]
    sender_id = data['sender']['id']

    
    if data.get("message"):
      message=data["message"].get("text")
      tasks.add_task(respond,sender_id,message)

    elif data["postback"]:
      message_id=(data["postback"]["payload"])
      tasks.add_task(respond,sender_id=sender_id,
              message=message_id,
              message_type="interactive")

  return "ok"


if __name__ == "__main__":
  app.run(debug=True,port=5000)