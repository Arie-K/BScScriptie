from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.util import sleep
from google.cloud import speech


sess = None
full_question = ""

def transcribe_file(speech_file: str):
    try:
        print("transcribe_file")
        client = speech.SpeechClient()
        with open(speech_file, "rb") as audio_file:
            content = audio_file.read()
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="nl-NL",
        )
        response = client.recognize(config=config, audio=audio)
        output = ""
        for result in response.results:
            output += result.alternatives[0].transcript
        print(output.strip())
        return output.strip()
    except Exception as e:
        print(e)
        return ""

def transcribeFrame(frame):
    print("2")
    audio_data = b""
    audio_data += frame["data"].get("body.head.front", b"")
    with open ("output.raw", "wb") as raw_file:
        raw_file.write(audio_data)
    currentFrame = transcribe_file("output.raw")
    print(currentFrame)


# Main loop to handle questions and answers
@inlineCallbacks
def handle_question(session):
    global full_question
    yield session.call("rie.dialogue.say", text="Ask a question", lang="en")

    while True:
        # Listen to question
        print("Press enter to start / stop recording:")
        print("1.1")
        yield input()
        print("Listening...")
        print("1.2")
        session.subscribe(transcribeFrame, "rom.sensor.hearing.stream")
        print("1.3")
        session.call("rom.sensor.hearing.stream")
        print("3")
        # # Read audio frames from the sensor for a specified time duration (8 seconds)
        # frames = yield session.call("rom.sensor.hearing.read", time=8000)
        # # Combine audio data from all frames into a single byte string
        # audio_data = b""
        # for frame in frames:
        #     audio_data += frame["data"].get("body.head.front", b"")
        # # Write the combined audio data to a raw audio file ("output.raw")
        # with open("output.raw", "wb") as raw_file:
        #     raw_file.write(audio_data)
        # # Transcribe the recorded audio file to obtain the user's question
        # full_question = transcribe_file(f"output.raw")
        yield input()
        yield sleep(1)
        print("Stopped listening")
        #print("You: " + full_question + "\n")

        # Quit loop if user says "stop"
        if full_question.lower() == "stop":
            break


# Main function
@inlineCallbacks
def main(session, details):
    global sess
    sess = session
    yield handle_question(session)
    sess.leave()  # Close connection with the robot



# Create connection to Nao
wamp = Component(
    transports=[{
        "url": "ws://wamp.robotsindeklas.nl",
        "serializers": ["msgpack"],
        "max_retries": 0
    }],
    realm="rie.66223f1a94f6248b6e0d1fe9",
)

wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])
