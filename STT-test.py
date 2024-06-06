from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor
from twisted.internet.task import deferLater
from google.cloud import speech
from google.cloud.speech_v1 import types

sess = None
full_question = ""
audio_data = []
stop_listening = False
pause_listening = False

def transcribeFrame(frame):
    # print(".")  # Indicate that the function is being called
    global audio_data
    audio_chunk = frame["data"].get("body.head.front", b"")
    audio_data.append(audio_chunk)
    # print(f"Received audio chunk of size: {len(audio_chunk)}")

def generate_audio_chunks():
    global audio_data, stop_listening
    while not stop_listening or audio_data:
        while audio_data:
            chunk = audio_data.pop(0)
            # print(f"Yielding audio chunk of size: {len(chunk)}")
            yield types.StreamingRecognizeRequest(audio_content=chunk)

def listen_for_enter():
    global stop_listening, pause_listening
    print("Press Enter to stop listening, Space to pause listening...\n")
    while not stop_listening:
        inputText = input()
        if inputText == "":
            stop_listening = True
        if inputText == " ":
            print("Paused listening")
            pause_listening = not pause_listening

@inlineCallbacks
def handle_question(session):
    global stop_listening
    stop_listening = False
    audio_data.clear()

    yield session.call("rie.dialogue.say", text="Ask a question", lang="en")
    print("Listening...")

    yield session.subscribe(transcribeFrame, "rom.sensor.hearing.stream")
    yield session.call("rom.sensor.hearing.stream")

    session.call("rie.dialogue.say", text="test 1 2 3 4 asd asd asd ss s sd sf as fas fas ", lang="en")
    print("klaar")

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
    global audio_data
    try:
        client = speech.SpeechClient.from_service_account_file("/home/arie/UniLeiden/gcloudkey/scriptiellm-440971c004cf.json")

        speech_contexts = [speech.SpeechContext(phrases=["fitbot", "push", "pull", "legs", "workout", "routine", "exercise", "gym", "fitness", "strength", "training", "muscle", "body", "weight", "lifting", "squat", "deadlift", "bench press", "barbell", "dumbbell", "kettlebell", "cardio", "calories", "burn", "fat", "protein", "carbs", "diet", "nutrition", "meal", "plan", "rest", "recovery", "sleep", "hydrate", "water", "supplement", "vitamin", "mineral", "protein shake", "pre workout", "post workout", "warm up", "cool down", "stretch", "flexibility", "mobility", "injury", "pain", "soreness", "form", "technique", "spotter", "personal trainer", "coach", "motivation", "inspiration", "goal", "progress", "success", "failure", "discipline", "consistency"])]

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="video",
            speech_contexts=speech_contexts
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
                if result.is_final and not pause_listening:
                    transcription = result.alternatives[0].transcript
                    print("Final Transcription: ", transcription)
                    with open("transcription.txt", "a") as f:
                        f.write(transcription + "\n")
                # else:
                #     print("Interim Transcription: ", result.alternatives[0].transcript)

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
    realm="rie.66619f9229fca0a53366e17d",
)

wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])
