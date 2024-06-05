from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.util import sleep
from google.cloud import speech


sess = None
full_question = ""
audio_data = b""

def transcribe_file(speech_file: str):
    try:
        print("transcribe_file")
        client = speech.SpeechClient.from_service_account_file("/home/arie/UniLeiden/gcloudkey/scriptiellm-440971c004cf.json")
        with open(speech_file, "rb") as audio_file:
            content = audio_file.read()
        print("Content length:", len(content))
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="nl-NL",
            enable_automatic_punctuation=True,
        )
        response = client.recognize(config=config, audio=audio)
        output = ""
        for result in response.results:
            output += result.alternatives[0].transcript
        return output.strip()
    except Exception as e:
        print(e)
        return ""



def transcribeFrame(frame):
    print(".")
    global audio_data
    audio_data += frame["data"].get("body.head.front", b"")


# Main loop to handle questions and answers
@inlineCallbacks
def handle_question(session):
    global full_question
    global audio_data
    yield session.call("rie.dialogue.say", text="Ask a question", lang="en")

    print("Listening...")
    # print("Size: ", len(audio_data))
    yield session.subscribe(transcribeFrame, "rom.sensor.hearing.stream")
    yield session.call("rom.sensor.hearing.stream")
    #frames = yield session.call("rom.sensor.hearing.read", time=5000)
    # Combine audio data from all frames into a single byte string
    # audio_data = b""
    # for frame in frames:
    #     audio_data += frame["data"].get("body.head.front", b"")
    # Write the combined audio data to a raw audio file ("output.raw")
    for i in range(10):
        print(len(audio_data))
        yield sleep(0.5)
    session.call("rom.sensor.hearing.close")
    print("Stopped listening")
    with open ("output.raw", "wb") as raw_file:
        raw_file.write(audio_data)
    full_question = transcribe_file("output.raw")
    print(full_question)
    audio_data = b""
    #print("You: " + full_question + "\n")



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
    realm="rie.662b8e3392cb4b4f64ea1871",
)

wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])
