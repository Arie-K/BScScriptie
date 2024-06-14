from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.util import sleep
from PIL import Image
from io import BytesIO
from deepface import DeepFace
import os


@inlineCallbacks
def main(session, details):
	imageData = yield session.call("rom.sensor.sight.read")
	imageData = imageData[0]["data"]["body.head.eyes"]
	image = Image.open(BytesIO(imageData))
	image.save("frame.jpg")

	dbPath = "face_database/"

	recognitionResult = DeepFace.find(img_path="frame.jpg", db_path=dbPath)
	if recognitionResult: 
		firstMatch = recognitionResult[0]
		matchedImageName = os.path.splitext(os.path.basename(str(firstMatch["identity"])))[0]
		print("Matched Image Name:", matchedImageName)
	else:
		print("No match found.")
	session.leave() # Close the connection with the robot

wamp = Component(
	transports=[{
		"url": "ws://wamp.robotsindeklas.nl",
		"serializers": ["msgpack"],
		"max_retries": 0
	}],
	realm="rie.666c0541961f249628fc2f5a",
)

wamp.on_join(main)

if __name__ == "__main__":
	run([wamp])