from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor
from twisted.internet.task import deferLater
from google.cloud import speech
from google.cloud.speech_v1 import types
from ManagerLLM import ManagerLLM
import time

sess = None
audioData = []
listening = True
silenceStartTime = None

systemPrompt = "You are a friendly virtual fitness coach, called FitBot, talking to your client. Mention their name if you know this and is seems appropiate. Be sure to keep a professional and well-mannered conversation. Don't answer any off-topic questions. If someone does ask you a question unrelated to fitness, explain that you are unable to answer it and do not provide the answer to the question. If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information. If you  are provding a list of exercises or a routine,  mark the beginning of the list with <list> and the end with </list>. Only mark the list itself, so that it can be extracted. If you have any comments about the routine or about specific exercises, dont include them in the marked area, but put them before or after. When referencing the list (for example, when saying 'here is the routine:'), keep in mind that the list will be displayed on a seperate display, so don't use ':', but refer to the display. Write down the exercises in the following format:  '[exerciseNr][exercise]; [sets]; [reps]\n'. If you do include a <list></list> section in your response, reference to this in your response. If the conversation seems to be reaching its end, ask whether the user/client has any more fitness-related questions or whether you can be of any more assistance, but don't ask this too often through the conversation. If they don't, you can end the conversation with a friendly greeting in which you adress them by their name if you know their name, and insert the keyword '<stop>' at the very end. If you finish with a question, don't end the conversation yet, as the user won't be able to answer your question anymore then."
introductoryText = "Hello! I am FitBot, your robotic virtual fitness coach. I am here to help you with your fitness journey. I can provide you with information about exercises, routines, and general fitness advice. Before we start our conversation, I was wondering whether we have had the pleasure of crossing paths before?"
LLM = ManagerLLM(systemPrompt, introductoryText)

def transcribeFrame(frame):
    global audioData
    audioChunk = frame["data"].get("body.head.front", b"")
    audioData.append(audioChunk)
    # print(f"Received audio chunk of size: {len(audio_chunk)}")

def generate_audio_chunks():
    global audioData
    while True:
        if not audioData and LLM.listening:
            if silenceStartTime is None:
                silenceStartTime = time.time()
            elif silenceStartTime is not None:
                silenceDuration = time.time() - silenceStartTime
                # print(f"Silence duration: {silenceDuration}")
                if silenceDuration > 2.0:
                    print("Silence detected, stopping transcription")
                    LLM.doneTalking = True
                    LLM.listening = False
                    silenceStartTime = None
        else:
            silenceStartTime = None

        # print(LLM.listening)
        # print("Generating audio chunks...", LLM.listening)
        while audioData:
            chunk = audioData.pop(0) if LLM.listening else audioData.pop(0) * 0
            # print(f"Yielding audio chunk of size: {len(chunk)}")
            yield types.StreamingRecognizeRequest(audio_content=chunk)
        yield types.StreamingRecognizeRequest(audio_content=b"")
            

@inlineCallbacks
def handle_question(session):
    audioData.clear()

    yield session.subscribe(transcribeFrame, "rom.sensor.hearing.stream")
    yield session.call("rom.sensor.hearing.stream")

    # Start the transcription thread
    reactor.callInThread(transcribe_streaming)

    LLM.robotSession = session

    yield LLM.mainLoop()
    print("Stopped main loop")
    #TODO: reset stream if too long: https://cloud.google.com/speech-to-text/docs/transcribe-streaming-audio#endless-streaming

    # while LLM.listening:
    #     yield deferLater(reactor, 0.1, lambda: None)  # Yield control to allow other operations

    yield session.call("rom.sensor.hearing.close")
    print("Stopped listening")

@inlineCallbacks
def transcribe_streaming():
    try:
        client = speech.SpeechClient.from_service_account_file("/home/arie/UniLeiden/gcloudkey/scriptiellm-440971c004cf.json")

        speechContexts = [speech.SpeechContext(phrases=["fitbot", "push", "pull", "legs", "calisthenics", "workout", "routine", "exercise", "gym", "fitness", "strength", "training", "muscle", "body", "weight", "lifting", "squat", "deadlift", "bench press", "barbell", "dumbbell", "kettlebell", "cardio", "calories", "burn", "fat", "protein", "carbs", "diet", "nutrition", "meal", "plan", "rest", "recovery", "sleep", "hydrate", "water", "supplement", "vitamin", "mineral", "protein shake", "pre workout", "post workout", "warm up", "cool down", "stretch", "flexibility", "mobility", "injury", "pain", "soreness", "form", "technique", "spotter", "personal trainer", "coach", "motivation", "inspiration", "goal", "progress", "success", "failure", "discipline", "consistency"])]

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=False,
            model="video",
            speech_contexts=speechContexts
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
        )

        streamingRequests = generate_audio_chunks()
        responses = client.streaming_recognize(config=streaming_config, requests=streamingRequests)

        print("Starting streaming recognition...")

        for response in responses:
            for result in response.results:
                if result.is_final:
                    transcription = result.alternatives[0].transcript
                    print("Final Transcription: ", transcription)
                    LLM.processTranscription(transcription)
                    # with open("transcription.txt", "a") as f:
                    #     f.write(transcription + "\n")
                # else:
                #     print("Interim Transcription: ", result.alternatives[0].transcript)

    except Exception as e:
        print(f"Error during streaming recognition: {e}")

    yield None

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
    realm="rie.666c0541961f249628fc2f5a",
)

wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])
