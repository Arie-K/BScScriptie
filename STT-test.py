from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor
from twisted.internet.task import deferLater
from google.cloud import speech
from google.cloud.speech_v1 import types
import threading

sess = None
full_question = ""
audio_data = []
stop_listening = False

def transcribeFrame(frame):
    # print(".")  # Indicate that the function is being called
    global audio_data
    audio_chunk = frame["data"].get("body.head.front", b"")
    audio_data.append(audio_chunk)
    # print(f"Received audio chunk of size: {len(audio_chunk)}")

def generate_audio_chunks():
    global audio_data
    while not stop_listening or audio_data:
        while audio_data:
            chunk = audio_data.pop(0)
            # print(f"Yielding audio chunk of size: {len(chunk)}")
            yield types.StreamingRecognizeRequest(audio_content=chunk)

def listen_for_enter():
    global stop_listening
    input("Press Enter to stop listening...\n")
    stop_listening = True

@inlineCallbacks
def handle_question(session):
    global stop_listening
    stop_listening = False
    audio_data.clear()

    yield session.call("rie.dialogue.say", text="Ask a question", lang="en")
    print("Listening...")

    yield session.subscribe(transcribeFrame, "rom.sensor.hearing.stream")
    yield session.call("rom.sensor.hearing.stream")

    # Start the transcription thread
    reactor.callInThread(transcribe_streaming)

    # Start a thread to listen for the Enter key
    reactor.callInThread(listen_for_enter)

    while not stop_listening:
        yield deferLater(reactor, 0.1, lambda: None)  # Yield control to allow other operations

    yield session.call("rom.sensor.hearing.close")
    print("Stopped listening")

@inlineCallbacks
def transcribe_streaming():
    global audio_data, stop_listening
    try:
        client = speech.SpeechClient.from_service_account_file("/home/arie/UniLeiden/gcloudkey/scriptiellm-440971c004cf.json")

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="video"
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
        )

        streaming_requests = generate_audio_chunks()
        responses = client.streaming_recognize(config=streaming_config, requests=streaming_requests)

        print("Starting streaming recognition...")

        for response in responses:
            for result in response.results:
                if result.is_final:
                    transcription = result.alternatives[0].transcript
                    print("Final Transcription: ", transcription)
                    with open("transcription.txt", "a") as f:
                        f.write(transcription + "\n")
                else:
                    print("Interim Transcription: ", result.alternatives[0].transcript)

    except Exception as e:
        print(f"Error during streaming recognition: {e}")

    # Ensure the function returns a generator
    yield None  # Or you can yield a value if needed

@inlineCallbacks
def main(session, details):
    global sess
    sess = session
    yield handle_question(session)
    sess.leave()  # Close connection with the robot

wamp = Component(
    transports=[{
        "url": "ws://wamp.robotsindeklas.nl",
        "serializers": ["msgpack"],
        "max_retries": 0
    }],
    realm="rie.6660665c29fca0a53366d9ea",
)

wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])
